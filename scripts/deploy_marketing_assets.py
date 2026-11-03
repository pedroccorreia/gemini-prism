#!/usr/bin/env python3
"""
Gemini Enterprise Low-Code Marketing Asset Pack API Deployer.

Zero-dependency Python 3 deployment tool that publishes the validated <= 3 item
marketing catalog (1 shared Skill + 2 low-code Agent Designer workflows) into a
live Gemini Enterprise (Discovery Engine v1alpha) assistant:

1. Validates catalog & builds deterministic 'dist/marketing/brand-kit-governance.zip'.
2. Auto-discovers target Search Engine, federated DataStores, and DataConnectors
   (Google Drive, Atlassian Confluence, Slack) on the target GCP project.
3. Upserts the shared 'Brand Kit & Governance' skillAgentDefinition, uploads the
   complete .zip bundle (SKILL.md + references/*.md) via Scotty raw upload, and
   publishes an active ENABLED revision shared with ALL_USERS (or custom scope).
4. Upserts & publishes the 2 low-code workflowAgentDefinitions ('Visual & Copy
   Campaign Agent' and 'Video & Social Motion Agent') wired to the shared skill,
   live federated connectors, and Custom Landing Page starter prompts.
5. Verifies live resource states via GET readback.
"""

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import scripts.package_marketing_assets as packager

API_BASE = "https://discoveryengine.googleapis.com/v1alpha"
UPLOAD_BASE = "https://discoveryengine.googleapis.com/upload/v1alpha"
DEFAULT_MODEL = "gemini-2.5-flash"


def get_access_token() -> str:
    """Retrieve an OAuth 2.0 Bearer token from active gcloud / ADC credentials."""
    for cmd in (
        ["gcloud", "auth", "print-access-token"],
        ["gcloud", "auth", "application-default", "print-access-token"],
    ):
        try:
            out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True).strip()
            if out:
                return out
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue
    raise RuntimeError(
        "Unable to obtain GCP access token. Run 'gcloud auth application-default login'."
    )


def api_request(
    method: str,
    url: str,
    token: str,
    quota_project: str,
    payload: Optional[Dict[str, Any]] = None,
    raw_bytes: Optional[bytes] = None,
    extra_headers: Optional[Dict[str, str]] = None,
    timeout: int = 60,
) -> Dict[str, Any]:
    """Execute an authenticated HTTP request against Discovery Engine v1alpha."""
    headers = {
        "Authorization": f"Bearer {token}",
        "x-goog-user-project": quota_project,
    }
    data: Optional[bytes] = None
    if raw_bytes is not None:
        data = raw_bytes
    elif payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")

    if extra_headers:
        headers.update(extra_headers)

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body.strip() else {}
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} on {method} {url}: {err_body}") from exc


