#!/usr/bin/env python3
"""
Interactive Connector Onboarding Wizard & Input Variable Configuration Engine.

Provides:
- Mode A (Cross-Harness Combo-Box Integration): Machine-readable schema (--check --json)
  with interactive_questions array, paired with non-interactive application (--apply-json, --connectors, --set).
- Mode B (Interactive Terminal Combo-Box): Arrow-key ([↑/↓]) and spacebar ([Space])
  multi-select combo-box ([✓] / [ ]) with automatic fallback to numbered selection on non-TTY streams,
  and inline contextual help ('?') rendering boxed console links and Help Center guides.
- Stage-Aware Deployment Safety: Stage 0 prevents bypass of Foundation and Human Gates
  by enforcing enable_* = false while recording planned_connectors.
- Missing Variable Audit (--check / make check-inputs): Audits variables against Help Center guides.
- Stage 2 Enablement Helper (--enable-connectors / make enable-connectors): Validates prerequisites
  and flips enable_* = true for planned connectors.

100% Python Standard Library (zero external pip dependencies).
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys

# Optional POSIX raw terminal support
try:
    import select
    import termios
    import tty
    TERMIOS_AVAILABLE = True
except ImportError:
    TERMIOS_AVAILABLE = False


CONNECTOR_OPTIONS = [
    {
        "value": "workspace",
        "label": "Google Workspace (Gmail, Drive, Docs)",
        "description": "Domain-Wide Delegation connector for corporate email and files",
        "docs_url": "https://docs.cloud.google.com/gemini/enterprise/docs/connectors/drive",
        "help_url": "https://docs.cloud.google.com/gemini/enterprise/docs/connectors/drive",
        "doc_url": "https://docs.cloud.google.com/gemini/enterprise/docs/connectors/drive",
        "admin_url": "https://admin.google.com/ac/owl/domainwidedelegation",
        "lookup_command": "gcloud auth list",
        "required_roles": ["Google Workspace Super Admin"],
        "default": True,
        "enable_flag": "enable_connectors",
    },
    {
        "value": "jira",
        "label": "Jira Cloud",
        "description": "Atlassian Jira Cloud project and issue search connector",
        "docs_url": "https://docs.cloud.google.com/gemini/enterprise/docs/connectors/jira-cloud",
        "help_url": "https://docs.cloud.google.com/gemini/enterprise/docs/connectors/jira-cloud",
        "doc_url": "https://docs.cloud.google.com/gemini/enterprise/docs/connectors/jira-cloud",
        "admin_url": "https://developer.atlassian.com/console/myapps/",
        "lookup_command": "curl -s https://<site>.atlassian.net/_edge/tenant_info | jq -r .cloudId",
        "required_roles": ["Atlassian Site Administrator"],
        "default": False,
        "enable_flag": "enable_jira_connector",
    },
    {
        "value": "people_directory",
        "label": "Google Workspace People Directory",
        "description": "User profile and directory search connector",
        "docs_url": "https://developers.google.com/admin-sdk/directory/v1/guides",
        "help_url": "https://developers.google.com/admin-sdk/directory/v1/guides",
        "doc_url": "https://developers.google.com/admin-sdk/directory/v1/guides",
        "admin_url": "https://admin.google.com/ac/owl/domainwidedelegation",
        "lookup_command": "echo 'people-directory-collection'",
        "required_roles": ["Google Workspace Super Admin"],
        "default": False,
        "enable_flag": "enable_people_directory_connector",
    },
]

PLACEHOLDER_STRINGS = {
    "example-customer",
    "example customer",
    "example.com",
    "c01234567",
    "0x1xxx-xxxxxx-xxxxxx",
    "00000000-0000-0000-0000-000000000000",
}

VARIABLE_METADATA = {
    "customer_id": {
        "name": "customer_id",
        "title": "Customer Slug",
        "description": "Unique lowercase alphanumeric customer slug (e.g. 'acme')",
        "connector": "foundation",
        "where_to_get": "Choose a short unique slug (alphanumeric, lowercase, hyphenated). Used in project IDs (${customer_id}-${env}).",
        "admin_url": "https://console.cloud.google.com",
        "lookup_command": "echo 'acme'",
        "required_roles": ["roles/resourcemanager.projectCreator"],
        "help_center_url": "https://cloud.google.com/resource-manager/docs/creating-managing-projects",
    },
    "customer_name": {
        "name": "customer_name",
        "title": "Customer Display Name",
        "description": "Human-readable display name of the customer organization",
        "connector": "foundation",
        "where_to_get": "Customer's official organization display name.",
        "admin_url": "https://admin.google.com/ac/accountsettings",
        "lookup_command": "echo 'Acme Corporation'",
        "required_roles": ["roles/resourcemanager.projectCreator"],
        "help_center_url": "https://support.google.com/a/answer/10070793",
    },
    "company_domain": {
        "name": "company_domain",
        "title": "Google Workspace Domain",
        "description": "Primary domain name of Google Workspace tenant (e.g. acme.com)",
        "connector": "foundation",
        "where_to_get": "Primary Google Workspace domain registered to your tenant.",
        "admin_url": "https://admin.google.com/ac/domains/manage",
        "lookup_command": "gcloud organizations list",
        "required_roles": ["Google Workspace Super Admin", "Groups Admin"],
        "help_center_url": "https://support.google.com/a/answer/182081",
    },
    "workspace_customer_id": {
        "name": "workspace_customer_id",
        "title": "Google Workspace Customer ID",
        "description": "Google Workspace Customer ID (e.g. C01234567)",
        "connector": "foundation",
        "where_to_get": "Alphanumeric Google Workspace Customer ID. In Admin Console: Account > Account settings > Profile > Customer ID.",
        "admin_url": "https://admin.google.com/ac/accountsettings",
        "lookup_command": "gcloud organizations list --format='value(owner.directoryCustomerId)'",
        "required_roles": ["Google Workspace Super Admin"],
        "help_center_url": "https://support.google.com/a/answer/10070793",
    },
    "billing_account": {
        "name": "billing_account",
        "title": "GCP Cloud Billing Account ID",
        "description": "GCP Cloud Billing Account ID in format 0X1XXX-XXXXXX-XXXXXX",
        "connector": "foundation",
        "where_to_get": "Google Cloud Console > Billing > Billing account management.",
        "admin_url": "https://console.cloud.google.com/billing",
        "lookup_command": "gcloud billing accounts list --format='table(name,displayName,open)'",
        "required_roles": ["roles/billing.admin", "roles/billing.user"],
        "help_center_url": "https://cloud.google.com/billing/docs/how-to/find-billing-account-id",
    },
    "jira_instance_uri": {
        "name": "jira_instance_uri",
        "title": "Atlassian Jira Site URL",
        "description": "Atlassian Jira base URL (e.g. https://<site>.atlassian.net)",
        "connector": "jira",
        "where_to_get": "Atlassian Admin Console or your Jira Cloud site URL.",
        "admin_url": "https://developer.atlassian.com/console/myapps/",
        "lookup_command": "echo 'https://<your-domain>.atlassian.net'",
        "required_roles": ["Atlassian Site Administrator"],
        "help_center_url": "https://docs.cloud.google.com/gemini/enterprise/docs/connectors/jira-cloud",
    },
    "jira_auth": {
        "name": "jira_auth",
        "title": "Atlassian Jira Credentials",
        "description": "Atlassian Jira credentials (client_id, client_secret, instance_id or api_token)",
        "connector": "jira",
        "where_to_get": "Atlassian Developer Console (OAuth 2.0 3LO App) or API Tokens.",
        "admin_url": "https://developer.atlassian.com/console/myapps/",
        "lookup_command": "curl -s https://<site>.atlassian.net/_edge/tenant_info | jq -r .cloudId",
        "required_roles": ["Atlassian Site Administrator"],
        "help_center_url": "https://docs.cloud.google.com/gemini/enterprise/docs/connectors/jira-cloud",
    },
}


def is_placeholder(val):
    """Check if value is None, empty, or an unresolved example placeholder."""
    if val is None:
        return True
    s = str(val).strip().lower()
    if not s:
        return True
    if s in PLACEHOLDER_STRINGS:
        return True
    if any(p in s for p in ["0x1xxx", "example-customer", "example.com", "example.atlassian.net"]):
        return True
    return False


def parse_tfvars(tfvars_path):
    """
    Lightweight, robust parser for terraform.tfvars without external dependencies.
    Extracts strings, booleans, lists, and maps.
    """
    if not os.path.exists(tfvars_path):
        return None

    data = {}
    with open(tfvars_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Remove single-line comments (# or //)
    lines = []
    for line in content.splitlines():
        line = re.sub(r'(?<!:)\/\/.*$', '', line)
        line = re.sub(r'#.*$', '', line)
        lines.append(line)
    clean_text = "\n".join(lines)

    # Match maps: key = { ... }
    map_matches = re.findall(r'^\s*([a-zA-Z0-9_-]+)\s*=\s*\{(.*?)\}', clean_text, re.MULTILINE | re.DOTALL)
    for k, raw_map in map_matches:
        inner = {}
        for mk, raw_items in re.findall(r'([a-zA-Z0-9_-]+)\s*=\s*\[(.*?)\]', raw_map, re.DOTALL):
            inner[mk] = re.findall(r'["\']([^"\']*)["\']', raw_items)
        raw_map_clean = re.sub(r'([a-zA-Z0-9_-]+)\s*=\s*\[.*?\]', '', raw_map, flags=re.DOTALL)
        for mk, mv in re.findall(r'([a-zA-Z0-9_-]+)\s*=\s*"([^"]*)"', raw_map_clean):
            if mk not in inner:
                inner[mk] = mv
        for mk, mv in re.findall(r'([a-zA-Z0-9_-]+)\s*=\s*([a-zA-Z0-9_./:-]+)\b', raw_map_clean):
            if mk not in inner:
                if mv.lower() == "true":
                    inner[mk] = True
                elif mv.lower() == "false":
                    inner[mk] = False
                elif mv.lower() == "null":
                    inner[mk] = None
                elif mv.isdigit():
                    inner[mk] = int(mv)
                else:
                    inner[mk] = mv
        data[k] = inner

    text_without_maps = re.sub(r'^\s*[a-zA-Z0-9_-]+\s*=\s*\{.*?\}', '', clean_text, flags=re.MULTILINE | re.DOTALL)

    # Match strings
    for k, v in re.findall(r'^\s*([a-zA-Z0-9_-]+)\s*=\s*"([^"]*)"', text_without_maps, re.MULTILINE):
        data[k] = v

    # Match booleans
    for k, v in re.findall(r'^\s*([a-zA-Z0-9_-]+)\s*=\s*(true|false)\b', text_without_maps, re.MULTILINE):
        data[k] = (v.lower() == "true")

    # Match lists
    for k, raw_items in re.findall(r'^\s*([a-zA-Z0-9_-]+)\s*=\s*\[(.*?)\]', text_without_maps, re.MULTILINE | re.DOTALL):
        items = re.findall(r'["\']([^"\']*)["\']', raw_items)
        data[k] = items

    return data


def parse_state(state_path):
    """Parse local terraform.tfstate if it exists."""
    if not os.path.exists(state_path):
        return None
    try:
        with open(state_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        return {"_error": str(e)}


def determine_stage(workdir=".", state_path=None, tfvars_path=None):
    """
    Determine current live deployment stage (0 to 5) consistent with status.py.
    Stage 0: Preflight / Inputs
    Stage 1: Foundation Apply
    Stage 2: DWD / Jira Authorization Gate
    Stage 3: Connectors & Search Engines Apply
    Stage 4: Licensing
    Stage 5: Verification Complete
    """
    actual_tfvars = tfvars_path or os.path.join(workdir, "terraform.tfvars")
    tfvars = parse_tfvars(actual_tfvars)
    if tfvars is None:
        return 0

    required_keys = ["customer_id", "customer_name", "company_domain", "workspace_customer_id", "billing_account"]
    for k in required_keys:
        if is_placeholder(tfvars.get(k)):
            return 0

    actual_state = state_path or os.path.join(workdir, "terraform.tfstate")
    state = parse_state(actual_state)
    if not state or "_error" in state:
        return 1

    outputs = state.get("outputs", {})
    project_ids = outputs.get("project_ids", {}).get("value", {})
    envs = tfvars.get("environments", ["non-prod", "prod"])
    if not project_ids or not all(e in project_ids for e in envs):
        return 1

    # Foundation is complete -> Stage 2 or beyond
    enable_connectors = tfvars.get("enable_connectors", False)
    enable_jira = tfvars.get("enable_jira_connector", False)
    enable_directory = tfvars.get("enable_people_directory_connector", False)

    if not enable_connectors and not enable_jira and not enable_directory:
        return 2

    # Check Jira if enabled
    if enable_jira:
        jira_cfg = tfvars.get("jira_config", {})
        instance_uri = str(jira_cfg.get("instance_uri", "")).strip()
        if not instance_uri or "example.atlassian.net" in instance_uri:
            return 2

    search_engines = outputs.get("search_engine_names", {}).get("value", {})
    assistants = outputs.get("assistant_names", {}).get("value", {})
    if not search_engines or not assistants:
        return 3

    license_config = tfvars.get("license_config_id", "")
    subscription = tfvars.get("subscription_id", "")
    if is_placeholder(license_config) or is_placeholder(subscription):
        return 4

    return 5


def get_interactive_questions():
    """
    Return interactive_questions schema array for coding harness agents (ask_question, AskUserQuestion).
    """
    return [
        {
            "id": "planned_connectors",
            "header": "Planned Connectors",
            "question": "Which data connectors do you plan to onboard for Gemini Enterprise?",
            "type": "multi_select",
            "is_multi_select": True,
            "options": [
                {
                    "value": opt["value"],
                    "label": opt["label"],
                    "description": opt["description"],
                    "docs_url": opt["docs_url"],
                    "help_url": opt["docs_url"],
                    "doc_url": opt["docs_url"],
                }
                for opt in CONNECTOR_OPTIONS
            ],
            "default": ["workspace"],
        }
    ]


def audit_inputs(tfvars=None, planned_connectors=None, workdir="."):
    """
    Audit configured vs missing/placeholder variables.
    Returns dictionary with status ('ok' | 'missing_variables'), configured_variables, and missing_variables.
    """
    if tfvars is None:
        tfvars = {}
    if planned_connectors is None:
        planned_connectors = tfvars.get("planned_connectors", ["workspace"])

    configured_variables = {}
    missing_variables = []

    # 1. Foundation variables
    foundation_keys = ["customer_id", "customer_name", "company_domain", "workspace_customer_id", "billing_account"]
    for k in foundation_keys:
        meta = VARIABLE_METADATA.get(k)
        val = tfvars.get(k)
        if is_placeholder(val):
            missing_variables.append({
                "name": k,
                "description": meta["description"],
                "connector": meta["connector"],
                "where_to_get": meta["where_to_get"],
                "admin_url": meta["admin_url"],
                "lookup_command": meta["lookup_command"],
                "required_roles": meta["required_roles"],
                "required_iam_roles": meta["required_roles"],
                "help_center_url": meta["help_center_url"],
                "help_url": meta["help_center_url"],
            })
        else:
            configured_variables[k] = val

    # 2. Jira variables if planned
    if "jira" in planned_connectors:
        jira_cfg = tfvars.get("jira_config", {})
        uri = jira_cfg.get("instance_uri") or tfvars.get("jira_instance_uri")
        meta_uri = VARIABLE_METADATA["jira_instance_uri"]
        if is_placeholder(uri):
            missing_variables.append({
                "name": "jira_instance_uri",
                "description": meta_uri["description"],
                "connector": meta_uri["connector"],
                "where_to_get": meta_uri["where_to_get"],
                "admin_url": meta_uri["admin_url"],
                "lookup_command": meta_uri["lookup_command"],
                "required_roles": meta_uri["required_roles"],
                "required_iam_roles": meta_uri["required_roles"],
                "help_center_url": meta_uri["help_center_url"],
                "help_url": meta_uri["help_center_url"],
            })
        else:
            configured_variables["jira_instance_uri"] = uri

        has_jira_cred = (
            bool(os.environ.get("TF_VAR_jira_auth")) or
            os.path.exists(os.path.join(workdir, ".env.jira")) or
            bool(tfvars.get("jira_auth"))
        )
        meta_auth = VARIABLE_METADATA["jira_auth"]
        if not has_jira_cred:
            missing_variables.append({
                "name": "jira_auth",
                "description": meta_auth["description"],
                "connector": meta_auth["connector"],
                "where_to_get": meta_auth["where_to_get"],
                "admin_url": meta_auth["admin_url"],
                "lookup_command": meta_auth["lookup_command"],
                "required_roles": meta_auth["required_roles"],
                "required_iam_roles": meta_auth["required_roles"],
                "help_center_url": meta_auth["help_center_url"],
                "help_url": meta_auth["help_center_url"],
            })
        else:
            configured_variables["jira_auth"] = "********"

    # Add other configured variables from tfvars
    for k, v in tfvars.items():
        if k not in configured_variables and not is_placeholder(v):
            if k not in ["jira_config", "people_directory_config"]:
                configured_variables[k] = v

    status = "ok" if not missing_variables else "missing_variables"
    return {
        "status": status,
        "configured_variables": configured_variables,
        "missing_variables": missing_variables,
        "planned_connectors": planned_connectors,
    }


def update_tfvars(tfvars_path, updates, stage=0, allow_enable=False, workdir="."):
    """
    Update terraform.tfvars preserving comments and formatting.
    If in Stage 0 and allow_enable is False, forces enable_* = false.
    """
    dir_name = os.path.dirname(tfvars_path) or "."
    example_path = os.path.join(dir_name, "terraform.tfvars.example")
    if not os.path.exists(example_path) and workdir:
        candidate = os.path.join(workdir, "terraform.tfvars.example")
        if os.path.exists(candidate):
            example_path = candidate

    if os.path.exists(tfvars_path):
        with open(tfvars_path, "r", encoding="utf-8") as f:
            content = f.read()
    elif os.path.exists(example_path):
        with open(example_path, "r", encoding="utf-8") as f:
            content = f.read()
    else:
        content = "# Gemini Prism Terraform Configuration\n"

    # Stage 0 Safety Guard
    if stage == 0 and not allow_enable:
        updates["enable_connectors"] = False
        updates["enable_jira_connector"] = False
        updates["enable_people_directory_connector"] = False

    # 1. Update planned_connectors
    if "planned_connectors" in updates:
        val_str = json.dumps(updates["planned_connectors"])
        line = f"planned_connectors   = {val_str}"
        if re.search(r'^\s*planned_connectors\s*=.*$', content, re.MULTILINE):
            content = re.sub(r'^\s*planned_connectors\s*=.*$', line, content, flags=re.MULTILINE)
        elif re.search(r'^\s*enable_connectors\s*=.*$', content, re.MULTILINE):
            content = re.sub(r'(^\s*enable_connectors\s*=.*$)', f"{line}\n\\1", content, flags=re.MULTILINE)
        else:
            content += f"\n{line}\n"

    # 2. Update enable_* flags
    for flag in ["enable_connectors", "enable_jira_connector", "enable_people_directory_connector"]:
        if flag in updates:
            val_bool = "true" if updates[flag] else "false"
            spacing = "    " if flag == "enable_connectors" else " "
            line = f"{flag}{spacing}= {val_bool}"
            if re.search(r'^\s*' + re.escape(flag) + r'\s*=.*$', content, re.MULTILINE):
                content = re.sub(r'^\s*' + re.escape(flag) + r'\s*=.*$', line, content, flags=re.MULTILINE)
            else:
                content += f"\n{line}\n"

    # 3. Update Jira config nested properties
    jira_uri = updates.get("jira_instance_uri") or updates.get("jira_config.instance_uri")
    if jira_uri:
        def replace_jira_uri(m):
            block = m.group(0)
            if re.search(r'instance_uri\s*=\s*"[^"]*"', block):
                return re.sub(r'instance_uri\s*=\s*"[^"]*"', f'instance_uri        = "{jira_uri}"', block)
            return block
        content = re.sub(r'jira_config\s*=\s*\{.*?\}', replace_jira_uri, content, flags=re.DOTALL)

    jira_id = updates.get("jira_instance_id") or updates.get("jira_config.instance_id")
    if jira_id:
        def replace_jira_id(m):
            block = m.group(0)
            if re.search(r'instance_id\s*=\s*"[^"]*"', block):
                return re.sub(r'instance_id\s*=\s*"[^"]*"', f'instance_id         = "{jira_id}"', block)
            return block
        content = re.sub(r'jira_config\s*=\s*\{.*?\}', replace_jira_id, content, flags=re.DOTALL)

    # 4. Update top-level variables
    skip_keys = {
        "planned_connectors",
        "enable_connectors",
        "enable_jira_connector",
        "enable_people_directory_connector",
        "jira_instance_uri",
        "jira_instance_id",
        "jira_config.instance_uri",
        "jira_config.instance_id",
        "jira_auth",
    }
    for k, v in updates.items():
        if k in skip_keys:
            continue
        if isinstance(v, bool):
            val_repr = "true" if v else "false"
        elif isinstance(v, (int, float)):
            val_repr = str(v)
        elif v is None:
            val_repr = "null"
        elif isinstance(v, list):
            val_repr = json.dumps(v)
        elif isinstance(v, dict):
            inner_lines = []
            for dk, dv in v.items():
                if isinstance(dv, bool):
                    dvr = "true" if dv else "false"
                elif isinstance(dv, (int, float)):
                    dvr = str(dv)
                elif dv is None:
                    dvr = "null"
                elif isinstance(dv, list):
                    dvr = json.dumps(dv)
                else:
                    dvr = f'"{dv}"'
                inner_lines.append(f"  {dk:20} = {dvr}")
            val_repr = "{\n" + "\n".join(inner_lines) + "\n}"
        else:
            val_repr = f'"{v}"'

        pattern = r'^\s*' + re.escape(k) + r'\s*=.*$'
        if re.search(pattern, content, re.MULTILINE):
            content = re.sub(pattern, f"{k:21} = {val_repr}", content, flags=re.MULTILINE)
        else:
            content += f"\n{k:21} = {val_repr}\n"

    # Write .env.jira helper if jira_auth is provided
    if "jira_auth" in updates and updates["jira_auth"]:
        jira_auth_val = updates["jira_auth"]
        jira_auth_str = json.dumps(jira_auth_val) if isinstance(jira_auth_val, dict) else str(jira_auth_val)
        env_jira_path = os.path.join(dir_name, ".env.jira")
        with open(env_jira_path, "w", encoding="utf-8") as f:
            f.write(f"export TF_VAR_jira_auth='{jira_auth_str}'\n")
        try:
            os.chmod(env_jira_path, 0o600)
        except Exception:
            pass

    with open(tfvars_path, "w", encoding="utf-8") as f:
        f.write(content)


def print_boxed_help(topic=None):
    """Render formatted boxed 'Where to find this' guide with Help Center URLs and console links."""
    width = 78
    print()
    print("┌" + "─" * (width - 2) + "┐")
    print("│ " + "WHERE TO FIND THIS — Gemini Enterprise Help Center & Credentials".center(width - 4) + " │")
    print("├" + "─" * (width - 2) + "┤")
    print("│ 1. Google Workspace (Gmail, Calendar, Drive, Chat)                         │")
    print("│    • Help Center: https://docs.cloud.google.com/gemini/enterprise/docs/    │")
    print("│      connectors/drive                                                      │")
    print("│    • Workspace Admin Console: https://admin.google.com/ac/owl/             │")
    print("│      domainwidedelegation                                                  │")
    print("│    • Required IAM: Google Workspace Super Admin                            │")
    print("│                                                                            │")
    print("│ 2. Atlassian Jira Cloud                                                    │")
    print("│    • Help Center: https://docs.cloud.google.com/gemini/enterprise/docs/    │")
    print("│      connectors/jira-cloud                                                 │")
    print("│    • Developer Console: https://developer.atlassian.com/console/myapps/   │")
    print("│    • Lookup Cloud ID: curl -s https://<site>.atlassian.net/_edge/          │")
    print("│      tenant_info | jq -r .cloudId                                          │")
    print("│    • Required Auth: OAuth 2.0 (3LO) App with read:jira-work scopes         │")
    print("│                                                                            │")
    print("│ 3. Google Workspace People Directory                                      │")
    print("│    • Guide: https://developers.google.com/admin-sdk/directory/v1/guides   │")
    print("│    • Workspace Admin: https://admin.google.com/ac/owl/domainwidedelegation │")
    print("│    • Required Scopes: Directory API user.readonly, orgunit.readonly       │")
    print("│                                                                            │")
    print("│ 4. Google Cloud Core Parameters                                            │")
    print("│    • Billing Account ID: https://console.cloud.google.com/billing           │")
    print("│      (Lookup command: gcloud billing accounts list)                        │")
    print("│    • Workspace Customer ID: https://admin.google.com/ac/accountsettings     │")
    print("│      (Account settings > Profile > Customer ID, e.g. C01234567)            │")
    print("└" + "─" * (width - 2) + "┘")
    print()


def fallback_combo_box(prompt_title, options, default_values=None):
    """
    Numbered fallback selection for non-TTY streams or environments without termios.
    """
    if default_values is None:
        default_values = ["workspace"]
    print(f"\n{prompt_title}")
    for idx, opt in enumerate(options, 1):
        is_def = opt["value"] in default_values
        mark = " [default: YES]" if is_def else ""
        print(f"  [{idx}] {opt['label']}{mark}")
        print(f"      {opt['description']}")
    print()
    print("Type numbers to toggle (e.g. '1', '1,2'), '?' for help, or Enter to accept default:")

    while True:
        sys.stdout.write("Selection [default: 1]: ")
        sys.stdout.flush()
        line = sys.stdin.readline()
        if not line:
            print()
            return list(default_values)
        line = line.strip()
        if not line:
            return list(default_values)
        if line == "?":
            print_boxed_help()
            print("Type numbers to toggle (e.g. '1', '1,2'), '?' for help, or Enter to accept default:")
            continue

        tokens = [t.strip().lower() for t in re.split(r'[, ]+', line) if t.strip()]
        selected = []
        for t in tokens:
            if t.isdigit():
                idx = int(t) - 1
                if 0 <= idx < len(options):
                    val = options[idx]["value"]
                    if val not in selected:
                        selected.append(val)
            else:
                for opt in options:
                    if t == opt["value"].lower() or t in opt["label"].lower():
                        if opt["value"] not in selected:
                            selected.append(opt["value"])
        if selected:
            return selected
        print("Invalid selection. Please enter numbers matching options above, or '?' for help.")


class RawTerminal:
    """Context manager for POSIX raw/cbreak terminal mode."""

    def __init__(self, stream=None):
        self.stream = stream or sys.stdin
        self.fd = None
        self.old_settings = None

    def __enter__(self):
        if TERMIOS_AVAILABLE and hasattr(self.stream, "fileno") and self.stream.isatty():
            try:
                self.fd = self.stream.fileno()
                self.old_settings = termios.tcgetattr(self.fd)
                tty.setcbreak(self.fd)
            except Exception:
                self.fd = None
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.fd is not None and self.old_settings is not None:
            try:
                termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old_settings)
            except Exception:
                pass


def read_terminal_key(stream=None):
    """Read a single keypress or escape sequence from terminal stream."""
    s = stream or sys.stdin
    ch = s.read(1)
    if ch == "\x1b":
        if select.select([s], [], [], 0.05)[0]:
            ch2 = s.read(1)
            if ch2 == "[":
                ch3 = s.read(1)
                if ch3 == "A":
                    return "UP"
                elif ch3 == "B":
                    return "DOWN"
                elif ch3 == "C":
                    return "RIGHT"
                elif ch3 == "D":
                    return "LEFT"
            return "ESC"
        return "ESC"
    elif ch in ("\r", "\n"):
        return "ENTER"
    elif ch == " ":
        return "SPACE"
    elif ch == "?":
        return "?"
    elif ch in ("q", "Q"):
        return "QUIT"
    elif ch == "\x03":
        raise KeyboardInterrupt
    return ch


def interactive_combo_box(prompt_title, options, default_values=None):
    """
    Render ANSI arrow-key ([↑/↓]) and spacebar ([Space]) multi-select combo-box ([✓] / [ ]).
    Falls back gracefully if raw terminal is unavailable.
    """
    if not (TERMIOS_AVAILABLE and sys.stdin.isatty() and sys.stdout.isatty()):
        return fallback_combo_box(prompt_title, options, default_values)

    selected = set(default_values or ["workspace"])
    cursor = 0
    show_help = False
    last_line_count = 0

    def render():
        nonlocal last_line_count
        lines = []
        if last_line_count > 0:
            for _ in range(last_line_count):
                sys.stdout.write("\033[F\033[K")

        lines.append(f"\n{prompt_title}")
        for i, opt in enumerate(options):
            val = opt["value"]
            is_sel = val in selected
            is_cur = (i == cursor)
            check = "[✓]" if is_sel else "[ ]"
            pointer = "❯ " if is_cur else "  "
            lines.append(f" {pointer}{check} {opt['label']}")
            lines.append(f"      {opt['description']}")
        lines.append("")
        lines.append(" [↑/↓] Navigate   [Space] Toggle   [?] Help Guide   [Enter] Confirm")

        if show_help:
            lines.append("┌" + "─" * 76 + "┐")
            lines.append("│ WHERE TO FIND THIS — Gemini Enterprise Help Center & Credentials".center(78) + "│")
            lines.append("├" + "─" * 76 + "┤")
            lines.append("│ • Workspace: https://docs.cloud.google.com/gemini/enterprise/docs/connectors/drive │")
            lines.append("│ • Jira:      https://docs.cloud.google.com/gemini/enterprise/docs/connectors/jira-cloud │")
            lines.append("│ • Directory: https://developers.google.com/admin-sdk/directory/v1/guides           │")
            lines.append("└" + "─" * 76 + "┘")

        output_str = "\n".join(lines) + "\n"
        sys.stdout.write(output_str)
        sys.stdout.flush()
        last_line_count = len(lines) + 1

    try:
        with RawTerminal():
            render()
            while True:
                key = read_terminal_key()
                if key in ("UP", "k"):
                    cursor = (cursor - 1) % len(options)
                    render()
                elif key in ("DOWN", "j"):
                    cursor = (cursor + 1) % len(options)
                    render()
                elif key == "SPACE":
                    val = options[cursor]["value"]
                    if val in selected:
                        selected.remove(val)
                    else:
                        selected.add(val)
                    render()
                elif key == "?":
                    show_help = not show_help
                    render()
                elif key == "ENTER":
                    break
                elif key == "QUIT":
                    break
    except Exception:
        return fallback_combo_box(prompt_title, options, default_values)

    return [opt["value"] for opt in options if opt["value"] in selected]


def print_human_audit(stage, planned_connectors, audit_data):
    """Print human-readable variable audit status table."""
    print("=" * 80)
    print("GEMINI PRISM — INPUT VARIABLE & CONNECTOR AUDIT")
    print("=" * 80)
    print(f"Stage              : {stage}")
    print(f"Planned Connectors : {', '.join(planned_connectors)}")
    status_str = "OK — All required variables are configured!" if audit_data["status"] == "ok" else f"MISSING VARIABLES ({len(audit_data['missing_variables'])} missing / placeholder)"
    print(f"Audit Status       : {status_str}")
    print()

    cfg = audit_data["configured_variables"]
    if cfg:
        print(f"Configured Variables ({len(cfg)}):")
        for k in sorted(cfg.keys()):
            val = str(cfg[k])
            if len(val) > 40:
                val = val[:37] + "..."
            print(f"  • {k:30} = {val}")
        print()

    missing = audit_data["missing_variables"]
    if missing:
        print(f"Missing / Placeholder Variables ({len(missing)}):")
        print("-" * 80)
        for i, item in enumerate(missing, 1):
            print(f"{i}. {item['name']} ({item['connector']})")
            print(f"   Description : {item['description']}")
            print(f"   Where to get: {item['where_to_get']}")
            print(f"   Admin URL   : {item['admin_url']}")
            print(f"   Lookup CMD  : {item['lookup_command']}")
            print(f"   IAM Roles   : {', '.join(item['required_roles'])}")
            print(f"   Help Center : {item['help_center_url']}")
            print("-" * 80)
        print()
        print("[ACTION REQUIRED] Complete the missing variables above.")
        print("Run 'python3 scripts/configure.py' for interactive setup,")
        print("or apply via 'python3 scripts/configure.py --apply-json <json>'.")
    else:
        print("[SUCCESS] All required variables for planned connectors are configured.")


def enable_connectors(workdir=".", state_path=None, tfvars_path=None, json_output=False):
    """
    Stage 2 Enablement Helper:
    Verifies that all prerequisites and credentials for planned_connectors are satisfied,
    then flips enable_* = true in terraform.tfvars.
    """
    actual_tfvars = tfvars_path or os.path.join(workdir, "terraform.tfvars")
    if not os.path.exists(actual_tfvars):
        msg = f"Configuration file not found: {actual_tfvars}. Run 'python3 scripts/configure.py' first."
        if json_output:
            print(json.dumps({"status": "error", "message": msg}, indent=2))
        else:
            print(f"[ERROR] {msg}", file=sys.stderr)
        sys.exit(1)

    tfvars = parse_tfvars(actual_tfvars) or {}
    planned = tfvars.get("planned_connectors", ["workspace"])

    stage = determine_stage(workdir, state_path, actual_tfvars)
    if stage < 2:
        msg = "Stage 1 Foundation must be applied before enabling connectors. Run 'make plan-foundation && make apply-foundation'."
        if json_output:
            print(json.dumps({"status": "error", "message": msg, "stage": stage}, indent=2))
        else:
            print(f"[ERROR] Refusing enablement: {msg}", file=sys.stderr)
        sys.exit(1)

    errors = []
    if "workspace" in planned:
        if is_placeholder(tfvars.get("company_domain")):
            errors.append("Workspace prerequisite missing: 'company_domain' is not configured.")
        if is_placeholder(tfvars.get("workspace_customer_id")):
            errors.append("Workspace prerequisite missing: 'workspace_customer_id' is not configured.")

    if "jira" in planned:
        jira_cfg = tfvars.get("jira_config", {})
        uri = str(jira_cfg.get("instance_uri") or tfvars.get("jira_instance_uri") or "").strip()
        if not uri or is_placeholder(uri) or "example.atlassian.net" in uri:
            errors.append("Jira prerequisite missing: 'jira_config.instance_uri' is not configured or placeholder.")
        modes = jira_cfg.get("connector_modes", ["FEDERATED"])
        if "DATA_INGESTION" in modes or "FEDERATED" not in modes:
            errors.append("Jira prerequisite invalid: Jira connector must use FEDERATED mode (connector_modes = [\"FEDERATED\"]).")
        auth_type = str(tfvars.get("jira_auth_type", "OAUTH")).strip().upper()
        if ".atlassian.net" in uri.lower() and auth_type in ("BASIC_AUTH", "API_TOKEN"):
            errors.append("Jira prerequisite invalid: Atlassian Jira Cloud (*.atlassian.net) requires OAuth 2.0 (jira_auth_type = \"OAUTH\").")

        has_jira_cred = (
            bool(os.environ.get("TF_VAR_jira_auth")) or
            os.path.exists(os.path.join(workdir, ".env.jira")) or
            bool(tfvars.get("jira_auth"))
        )
        if not has_jira_cred:
            errors.append("Jira prerequisite missing: Credentials not found in TF_VAR_jira_auth, .env.jira, or terraform.tfvars.")

    if "people_directory" in planned:
        if is_placeholder(tfvars.get("company_domain")) or is_placeholder(tfvars.get("workspace_customer_id")):
            errors.append("People Directory prerequisite missing: Workspace domain and customer ID must be configured.")

    if errors:
        if json_output:
            print(json.dumps({"status": "prerequisites_failed", "errors": errors}, indent=2))
        else:
            print("[ERROR] Cannot enable connectors — prerequisites missing or invalid:", file=sys.stderr)
            for err in errors:
                print(f"  • {err}", file=sys.stderr)
            print("\nSee RUNBOOK.md §Stage 2 for authorization checklists.", file=sys.stderr)
        sys.exit(1)

    updates = {
        "enable_connectors": ("workspace" in planned),
        "enable_jira_connector": ("jira" in planned),
        "enable_people_directory_connector": ("people_directory" in planned),
    }
    update_tfvars(actual_tfvars, updates, stage=stage, allow_enable=True, workdir=workdir)

    if json_output:
        print(json.dumps({
            "status": "enabled",
            "planned_connectors": planned,
            "enabled_flags": updates
        }, indent=2))
    else:
        print("=" * 80)
        print("[SUCCESS] Planned connectors enabled in terraform.tfvars:")
        print(f"  • enable_connectors                = {str(updates['enable_connectors']).lower()}")
        print(f"  • enable_jira_connector            = {str(updates['enable_jira_connector']).lower()}")
        print(f"  • enable_people_directory_connector = {str(updates['enable_people_directory_connector']).lower()}")
        print("=" * 80)
        print("Next step: Run 'make plan-connectors && make apply-connectors' to provision resources.")
    sys.exit(0)


def main():
    parser = argparse.ArgumentParser(
        description="Interactive Connector Onboarding Wizard & Input Variable Configuration Engine."
    )
    parser.add_argument("--check", action="store_true", help="Audit variables against planned connectors.")
    parser.add_argument("--json", action="store_true", help="Output audit or operation result in JSON format.")
    parser.add_argument("--apply-json", help="JSON string containing configuration to apply non-interactively.")
    parser.add_argument("--connectors", help="Comma-separated list of planned connectors (workspace,jira,people_directory).")
    parser.add_argument("--set", action="append", default=[], help="Set variable key=value (can be used multiple times).")
    parser.add_argument("--enable-connectors", action="store_true", help="Stage 2 helper: Validate prerequisites and flip enable_* = true.")
    parser.add_argument("--workdir", default=".", help="Root directory of Terraform configuration.")
    parser.add_argument("--tfvars-file", help="Path to terraform.tfvars file override.")
    parser.add_argument("--state-file", help="Path to terraform.tfstate file override.")
    parser.add_argument("--non-interactive", action="store_true", help="Force non-interactive mode.")

    args = parser.parse_args()
    workdir = os.path.abspath(args.workdir)
    tfvars_path = os.path.abspath(args.tfvars_file) if args.tfvars_file else os.path.join(workdir, "terraform.tfvars")
    state_path = os.path.abspath(args.state_file) if args.state_file else os.path.join(workdir, "terraform.tfstate")

    # 1. Stage 2 Enablement Helper
    if args.enable_connectors:
        enable_connectors(workdir=workdir, state_path=state_path, tfvars_path=tfvars_path, json_output=args.json)
        return

    # 2. Check / Audit Mode
    if args.check or (args.json and not args.apply_json and not args.connectors and not args.set):
        tfvars = parse_tfvars(tfvars_path) or {}
        planned = tfvars.get("planned_connectors", ["workspace"])
        stage = determine_stage(workdir, state_path, tfvars_path)
        audit_data = audit_inputs(tfvars, planned, workdir=workdir)

        if args.json:
            result = {
                "status": audit_data["status"],
                "stage": stage,
                "interactive_questions": get_interactive_questions(),
                "configured_variables": audit_data["configured_variables"],
                "missing_variables": audit_data["missing_variables"],
                "planned_connectors": planned,
            }
            print(json.dumps(result, indent=2))
        else:
            print_human_audit(stage, planned, audit_data)

        sys.exit(0 if audit_data["status"] == "ok" else 1)

    # 3. Non-Interactive Apply Mode (--apply-json, --connectors, --set)
    updates = {}
    is_apply_mode = (args.apply_json is not None) or bool(args.connectors) or bool(args.set)
    if args.apply_json is not None:
        try:
            payload = json.loads(args.apply_json)
        except Exception as e:
            print(f"Error: Invalid JSON payload in --apply-json: {e}", file=sys.stderr)
            sys.exit(1)
        if not isinstance(payload, dict):
            print("Error: --apply-json payload must be a JSON object", file=sys.stderr)
            sys.exit(1)
        updates.update(payload)

    if args.connectors:
        selected_connectors = [c.strip() for c in args.connectors.split(",") if c.strip()]
        updates["planned_connectors"] = selected_connectors

    for item in args.set:
        pairs = item.split(",")
        for pair in pairs:
            if "=" in pair:
                k, v = pair.split("=", 1)
                k = k.strip()
                v = v.strip()
                if v.lower() == "true":
                    updates[k] = True
                elif v.lower() == "false":
                    updates[k] = False
                elif v.lower() == "null":
                    updates[k] = None
                elif v.isdigit():
                    updates[k] = int(v)
                else:
                    updates[k] = v

    if is_apply_mode:
        # Validate planned_connectors if specified
        if "planned_connectors" in updates:
            planned = updates["planned_connectors"]
            if not isinstance(planned, list):
                print("Error: planned_connectors must be a list of strings", file=sys.stderr)
                sys.exit(1)
            valid_set = {"workspace", "jira", "people_directory"}
            for c in planned:
                if c not in valid_set:
                    print(f"Error: Invalid connector '{c}'. Allowed: 'workspace', 'jira', 'people_directory'", file=sys.stderr)
                    sys.exit(1)

        stage = determine_stage(workdir, state_path, tfvars_path)
        update_tfvars(tfvars_path, updates, stage=stage, allow_enable=False, workdir=workdir)

        if args.json:
            print(json.dumps({
                "status": "applied",
                "stage": stage,
                "applied_updates": updates
            }, indent=2))
        else:
            print(f"[SUCCESS] Applied configuration updates to {tfvars_path}.")
            if stage == 0:
                print("Stage 0 Safety Guard enforced: enable_* flags set to false.")
        sys.exit(0)

    # 4. Mode B: Interactive Onboarding Wizard
    stage = determine_stage(workdir, state_path, tfvars_path)
    tfvars = parse_tfvars(tfvars_path) or {}
    current_planned = tfvars.get("planned_connectors", ["workspace"])

    prompt_title = "Select planned enterprise connectors for Gemini Enterprise:"
    if args.non_interactive or not sys.stdin.isatty():
        chosen_connectors = fallback_combo_box(prompt_title, CONNECTOR_OPTIONS, current_planned)
    else:
        chosen_connectors = interactive_combo_box(prompt_title, CONNECTOR_OPTIONS, current_planned)

    wizard_updates = {
        "planned_connectors": chosen_connectors
    }

    # If Jira is planned, prompt for site URI if missing/placeholder
    if "jira" in chosen_connectors:
        existing_uri = tfvars.get("jira_config", {}).get("instance_uri") or tfvars.get("jira_instance_uri") or ""
        if is_placeholder(existing_uri) and sys.stdin.isatty():
            print("\nJira Cloud Onboarding:")
            print("Enter Atlassian Jira site URL (e.g. https://your-site.atlassian.net), '?' for help, or Enter to skip:")
            sys.stdout.write("Jira site URL: ")
            sys.stdout.flush()
            line = sys.stdin.readline().strip()
            if line == "?":
                print_boxed_help()
                sys.stdout.write("Jira site URL: ")
                sys.stdout.flush()
                line = sys.stdin.readline().strip()
            if line and not is_placeholder(line):
                wizard_updates["jira_instance_uri"] = line

    update_tfvars(tfvars_path, wizard_updates, stage=stage, allow_enable=False, workdir=workdir)

    print()
    print("=" * 80)
    print(f"[SUCCESS] Configuration saved to {tfvars_path}:")
    print(f"  • planned_connectors               = {json.dumps(chosen_connectors)}")
    print(f"  • enable_connectors                = false (Stage 0 safety)")
    print(f"  • enable_jira_connector            = false (Stage 0 safety)")
    print(f"  • enable_people_directory_connector = false (Stage 0 safety)")
    print("=" * 80)

    updated_tfvars = parse_tfvars(tfvars_path) or {}
    audit_data = audit_inputs(updated_tfvars, chosen_connectors, workdir=workdir)
    print_human_audit(stage, chosen_connectors, audit_data)
    sys.exit(0)


if __name__ == "__main__":
    main()
