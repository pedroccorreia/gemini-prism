#!/usr/bin/env python3
"""
Gemini Enterprise Low-Code Marketing Asset Pack Validator & Packager.

Zero-dependency Python 3 utility that:
1. Enforces the strict combined budget cap (len(agents) + len(skills) <= 3).
2. Validates Gemini Enterprise SKILL.md YAML frontmatter, description length
   (<= 1024 chars), progressive-disclosure reference links, and guardrails.
3. Validates Agent Designer blueprints (agent_blueprint.json + AGENT.md),
   attached skill resolution, federated connector bindings, Imagen aspect
   ratios (1:1, 16:9, 9:16), and Veo video modes (text_to_video,
   image_to_video, first_to_last_frame).
4. Builds deterministic, upload-ready Gemini Enterprise skill .zip archives
   with top-level '<skill-name>/' root folder structure and emits
   marketing_pack_manifest.json.
"""

import argparse
import hashlib
import json
import os
import re
import sys
import zipfile
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_CATALOG_DIR = os.path.join(REPO_ROOT, "catalog", "marketing")
DEFAULT_OUTPUT_DIR = os.path.join(REPO_ROOT, "dist", "marketing")

MAX_CATALOG_ITEMS = 3
MAX_SKILL_DESCRIPTION_LEN = 1024
DETERMINISTIC_ZIP_DATE = (2026, 1, 1, 0, 0, 0)

KEBAB_CASE_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

ALLOWED_PLATFORM_TOOLS = {
    "image_generation_imagen",
    "video_generation_veo",
    "enterprise_search",
}
ALLOWED_FEDERATED_CONNECTORS = {
    "google_drive",
    "google_mail",
    "google_calendar",
    "google_chat",
    "jira",
    "confluence",
    "slack",
    "people_directory",
}
REQUIRED_IMAGEN_RATIOS = {"1:1", "16:9", "9:16"}
REQUIRED_VEO_MODES = {"text_to_video", "image_to_video", "first_to_last_frame"}
REQUIRED_AGENT_MD_HEADINGS = [
    "## Agent Designer Configuration",
    "## System Instructions",
    "## Guardrails",
    "## Starter Prompts",
]