def discover_environment(
    project: str,
    location: str,
    token: str,
    engine_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Discover engine metadata, federated data stores, and active data connectors."""
    engines_url = (
        f"{API_BASE}/projects/{project}/locations/{location}"
        f"/collections/default_collection/engines"
    )
    engines_resp = api_request("GET", engines_url, token, project)
    engines = engines_resp.get("engines", [])
    if not engines:
        raise RuntimeError(
            f"No Gemini Enterprise engines found in project '{project}' ({location})."
        )

    selected_engine = None
    if engine_id:
        for eng in engines:
            name = eng.get("name", "")
            if name.endswith(f"/engines/{engine_id}") or name == engine_id:
                selected_engine = eng
                break
        if not selected_engine:
            available = [e.get("name", "").split("/")[-1] for e in engines]
            raise RuntimeError(
                f"Engine '{engine_id}' not found in '{project}'. Available: {available}"
            )
    else:
        selected_engine = engines[0]

    engine_name = selected_engine["name"]
    # Format: projects/{project_number}/locations/{location}/collections/default_collection/engines/{engine_id}
    parts = engine_name.split("/")
    project_number = parts[1]
    resolved_engine_id = parts[-1]

    # Map relevant federated data stores attached to the engine
    ds_ids = selected_engine.get("dataStoreIds", [])
    preferred_prefixes = ("drive-collection", "google-drive", "confluence", "slack", "hubspot", "jira")
    matched_ds_specs = []
    for ds_id in ds_ids:
        if any(ds_id.startswith(pref) for pref in preferred_prefixes):
            # Prefer primary document/page/message/drive stores (max 6 to stay well under limit 10)
            if any(
                ds_id.endswith(suffix)
                for suffix in ("_google_drive", "_page", "_space", "_message", "_file")
            ):
                matched_ds_specs.append(
                    {
                        "dataStore": (
                            f"projects/{project_number}/locations/{location}"
                            f"/collections/default_collection/dataStores/{ds_id}"
                        )
                    }
                )
    matched_ds_specs = matched_ds_specs[:8]

    # Discover active data connectors across collections
    cols_url = f"{API_BASE}/projects/{project_number}/locations/{location}/collections"
    cols_resp = api_request("GET", cols_url, token, project)
    connectors_by_source: Dict[str, str] = {}
    for col in cols_resp.get("collections", []):
        col_name = col.get("name", "")
        if col_name.endswith("/default_collection"):
            continue
        try:
            dc = api_request("GET", f"{API_BASE}/{col_name}/dataConnector", token, project)
            ds_source = dc.get("dataSource", "")
            dc_name = dc.get("name", "")
            if ds_source and dc_name:
                connectors_by_source[ds_source] = dc_name
        except RuntimeError:
            continue

    # Auto-detect enabled Gemini text models from default_search_widget_config if available
    enabled_models: List[str] = []
    try:
        wc = api_request(
            "GET",
            f"{API_BASE}/{engine_name}/widgetConfigs/default_search_widget_config",
            token,
            project,
        )
        model_cfgs = wc.get("customerProvidedConfig", {}).get("modelConfigs") or wc.get(
            "modelConfigs", {}
        )
        for m_id, status_val in model_cfgs.items():
            if status_val == "MODEL_ENABLED" and "image" not in m_id:
                enabled_models.append(m_id)
    except RuntimeError:
        pass

    return {
        "project_id": project,
        "project_number": project_number,
        "location": location,
        "engine_id": resolved_engine_id,
        "engine_name": engine_name,
        "data_store_specs": matched_ds_specs,
        "connectors_by_source": connectors_by_source,
        "enabled_models": enabled_models,
    }


def list_existing_agents(assistant_name: str, token: str, quota_project: str) -> List[Dict[str, Any]]:
    """List all agents currently registered under the target assistant."""
    resp = api_request("GET", f"{API_BASE}/{assistant_name}/agents", token, quota_project)
    return resp.get("agents", [])


def skill_id_to_display_name(skill_id: str) -> str:
    """Convert a kebab-case skill ID into a valid Gemini Enterprise Skill displayName (<=64 chars, letters/numbers/spaces only)."""
    cleaned = " ".join(part.capitalize() for part in skill_id.strip().split("-") if part)
    return cleaned[:64]


def _publish_and_enable_agent(
    agent_name: str,
    sharing_scope: str,
    token: str,
    quota_project: str,
) -> Tuple[Dict[str, Any], Optional[str]]:
    """Publish active revision and transition PRIVATE -> DISABLED -> ENABLED when shared."""
    publish_note: Optional[str] = None
    try:
        api_request(
            "POST",
            f"{API_BASE}/{agent_name}:publish",
            token,
            quota_project,
            payload={},
        )
    except RuntimeError as exc:
        publish_note = str(exc)

    current = api_request("GET", f"{API_BASE}/{agent_name}", token, quota_project)
    if sharing_scope != "PRIVATE":
        if current.get("state") == "PRIVATE":
            try:
                current = api_request(
                    "POST",
                    f"{API_BASE}/{agent_name}:requestAgentReview",
                    token,
                    quota_project,
                )
            except RuntimeError as exc:
                publish_note = publish_note or str(exc)
        if current.get("state") in ("DISABLED", "SUSPENDED"):
            try:
                current = api_request(
                    "POST",
                    f"{API_BASE}/{agent_name}:enableAgent",
                    token,
                    quota_project,
                )
            except RuntimeError as exc:
                publish_note = publish_note or str(exc)
        if current.get("sharingConfig", {}).get("scope") != sharing_scope:
            mask = urllib.parse.urlencode({"updateMask": "sharingConfig"})
            try:
                current = api_request(
                    "PATCH",
                    f"{API_BASE}/{agent_name}?{mask}",
                    token,
                    quota_project,
                    payload={
                        "name": agent_name,
                        "sharingConfig": {"scope": sharing_scope},
                    },
                )
            except RuntimeError as exc:
                publish_note = publish_note or str(exc)
        current = api_request("GET", f"{API_BASE}/{agent_name}", token, quota_project)

    return current, publish_note


def deploy_shared_skill(
    assistant_name: str,
    skill_manifest: Dict[str, Any],
    skill_md_path: str,
    sharing_scope: str,
    existing_agents: List[Dict[str, Any]],
    token: str,
    quota_project: str,
) -> Dict[str, Any]:
    """Create or update the shared Brand Kit Governance skill, upload .zip, and publish."""
    display_name = skill_id_to_display_name(skill_manifest["name"])
    candidate_names = {display_name, skill_manifest["name"], skill_manifest["id"]}
    with open(skill_md_path, "r", encoding="utf-8") as f:
        raw_md = f.read()
    _, instruction_body, _ = packager.parse_skill_frontmatter(raw_md)

    existing = next(
        (
            a
            for a in existing_agents
            if a.get("displayName") in candidate_names and "skillAgentDefinition" in a
        ),
        None,
    )

    agent_payload = {
        "displayName": display_name,
        "description": skill_manifest["description"],
        "sharingConfig": {"scope": sharing_scope},
        "skillAgentDefinition": {
            "instruction": instruction_body.strip(),
        },
    }

    if existing:
        agent_name = existing["name"]
        action = "UPDATED"
    else:
        created = api_request(
            "POST",
            f"{API_BASE}/{assistant_name}/agents",
            token,
            quota_project,
            payload=agent_payload,
        )
        agent_name = created["name"]
        action = "CREATED"

    # Upload full skill .zip package (SKILL.md + references/*.md) via Scotty raw upload
    with open(skill_manifest["zip_path"], "rb") as zf:
        zip_bytes = zf.read()

    upload_url = f"{UPLOAD_BASE}/{agent_name}/files:upload"
    upload_resp = api_request(
        "POST",
        upload_url,
        token,
        quota_project,
        raw_bytes=zip_bytes,
        extra_headers={
            "X-Goog-Upload-Protocol": "raw",
            "X-Goog-Upload-File-Name": os.path.basename(skill_manifest["zip_path"]),
            "Content-Type": "application/zip",
        },
        timeout=90,
    )

    # Restore human-friendly displayName & sharingConfig after ZIP extraction
    mask = urllib.parse.urlencode({"updateMask": "displayName,description,sharingConfig"})
    api_request(
        "PATCH",
        f"{API_BASE}/{agent_name}?{mask}",
        token,
        quota_project,
        payload={
            "name": agent_name,
            "displayName": display_name,
            "description": skill_manifest["description"],
            "sharingConfig": {"scope": sharing_scope},
        },
    )

    final_skill, publish_note = _publish_and_enable_agent(
        agent_name=agent_name,
        sharing_scope=sharing_scope,
        token=token,
        quota_project=quota_project,
    )

    return {
        "id": skill_manifest["id"],
        "display_name": final_skill.get("displayName", display_name),
        "action": action,
        "resource_name": agent_name,
        "state": final_skill.get("state"),
        "sharing_scope": final_skill.get("sharingConfig", {}).get("scope"),
        "active_revision": final_skill.get("activeRevision"),
        "subfiles": final_skill.get("skillAgentDefinition", {}).get("subfiles", []),
        "upload_response": upload_resp,
        "publish_note": publish_note,
    }


def _extract_system_instruction(agent_md_path: str) -> str:
    """Extract the fenced markdown block under '## System Instructions' from AGENT.md."""
    with open(agent_md_path, "r", encoding="utf-8") as f:
        text = f.read()
    marker = "## System Instructions"
    idx = text.find(marker)
    if idx == -1:
        return text.strip()
    sub = text[idx:]
    fence_start = sub.find("```markdown\n")
    if fence_start == -1:
        return sub.strip()
    body_start = fence_start + len("```markdown\n")
    fence_end = sub.find("\n```", body_start)
    if fence_end == -1:
        return sub[body_start:].strip()
    return sub[body_start:fence_end].strip()


def build_workflow_agent_payload(
    blueprint: Dict[str, Any],
    system_instruction: str,
    skill_resource_name: str,
    env_info: Dict[str, Any],
    model: str,
    sharing_scope: str,
) -> Dict[str, Any]:
    """Construct a valid Discovery Engine v1alpha workflowAgentDefinition payload."""
    agent_id = blueprint["id"]
    display_name = blueprint["display_name"]
    description = blueprint["description"]

    # Map requested federated connectors to live connectorToolSelections
    connector_selections = []
    live_conns = env_info.get("connectors_by_source", {})
    for conn_key in blueprint.get("federated_connectors", []):
        if conn_key in live_conns:
            connector_selections.append(
                {
                    "dataConnector": {
                        "name": live_conns[conn_key],
                        "dataSource": conn_key,
                    }
                }
            )

    ds_specs = env_info.get("data_store_specs", [])
    starter_prompts = [{"text": card["prompt"]} for card in blueprint.get("starter_prompts", [])]

    if "video_generation_veo" in blueprint.get("platform_tools", []):
        step1_id = "brief_and_storyboard_planner"
        step1_title = "1. Federated Brief Grounding & 3-Beat Storyboard"
        step1_desc = (
            "Grounds in Google Drive, Confluence, and Slack briefs + Brand Kit skill "
            "to assemble a scene-by-scene storyboard."
        )
        step1_instr = (
            "Load and follow the attached **Brand Kit & Governance** skill (`SKILL.md` and "
            "`references/veo_cinematography_guide.md`).\n"
            "1. Search connected Google Drive, Confluence, and Slack sources (plus Google Search "
            "when external market context helps) for campaign briefs, product launch docs, or reference visuals matching the user's request.\n"
            "2. If no live campaign brief overrides the visual palette, apply `references/brand_guidelines.template.md` and cite the active grounding source.\n"
            "3. Produce `grounding_summary` and `storyboard_markdown` (Scene #, 4-8s Beat, Veo Mode [`text_to_video` | `image_to_video` | `first_to_last_frame`], Camera Movement, Brand Lighting, and Voiceover/Super)."
        )
        step1_schema = {
            "properties": {
                "grounding_summary": {
                    "type": "STRING",
                    "description": "Cited Drive/Confluence/Slack brief or bundled Brand Kit fallback profile",
                    "additionalProperties": {"display_order": 0},
                },
                "storyboard_markdown": {
                    "type": "STRING",
                    "description": "3-beat storyboard table with Veo modes, single camera moves, and lighting cues",
                    "additionalProperties": {"display_order": 1},
                },
            },
            "required": ["grounding_summary", "storyboard_markdown"],
        }

        step2_id = "veo_motion_and_social_pack_director"
        step2_title = "2. Veo Motion Prompts, Keyframes & Social Publishing Pack"
        step2_desc = (
            "Produces production-ready Veo prompts (text-to-video, image-to-video, "
            "first-to-last frame) paired with timed supers, captions, and social copy."
        )
        step2_instr = (
            f"{system_instruction}\n\n"
            "Using the approved grounding context (`${brief_and_storyboard_planner.grounding_summary}`) "
            "and storyboard (`${brief_and_storyboard_planner.storyboard_markdown}`), deliver the complete "
            "Veo production package directly to the user in clean Markdown, including:\n"
            "- Production-ready 6-part **Veo** prompts (`text_to_video`, `image_to_video`, and/or `first_to_last_frame` interpolation cues)\n"
            "- Timed on-screen supers & closed-caption/voiceover script\n"
            "- Channel post copy, hook, CTA, and recommended cover frame."
        )
        step2_schema = {
            "properties": {
                "veo_production_pack_markdown": {
                    "type": "STRING",
                    "description": "Complete Veo clip prompts, transition keyframes, timed supers, captions, and social CTA copy",
                    "additionalProperties": {"display_order": 0},
                }
            },
            "required": ["veo_production_pack_markdown"],
        }
    else:
        step1_id = "brief_and_brand_grounding"
        step1_title = "1. Federated Brief Discovery & Brand Kit Alignment"
        step1_desc = (
            "Searches Google Drive, Confluence, and Slack for campaign briefs and "
            "loads Brand Kit aspect-ratio & palette rules."
        )
        step1_instr = (
            "Load and follow the attached **Brand Kit & Governance** skill (`SKILL.md` and "
            "`references/imagen_prompt_matrix.md`).\n"
            "1. Search connected Google Drive, Confluence, and Slack sources (plus Google Search "
            "if helpful) for launch briefs, messaging docs, or brand guidelines relevant to the user's request.\n"
            "2. Fall back cleanly to `references/brand_guidelines.template.md` when no campaign-specific override is found.\n"
            "3. Output `grounding_summary` and `creative_plan` specifying target channels, aspect ratios (`1:1`, `16:9`, `9:16`), brand lighting/surface descriptors, and copy safe-zone allocations."
        )
        step1_schema = {
            "properties": {
                "grounding_summary": {
                    "type": "STRING",
                    "description": "Cited Drive/Confluence/Slack brief or bundled Brand Kit fallback profile",
                    "additionalProperties": {"display_order": 0},
                },
                "creative_plan": {
                    "type": "STRING",
                    "description": "Channel aspect-ratio matrix (1:1, 16:9, 9:16), palette lighting tokens, and typography safe zones",
                    "additionalProperties": {"display_order": 1},
                },
            },
            "required": ["grounding_summary", "creative_plan"],
        }

        step2_id = "imagen_visual_and_copy_studio"
        step2_title = "2. Multi-Format Imagen Visuals & Channel Copy Pack"
        step2_desc = (
            "Synthesizes multi-format 1:1, 16:9, and 9:16 Imagen creative prompts/visuals "
            "with paired headlines, ad copy, CTAs, alt-text, and video seed handoff."
        )
        step2_instr = (
            f"{system_instruction}\n\n"
            "Using the grounding summary (`${brief_and_brand_grounding.grounding_summary}`) and "
            "creative plan (`${brief_and_brand_grounding.creative_plan}`), deliver the complete "
            "multi-format **Imagen** (`1:1`, `16:9`, `9:16`) visual & channel copy package in clean Markdown, including:\n"
            "- 6-part Imagen generation prompts with clean post-production safe zones\n"
            "- Paired Headline, Primary Ad/Social Copy, 2-4 word CTA, and Accessibility Alt-Text per format\n"
            "- Optional 2-line Seed Keyframe Handoff ready for the **Video & Social Motion Agent**."
        )
        step2_schema = {
            "properties": {
                "campaign_asset_pack_markdown": {
                    "type": "STRING",
                    "description": "Multi-format 1:1, 16:9, and 9:16 Imagen visual prompts/specs, channel copy, CTAs, alt-text, and motion handoff",
                    "additionalProperties": {"display_order": 0},
                }
            },
            "required": ["campaign_asset_pack_markdown"],
        }

    node1_agent: Dict[str, Any] = {
        "model": model,
        "instruction": step1_instr,
        "selectedTools": {"tools": [{"name": "googleSearch"}]},
        "skillAgentNames": [skill_resource_name],
        "outputDisplayEnabled": False,
    }
    if ds_specs:
        node1_agent["dataStoreSpecs"] = {"specs": ds_specs}
    if connector_selections:
        node1_agent["connectorToolSelections"] = connector_selections

    node2_agent: Dict[str, Any] = {
        "model": model,
        "instruction": step2_instr,
        "skillAgentNames": [skill_resource_name],
        "outputDisplayEnabled": True,
    }
    if ds_specs:
        node2_agent["dataStoreSpecs"] = {"specs": ds_specs}

    trigger_id = f"start_{agent_id.replace('-', '_')}"
    payload: Dict[str, Any] = {
        "displayName": display_name,
        "description": description,
        "sharingConfig": {"scope": sharing_scope},
        "starterPrompts": starter_prompts,
        "workflowAgentDefinition": {
            "triggerNodeId": trigger_id,
            "agentFlow": {
                "nodes": [
                    {
                        "id": trigger_id,
                        "displayName": "Start Marketing Request",
                        "description": "Interactive chat entry point for marketing asset requests.",
                        "metadata": {"position": {"x": 80, "y": 240}},
                        "nodeType": "CHAT_TRIGGER",
                        "chatTrigger": {},
                    },
                    {
                        "id": step1_id,
                        "displayName": step1_title,
                        "description": step1_desc,
                        "metadata": {"position": {"x": 460, "y": 240}},
                        "nodeType": "AGENT_NODE",
                        "agentNode": node1_agent,
                        "outputSchema": step1_schema,
                    },
                    {
                        "id": step2_id,
                        "displayName": step2_title,
                        "description": step2_desc,
                        "metadata": {"position": {"x": 860, "y": 240}},
                        "nodeType": "AGENT_NODE",
                        "agentNode": node2_agent,
                        "outputSchema": step2_schema,
                    },
                ],
                "edges": [
                    {"sourceNodeId": trigger_id, "targetNodeId": step1_id},
                    {"sourceNodeId": step1_id, "targetNodeId": step2_id},
                ],
            },
        },
    }
    if ds_specs:
        payload["dataStoreSpecs"] = {"specs": ds_specs}
    return payload


def deploy_workflow_agent(
    assistant_name: str,
    blueprint: Dict[str, Any],
    agent_md_path: str,
    skill_resource_name: str,
    env_info: Dict[str, Any],
    model: str,
    sharing_scope: str,
    existing_agents: List[Dict[str, Any]],
    token: str,
    quota_project: str,
) -> Dict[str, Any]:
    """Create or update a low-code workflowAgentDefinition and publish an active revision."""
    sys_instr = _extract_system_instruction(agent_md_path)
    payload = build_workflow_agent_payload(
        blueprint=blueprint,
        system_instruction=sys_instr,
        skill_resource_name=skill_resource_name,
        env_info=env_info,
        model=model,
        sharing_scope=sharing_scope,
    )

    display_name = blueprint["display_name"]
    existing = next(
        (
            a
            for a in existing_agents
            if a.get("displayName") == display_name and "workflowAgentDefinition" in a
        ),
        None,
    )

    if existing:
        agent_name = existing["name"]
        payload["name"] = agent_name
        mask = urllib.parse.urlencode(
            {
                "updateMask": (
                    "displayName,description,sharingConfig,starterPrompts,"
                    "dataStoreSpecs,workflowAgentDefinition"
                )
            }
        )
        api_request(
            "PATCH",
            f"{API_BASE}/{agent_name}?{mask}",
            token,
            quota_project,
            payload=payload,
        )
        action = "UPDATED"
    else:
        created = api_request(
            "POST",
            f"{API_BASE}/{assistant_name}/agents",
            token,
            quota_project,
            payload=payload,
        )
        agent_name = created["name"]
        action = "CREATED"

    # Publish active revision and transition PRIVATE -> DISABLED -> ENABLED for users
    final_agent, publish_error = _publish_and_enable_agent(
        agent_name=agent_name,
        sharing_scope=sharing_scope,
        token=token,
        quota_project=quota_project,
    )

    return {
        "id": blueprint["id"],
        "display_name": display_name,
        "action": action,
        "resource_name": agent_name,
        "state": final_agent.get("state"),
        "sharing_scope": final_agent.get("sharingConfig", {}).get("scope"),
        "active_revision": final_agent.get("activeRevision"),
        "attached_skill": skill_resource_name,
        "publish_note": publish_error,
    }


def deploy_pack(
    project: str,
    engine_id: Optional[str] = None,
    location: str = "global",
    assistant_id: str = "default_assistant",
    sharing_scope: str = "ALL_USERS",
    model: str = DEFAULT_MODEL,
    catalog_dir: str = packager.DEFAULT_CATALOG_DIR,
    output_dir: str = packager.DEFAULT_OUTPUT_DIR,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Validate, package, and deploy the 3-item marketing catalog to Gemini Enterprise."""
    manifest = packager.build_packages(catalog_dir=catalog_dir, output_dir=output_dir)
    token = get_access_token()
    env_info = discover_environment(
        project=project, location=location, token=token, engine_id=engine_id
    )
    enabled_models = env_info.get("enabled_models", [])
    if enabled_models and model not in enabled_models:
        for preferred in ("gemini-3.8-flash", "gemini-4-argon", "gemini-3.1-pro-preview", "gemini-2.5-pro"):
            if preferred in enabled_models:
                model = preferred
                break
    assistant_name = f"{env_info['engine_name']}/assistants/{assistant_id}"

    if dry_run:
        return {
            "mode": "DRY_RUN",
            "environment": env_info,
            "assistant": assistant_name,
            "sharing_scope": sharing_scope,
            "model": model,
            "manifest": manifest,
        }

    existing_agents = list_existing_agents(assistant_name, token, project)

    # 1. Deploy Shared Skill (1 of 3)
    skill_entry = manifest["skills"][0]
    skill_md_path = os.path.join(catalog_dir, "skills", skill_entry["id"], "SKILL.md")
    deployed_skill = deploy_shared_skill(
        assistant_name=assistant_name,
        skill_manifest=skill_entry,
        skill_md_path=skill_md_path,
        sharing_scope=sharing_scope,
        existing_agents=existing_agents,
        token=token,
        quota_project=project,
    )

    # 2. Deploy the 2 Specialized Low-Code Agents (2 & 3 of 3)
    deployed_agents = []
    for ag_entry in manifest["agents"]:
        bp_path = os.path.join(catalog_dir, ag_entry["blueprint_file"])
        md_path = os.path.join(catalog_dir, ag_entry["instructions_file"])
        with open(bp_path, "r", encoding="utf-8") as f:
            bp = json.load(f)
        res = deploy_workflow_agent(
            assistant_name=assistant_name,
            blueprint=bp,
            agent_md_path=md_path,
            skill_resource_name=deployed_skill["resource_name"],
            env_info=env_info,
            model=model,
            sharing_scope=sharing_scope,
            existing_agents=existing_agents,
            token=token,
            quota_project=project,
        )
        deployed_agents.append(res)

    return {
        "mode": "LIVE",
        "environment": env_info,
        "assistant": assistant_name,
        "total_deployed": 1 + len(deployed_agents),
        "skill": deployed_skill,
        "agents": deployed_agents,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Deploy the <= 3 item Low-Code Marketing Asset Pack to Gemini Enterprise."
    )
    parser.add_argument(
        "--project",
        required=True,
        help="Target GCP Project ID hosting the Gemini Enterprise engine.",
    )
    parser.add_argument(
        "--engine",
        default=None,
        help="Target Search Engine ID (auto-discovered if omitted).",
    )
    parser.add_argument(
        "--location",
        default="global",
        help="Discovery Engine location (default: global).",
    )
    parser.add_argument(
        "--assistant",
        default="default_assistant",
        help="Target Assistant ID (default: default_assistant).",
    )
    parser.add_argument(
        "--sharing-scope",
        default="ALL_USERS",
        choices=["ALL_USERS", "PRIVATE", "RESTRICTED"],
        help="Sharing visibility scope in Gemini Enterprise (default: ALL_USERS).",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Model ID for workflow AgentNodes (default: {DEFAULT_MODEL}).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate catalog and discover live environment without creating resources.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON deployment summary.",
    )

    args = parser.parse_args(argv)
    try:
        result = deploy_pack(
            project=args.project,
            engine_id=args.engine,
            location=args.location,
            assistant_id=args.assistant,
            sharing_scope=args.sharing_scope,
            model=args.model,
            dry_run=args.dry_run,
        )
    except Exception as exc:
        if args.json:
            print(json.dumps({"status": "error", "error": str(exc)}, indent=2))
        else:
            print(f"[ERROR] Marketing pack deployment failed: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("=" * 80)
        print(f" PRISM — GEMINI ENTERPRISE MARKETING PACK DEPLOYMENT ({result['mode']})")
        print("=" * 80)
        env = result["environment"]
        print(f" Project       : {env['project_id']} (#{env['project_number']})")
        print(f" Search Engine : {env['engine_id']}")
        print(f" Connectors    : {', '.join(sorted(env['connectors_by_source'].keys())) or 'none'}")
        if result["mode"] == "LIVE":
            sk = result["skill"]
            print("-" * 80)
            print(
                f" [1/3 SKILL] {sk['display_name']} ({sk['action']}) -> state={sk['state']} "
                f"scope={sk['sharing_scope']}"
            )
            print(f"             {sk['resource_name']}")
            for idx, ag in enumerate(result["agents"], start=2):
                print(
                    f" [{idx}/3 AGENT] {ag['display_name']} ({ag['action']}) -> state={ag['state']} "
                    f"scope={ag['sharing_scope']}"
                )
                print(f"             {ag['resource_name']}")
                if ag.get("publish_note"):
                    print(f"             [note] {ag['publish_note']}")
        print("=" * 80)
    return 0


if __name__ == "__main__":
    sys.exit(main())
