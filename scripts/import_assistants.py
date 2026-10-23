#!/usr/bin/env python3
"""
Prism — Discovery Engine Assistant State Importer
When a Vertex AI Search engine is created with SEARCH_ADD_ON_LLM, Google Cloud
automatically provisions default_assistant on the backend.
This script detects existing engines and imports default_assistant into Terraform state
if not already present, preventing 'Error 400: Only one assistant per engine is allowed'.
"""

import json
import os
import re
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def parse_tfvars(tfvars_path):
    if not os.path.exists(tfvars_path):
        return {}
    data = {}
    with open(tfvars_path, "r", encoding="utf-8") as f:
        content = f.read()
    str_matches = re.findall(r"^\s*([a-zA-Z0-9_-]+)\s*=\s*\"([^\"]*)\"", content, re.MULTILINE)
    for k, v in str_matches:
        data[k] = v
    list_matches = re.findall(r"^\s*([a-zA-Z0-9_-]+)\s*=\s*\[(.*?)\]", content, re.MULTILINE | re.DOTALL)
    for k, raw_items in list_matches:
        data[k] = re.findall(r"\"([^\"]*)\"", raw_items)
    return data


def get_terraform_cmd():
    import shutil
    if shutil.which("terraform"):
        return "terraform"
    for candidate in ["/opt/homebrew/bin/terraform", "/usr/local/bin/terraform"]:
        if os.path.exists(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return "terraform"


def import_assistants():
    state_path = os.path.join(REPO_ROOT, "terraform.tfstate")
    if not os.path.exists(state_path):
        return 0

    try:
        with open(state_path, "r", encoding="utf-8") as f:
            state = json.load(f)
    except Exception as e:
        print(f"[WARN] Could not parse terraform.tfstate: {e}")
        return 0

    tfvars_path = os.path.join(REPO_ROOT, "terraform.tfvars")
    tfvars = parse_tfvars(tfvars_path)
    location = tfvars.get("location", "global") or "global"
    customer_id = tfvars.get("customer_id", "")
    prefix = tfvars.get("project_id_prefix", "")

    resources = state.get("resources", [])

    # Map environment key -> project_id
    project_map = {}
    for res in resources:
        if res.get("type") == "google_project":
            for inst in res.get("instances", []):
                env_key = inst.get("index_key")
                pid = inst.get("attributes", {}).get("project_id")
                if env_key and pid:
                    project_map[env_key] = pid

    # Map environment key -> engine_id
    engine_map = {}
    for res in resources:
        if res.get("type") == "google_discovery_engine_search_engine":
            for inst in res.get("instances", []):
                env_key = inst.get("index_key")
                eid = inst.get("attributes", {}).get("engine_id")
                if env_key and eid:
                    engine_map[env_key] = eid

    # Set of environments that already have assistant in state
    managed_assistants = set()
    for res in resources:
        if res.get("type") == "google_discovery_engine_assistant":
            for inst in res.get("instances", []):
                env_key = inst.get("index_key")
                if env_key:
                    managed_assistants.add(env_key)

    terraform_bin = get_terraform_cmd()

    imported_count = 0
    for env_key, engine_id in engine_map.items():
        if env_key in managed_assistants:
            continue

        project_id = project_map.get(env_key) or f"{prefix}{customer_id}-{env_key}"
        resource_id = f"projects/{project_id}/locations/{location}/collections/default_collection/engines/{engine_id}/assistants/default_assistant"
        tf_addr = f"google_discovery_engine_assistant.default[\"{env_key}\"]"

        print(f"[INFO] Importing auto-created assistant for environment '{env_key}'...")
        proc = subprocess.run(
            [terraform_bin, "import", "-input=false", tf_addr, resource_id],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True
        )
        if proc.returncode == 0:
            print(f"[OK] Successfully imported {tf_addr}")
            imported_count += 1
        else:
            if "Resource already managed by Terraform" in proc.stderr:
                print(f"[INFO] {tf_addr} is already managed by Terraform.")
            else:
                print(f"[DEBUG] Import command output: {proc.stdout}\n{proc.stderr}")

    if imported_count > 0:
        print(f"[OK] Imported {imported_count} assistant(s) into Terraform state.")
    return 0


if __name__ == "__main__":
    sys.exit(import_assistants())