def parse_skill_frontmatter(content: str) -> Tuple[Optional[Dict[str, str]], str, List[str]]:
    """Parse minimal YAML frontmatter from SKILL.md using Python stdlib."""
    errors: List[str] = []
    if not content.startswith("---\n"):
        return None, content, ["SKILL.md must start with YAML frontmatter delimiter '---'"]

    end_idx = content.find("\n---\n", 4)
    if end_idx == -1:
        return None, content, ["SKILL.md is missing closing YAML frontmatter delimiter '---'"]

    raw_fm = content[4:end_idx]
    body = content[end_idx + 5 :]
    meta: Dict[str, str] = {}

    current_key: Optional[str] = None
    for line in raw_fm.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not line.startswith((" ", "\t")) and ":" in line:
            key, val = line.split(":", 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            meta[key] = val
            current_key = key
        elif current_key is not None:
            meta[current_key] = (meta[current_key] + " " + stripped).strip()
        else:
            errors.append(f"Malformed YAML frontmatter line: '{line}'")

    return meta, body, errors


def _validate_relative_links(md_path: str, md_content: str) -> List[str]:
    """Verify all relative file links inside a Markdown document resolve on disk."""
    errors: List[str] = []
    base_dir = os.path.dirname(md_path)
    for text, target in MD_LINK_RE.findall(md_content):
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        clean_target = target.split("#", 1)[0].strip()
        if not clean_target:
            continue
        resolved = os.path.normpath(os.path.join(base_dir, clean_target))
        if not os.path.exists(resolved):
            errors.append(
                f"Broken relative reference [{text}]({target}) in {os.path.basename(md_path)} -> missing '{resolved}'"
            )
    return errors


def _list_subdirs(parent_dir: str) -> List[str]:
    """Return sorted immediate directory names inside parent_dir."""
    if not os.path.isdir(parent_dir):
        return []
    return sorted(
        entry
        for entry in os.listdir(parent_dir)
        if not entry.startswith(".") and os.path.isdir(os.path.join(parent_dir, entry))
    )


def validate_skill_dir(skill_dir: str, expected_id: str) -> Tuple[Dict[str, Any], List[str]]:
    """Validate a single Gemini Enterprise skill folder."""
    errors: List[str] = []
    skill_md_path = os.path.join(skill_dir, "SKILL.md")
    info: Dict[str, Any] = {
        "id": expected_id,
        "path": skill_dir,
        "name": None,
        "description": None,
        "references": [],
    }

    if not KEBAB_CASE_RE.match(expected_id):
        errors.append(f"Skill directory '{expected_id}' must use lowercase kebab-case")

    if not os.path.isfile(skill_md_path):
        errors.append(f"Skill '{expected_id}' is missing mandatory SKILL.md")
        return info, errors

    with open(skill_md_path, "r", encoding="utf-8") as f:
        content = f.read()

    fm, body, fm_errors = parse_skill_frontmatter(content)
    errors.extend(f"Skill '{expected_id}': {err}" for err in fm_errors)

    if fm is not None:
        name = fm.get("name", "").strip()
        description = fm.get("description", "").strip()
        info["name"] = name
        info["description"] = description

        if not name:
            errors.append(f"Skill '{expected_id}': SKILL.md frontmatter missing 'name'")
        elif name != expected_id:
            errors.append(
                f"Skill '{expected_id}': SKILL.md frontmatter name '{name}' must match folder '{expected_id}'"
            )

        if not description:
            errors.append(f"Skill '{expected_id}': SKILL.md frontmatter missing 'description'")
        elif len(description) > MAX_SKILL_DESCRIPTION_LEN:
            errors.append(
                f"Skill '{expected_id}': description length ({len(description)}) exceeds {MAX_SKILL_DESCRIPTION_LEN} chars"
            )

    if len(body.strip()) < 50:
        errors.append(f"Skill '{expected_id}': SKILL.md instruction body is empty or too short")

    errors.extend(
        f"Skill '{expected_id}': {err}" for err in _validate_relative_links(skill_md_path, body)
    )

    refs_dir = os.path.join(skill_dir, "references")
    if os.path.isdir(refs_dir):
        ref_files = sorted(
            entry
            for entry in os.listdir(refs_dir)
            if not entry.startswith(".") and os.path.isfile(os.path.join(refs_dir, entry))
        )
        info["references"] = [f"references/{r}" for r in ref_files]

    return info, errors


def validate_agent_dir(
    agent_dir: str, expected_id: str, known_skill_ids: set
) -> Tuple[Dict[str, Any], List[str]]:
    """Validate a single Gemini Enterprise low-code Agent Designer folder."""
    errors: List[str] = []
    blueprint_path = os.path.join(agent_dir, "agent_blueprint.json")
    agent_md_path = os.path.join(agent_dir, "AGENT.md")
    info: Dict[str, Any] = {
        "id": expected_id,
        "path": agent_dir,
        "display_name": None,
        "builder_surface": None,
        "attached_skills": [],
        "platform_tools": [],
        "federated_connectors": [],
    }

    if not KEBAB_CASE_RE.match(expected_id):
        errors.append(f"Agent directory '{expected_id}' must use lowercase kebab-case")

    if not os.path.isfile(blueprint_path):
        errors.append(f"Agent '{expected_id}' is missing mandatory agent_blueprint.json")
    else:
        try:
            with open(blueprint_path, "r", encoding="utf-8") as f:
                bp = json.load(f)
        except ValueError as exc:
            bp = None
            errors.append(f"Agent '{expected_id}': invalid JSON in agent_blueprint.json ({exc})")

        if isinstance(bp, dict):
            bp_id = bp.get("id")
            if bp_id != expected_id:
                errors.append(
                    f"Agent '{expected_id}': blueprint id '{bp_id}' must match folder '{expected_id}'"
                )

            display_name = bp.get("display_name", "").strip()
            if not display_name:
                errors.append(f"Agent '{expected_id}': missing non-empty 'display_name'")
            info["display_name"] = display_name

            surface = bp.get("builder_surface", "")
            if surface != "GEMINI_ENTERPRISE_AGENT_DESIGNER":
                errors.append(
                    f"Agent '{expected_id}': builder_surface must be 'GEMINI_ENTERPRISE_AGENT_DESIGNER'"
                )
            info["builder_surface"] = surface

            attached_skills = bp.get("attached_skills", [])
            if not isinstance(attached_skills, list):
                errors.append(f"Agent '{expected_id}': 'attached_skills' must be a list")
            else:
                info["attached_skills"] = attached_skills
                for sk in attached_skills:
                    if sk not in known_skill_ids:
                        errors.append(
                            f"Agent '{expected_id}': attached skill '{sk}' not found in catalog skills {sorted(known_skill_ids)}"
                        )

            tools = bp.get("platform_tools", [])
            if not isinstance(tools, list) or not tools:
                errors.append(f"Agent '{expected_id}': 'platform_tools' must be a non-empty list")
            else:
                info["platform_tools"] = tools
                unknown_tools = set(tools) - ALLOWED_PLATFORM_TOOLS
                if unknown_tools:
                    errors.append(
                        f"Agent '{expected_id}': unsupported platform_tools {sorted(unknown_tools)}"
                    )

            connectors = bp.get("federated_connectors", [])
            if not isinstance(connectors, list) or not connectors:
                errors.append(
                    f"Agent '{expected_id}': 'federated_connectors' must be a non-empty list"
                )
            else:
                info["federated_connectors"] = connectors
                unknown_conns = set(connectors) - ALLOWED_FEDERATED_CONNECTORS
                if unknown_conns:
                    errors.append(
                        f"Agent '{expected_id}': unsupported federated_connectors {sorted(unknown_conns)}"
                    )

            if "supported_aspect_ratios" in bp:
                ratios = bp.get("supported_aspect_ratios")
                if not isinstance(ratios, list) or not REQUIRED_IMAGEN_RATIOS.issubset(set(ratios)):
                    errors.append(
                        f"Agent '{expected_id}': supported_aspect_ratios must include {sorted(REQUIRED_IMAGEN_RATIOS)}"
                    )
                info["supported_aspect_ratios"] = ratios

            if "supported_video_modes" in bp:
                modes = bp.get("supported_video_modes")
                if not isinstance(modes, list) or not REQUIRED_VEO_MODES.issubset(set(modes)):
                    errors.append(
                        f"Agent '{expected_id}': supported_video_modes must include {sorted(REQUIRED_VEO_MODES)}"
                    )
                info["supported_video_modes"] = modes

            starters = bp.get("starter_prompts", [])
            if not isinstance(starters, list) or len(starters) == 0:
                errors.append(
                    f"Agent '{expected_id}': 'starter_prompts' must contain at least 1 starter card"
                )
            else:
                for idx, card in enumerate(starters):
                    if not isinstance(card, dict) or not card.get("title") or not card.get("prompt"):
                        errors.append(
                            f"Agent '{expected_id}': starter_prompts[{idx}] must include 'title' and 'prompt'"
                        )

    if not os.path.isfile(agent_md_path):
        errors.append(f"Agent '{expected_id}' is missing mandatory AGENT.md")
    else:
        with open(agent_md_path, "r", encoding="utf-8") as f:
            md_content = f.read()
        for heading in REQUIRED_AGENT_MD_HEADINGS:
            if heading not in md_content:
                errors.append(
                    f"Agent '{expected_id}': AGENT.md missing required section '{heading}'"
                )
        errors.extend(
            f"Agent '{expected_id}': {err}"
            for err in _validate_relative_links(agent_md_path, md_content)
        )

    return info, errors


def validate_catalog(
    catalog_dir: str = DEFAULT_CATALOG_DIR, max_items: int = MAX_CATALOG_ITEMS
) -> Dict[str, Any]:
    """Validate the marketing catalog directory and enforce the <= max_items budget."""
    errors: List[str] = []
    if not os.path.isdir(catalog_dir):
        return {
            "valid": False,
            "catalog_dir": catalog_dir,
            "total_items": 0,
            "max_items": max_items,
            "skills": [],
            "agents": [],
            "errors": [f"Catalog directory not found: {catalog_dir}"],
        }

    skills_root = os.path.join(catalog_dir, "skills")
    agents_root = os.path.join(catalog_dir, "agents")

    skill_ids = _list_subdirs(skills_root)
    agent_ids = _list_subdirs(agents_root)
    total_items = len(skill_ids) + len(agent_ids)

    if total_items == 0:
        errors.append("Catalog must define at least 1 low-code agent or skill (found 0)")
    if total_items > max_items:
        errors.append(
            f"Catalog budget exceeded: found {total_items} items "
            f"({len(agent_ids)} agents + {len(skill_ids)} skills), maximum allowed is {max_items}"
        )

    known_skill_ids = set(skill_ids)
    skills_report: List[Dict[str, Any]] = []
    for sid in skill_ids:
        s_info, s_errs = validate_skill_dir(os.path.join(skills_root, sid), sid)
        skills_report.append(s_info)
        errors.extend(s_errs)

    agents_report: List[Dict[str, Any]] = []
    has_imagen = False
    has_veo = False
    for aid in agent_ids:
        a_info, a_errs = validate_agent_dir(
            os.path.join(agents_root, aid), aid, known_skill_ids
        )
        agents_report.append(a_info)
        errors.extend(a_errs)
        tools = set(a_info.get("platform_tools", []))
        if "image_generation_imagen" in tools and REQUIRED_IMAGEN_RATIOS.issubset(
            set(a_info.get("supported_aspect_ratios", []))
        ):
            has_imagen = True
        if "video_generation_veo" in tools and REQUIRED_VEO_MODES.issubset(
            set(a_info.get("supported_video_modes", []))
        ):
            has_veo = True

    if agent_ids:
        if not has_imagen:
            errors.append(
                "Catalog must include an Imagen low-code agent covering 1:1, 16:9, and 9:16 aspect ratios"
            )
        if not has_veo:
            errors.append(
                "Catalog must include a Veo low-code agent covering text_to_video, image_to_video, and first_to_last_frame"
            )

    return {
        "valid": len(errors) == 0,
        "catalog_dir": catalog_dir,
        "total_items": total_items,
        "max_items": max_items,
        "skills": skills_report,
        "agents": agents_report,
        "errors": errors,
    }


def _create_deterministic_skill_zip(skill_dir: str, skill_id: str, zip_path: str) -> Tuple[str, List[str]]:
    """
    Create a deterministic Gemini Enterprise skill .zip archive with '<skill_id>/' at the ZIP root.
    Returns (sha256_hex, archived_entries).
    """
    entries: List[Tuple[str, str]] = []
    for root, dirs, files in os.walk(skill_dir):
        dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d != "__pycache__")
        for fname in sorted(files):
            if fname.startswith(".") or fname.endswith((".pyc", ".pyo")):
                continue
            abs_file = os.path.join(root, fname)
            rel_inside_skill = os.path.relpath(abs_file, skill_dir).replace(os.sep, "/")
            arcname = f"{skill_id}/{rel_inside_skill}"
            entries.append((arcname, abs_file))

    os.makedirs(os.path.dirname(zip_path), exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # Explicit root directory entry '<skill_id>/'
        dir_info = zipfile.ZipInfo(f"{skill_id}/", date_time=DETERMINISTIC_ZIP_DATE)
        dir_info.external_attr = 0o40755 << 16
        zf.writestr(dir_info, b"")

        for arcname, abs_file in entries:
            with open(abs_file, "rb") as f:
                data = f.read()
            zinfo = zipfile.ZipInfo(arcname, date_time=DETERMINISTIC_ZIP_DATE)
            zinfo.compress_type = zipfile.ZIP_DEFLATED
            zinfo.external_attr = 0o100644 << 16
            zf.writestr(zinfo, data)

    sha256 = hashlib.sha256()
    with open(zip_path, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            sha256.update(chunk)

    return sha256.hexdigest(), [arc for arc, _ in entries]


def build_packages(
    catalog_dir: str = DEFAULT_CATALOG_DIR,
    output_dir: str = DEFAULT_OUTPUT_DIR,
    max_items: int = MAX_CATALOG_ITEMS,
) -> Dict[str, Any]:
    """Validate catalog and emit upload-ready .zip skill bundles + manifest JSON."""
    report = validate_catalog(catalog_dir=catalog_dir, max_items=max_items)
    if not report["valid"]:
        raise ValueError(
            "Cannot package invalid marketing catalog:\n  - " + "\n  - ".join(report["errors"])
        )

    os.makedirs(output_dir, exist_ok=True)
    packaged_skills: List[Dict[str, Any]] = []

    for skill in report["skills"]:
        sid = skill["id"]
        zip_filename = f"{sid}.zip"
        zip_path = os.path.join(output_dir, zip_filename)
        digest, archived_files = _create_deterministic_skill_zip(skill["path"], sid, zip_path)
        packaged_skills.append(
            {
                "id": sid,
                "name": skill["name"],
                "description": skill["description"],
                "zip_file": zip_filename,
                "zip_path": zip_path,
                "sha256": digest,
                "entries": archived_files,
                "ui_import_step": "Gemini Enterprise Web App > Skills > + Add > Upload skill package (.zip)",
            }
        )

    packaged_agents: List[Dict[str, Any]] = []
    for agent in report["agents"]:
        aid = agent["id"]
        packaged_agents.append(
            {
                "id": aid,
                "display_name": agent["display_name"],
                "builder_surface": agent["builder_surface"],
                "attached_skills": agent["attached_skills"],
                "platform_tools": agent["platform_tools"],
                "federated_connectors": agent["federated_connectors"],
                "blueprint_file": os.path.relpath(
                    os.path.join(agent["path"], "agent_blueprint.json"), catalog_dir
                ).replace(os.sep, "/"),
                "instructions_file": os.path.relpath(
                    os.path.join(agent["path"], "AGENT.md"), catalog_dir
                ).replace(os.sep, "/"),
                "ui_setup_step": "Gemini Enterprise Web App > Agent Designer > + New Agent",
            }
        )

    manifest = {
        "pack_name": "prism-gemini-enterprise-marketing-pack",
        "schema_version": "1.0",
        "total_items": report["total_items"],
        "max_items": report["max_items"],
        "skills": packaged_skills,
        "agents": packaged_agents,
    }

    manifest_path = os.path.join(output_dir, "marketing_pack_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")

    manifest["manifest_path"] = manifest_path
    return manifest


def _print_check_summary(report: Dict[str, Any]) -> None:
    status_str = "PASS" if report["valid"] else "FAIL"
    print("=" * 78)
    print(" PRISM — GEMINI ENTERPRISE LOW-CODE MARKETING CATALOG AUDIT")
    print("=" * 78)
    print(f" Status       : {status_str}")
    print(
        f" Budget Usage : {report['total_items']} / {report['max_items']} max items "
        f"({len(report['agents'])} low-code agents, {len(report['skills'])} shared skills)"
    )
    print("-" * 78)
    for skill in report["skills"]:
        refs_count = len(skill.get("references", []))
        print(f" [SKILL] {skill['id']} ({refs_count} reference docs)")
    for agent in report["agents"]:
        tools = ", ".join(agent.get("platform_tools", []))
        print(f" [AGENT] {agent['id']} — {agent.get('display_name') or 'Unnamed'} [{tools}]")
    if report["errors"]:
        print("-" * 78)
        print(" Validation Errors:")
        for err in report["errors"]:
            print(f"   [!] {err}")
    print("=" * 78)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate and package Gemini Enterprise low-code marketing agents and skills."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate catalog structure, schemas, and <= 3 item cap.",
    )
    parser.add_argument(
        "--build",
        action="store_true",
        help="Validate catalog and build deterministic .zip skill bundles + manifest.",
    )
    parser.add_argument(
        "--catalog-dir",
        default=DEFAULT_CATALOG_DIR,
        help="Path to marketing catalog directory (default: catalog/marketing).",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help="Output directory for .zip packages and manifest (default: dist/marketing).",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=MAX_CATALOG_ITEMS,
        help=f"Maximum allowed combined agents + skills (default: {MAX_CATALOG_ITEMS}).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON output.",
    )

    args = parser.parse_args(argv)
    if not args.check and not args.build:
        args.check = True

    if args.build:
        try:
            manifest = build_packages(
                catalog_dir=args.catalog_dir,
                output_dir=args.output_dir,
                max_items=args.max_items,
            )
        except ValueError as exc:
            if args.json:
                report = validate_catalog(catalog_dir=args.catalog_dir, max_items=args.max_items)
                print(json.dumps(report, indent=2))
            else:
                print(str(exc), file=sys.stderr)
            return 1

        if args.json:
            print(json.dumps(manifest, indent=2))
        else:
            print("=" * 78)
            print(" PRISM — MARKETING ASSET PACK BUILT SUCCESSFULLY")
            print("=" * 78)
            print(f" Total Items : {manifest['total_items']} / {manifest['max_items']} max")
            for sk in manifest["skills"]:
                print(f" Skill ZIP   : {sk['zip_path']} (sha256: {sk['sha256'][:12]}...)")
            for ag in manifest["agents"]:
                print(f" Agent Spec  : {ag['id']} -> {ag['instructions_file']}")
            print(f" Manifest    : {manifest['manifest_path']}")
            print("=" * 78)
        return 0

    report = validate_catalog(catalog_dir=args.catalog_dir, max_items=args.max_items)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        _print_check_summary(report)
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
