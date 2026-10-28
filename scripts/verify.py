#!/usr/bin/env python3
"""
Post-deployment verification script for Gemini Enterprise customer environments.
Checks connectors, search engine, assistant, user store, and license configs.
Supports polling via --wait (e.g. 15m) and JSON output via --json.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request


GEAP_FOUNDATION_APIS = [
    "serviceusage.googleapis.com",
    "agentregistry.googleapis.com",
    "agentidentity.googleapis.com",
    "aiplatform.googleapis.com",
    "networkservices.googleapis.com",
    "networksecurity.googleapis.com",
    "iap.googleapis.com",
    "modelarmor.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "cloudtrace.googleapis.com",
    "telemetry.googleapis.com",
    "observability.googleapis.com",
    "apphub.googleapis.com",
    "cloudasset.googleapis.com",
    "apptopology.googleapis.com",
]


def detect_governance_mode(tfvars_path="terraform.tfvars"):
    """Detect geap_governance_mode ('none' or 'foundation') from terraform.tfvars."""
    if not os.path.exists(tfvars_path):
        return "none"
    try:
        with open(tfvars_path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = re.sub(r'#.*$', '', raw_line)
                m = re.match(r'^\s*geap_governance_mode\s*=\s*"([^"]*)"', line)
                if m:
                    val = m.group(1).strip().lower()
                    return val if val in ("none", "foundation") else "none"
    except Exception:
        pass
    return "none"


def parse_duration(duration_str):
    """Parse duration strings like 15m, 30s, 1h into seconds."""
    if not duration_str:
        return 0
    duration_str = str(duration_str).strip().lower()
    try:
        if duration_str.endswith("s"):
            val = int(duration_str[:-1])
        elif duration_str.endswith("m"):
            val = int(duration_str[:-1]) * 60
        elif duration_str.endswith("h"):
            val = int(duration_str[:-1]) * 3600
        elif duration_str.isdigit():
            val = int(duration_str)
        else:
            raise ValueError()
    except (ValueError, IndexError):
        raise ValueError(f"Invalid duration format: '{duration_str}'. Use e.g. 30s, 15m, 1h")

    if val < 0:
        raise ValueError(f"Duration cannot be negative: '{duration_str}'")
    return val


def get_access_token():
    """Retrieve access token using gcloud auth (preferring Application Default Credentials)."""
    for cmd in (
        ["gcloud", "auth", "application-default", "print-access-token"],
        ["gcloud", "auth", "print-access-token"],
    ):
        try:
            token = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL).strip()
            if token:
                return token
        except Exception:
            continue
    print("Error obtaining GCP access token.", file=sys.stderr)
    print("Please authenticate with 'gcloud auth application-default login' or 'gcloud auth login'", file=sys.stderr)
    sys.exit(1)


def make_request(url, method="GET", body=None, token=None, project_id=None):
    """Execute REST API request to Google Cloud APIs."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    if project_id:
        headers["x-goog-user-project"] = project_id

    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req) as resp:
            content = resp.read().decode("utf-8")
            return json.loads(content) if content else {}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        return {"_error": e.code, "_message": err_body}
    except Exception as e:
        return {"_error": -1, "_message": str(e)}


WORKSPACE_CONNECTOR_SOURCES = {"google_mail", "google_calendar", "google_drive", "google_chat"}


def check_data_connectors(project_id, location, token):
    """Check status of federated data connectors and BAP action configurations."""
    url = f"https://discoveryengine.googleapis.com/v1alpha/projects/{project_id}/locations/{location}/collections"
    cols = make_request(url, token=token, project_id=project_id)
    if "_error" in cols:
        return [("Collections", "ERROR", f"HTTP {cols['_error']}: {cols['_message']}")]

    results = []
    collections = cols.get("collections", [])
    if not collections:
        results.append(("Data Connectors", "WARN", "No collections found in project"))
        return results

    found_connectors = False
    for col in collections:
        col_name = col.get("name", "")
        col_id = col_name.split("/")[-1]
        c_url = f"https://discoveryengine.googleapis.com/v1alpha/{col_name}/dataConnector"
        c_res = make_request(c_url, token=token, project_id=project_id)
        if "_error" in c_res:
            continue
        found_connectors = True
        state = c_res.get("state", "UNKNOWN")
        data_source = c_res.get("dataSource", col_id)
        realtime_state = c_res.get("realtimeState")
        action_state = c_res.get("actionState")
        blocking_reasons = c_res.get("blockingReasons", [])
        entities = c_res.get("entities", [])
        errors = c_res.get("errors", [])
        connector_modes = c_res.get("connectorModes", [])
        action_config = c_res.get("actionConfig", {}) or {}
        is_action_configured = bool(action_config.get("isActionConfigured"))
        bap_config = c_res.get("bapConfig", {}) or {}
        enabled_actions = bap_config.get("enabledActions", []) or []

        details_parts = [f"Collection: {col_id}"]
        if connector_modes:
            details_parts.append(f"Modes: {','.join(connector_modes)}")
        if entities:
            details_parts.append(f"Entities: {len(entities)}")
        if realtime_state:
            details_parts.append(f"Realtime: {realtime_state}")
        if action_state:
            details_parts.append(f"ActionState: {action_state}")
        if "ACTIONS" in connector_modes:
            details_parts.append(f"ActionConfigured: {is_action_configured}")
        if enabled_actions:
            details_parts.append(f"Actions: {len(enabled_actions)}")
        if data_source in WORKSPACE_CONNECTOR_SOURCES and "ACTIONS" in connector_modes:
            if not is_action_configured or action_state != "ACTIVE":
                details_parts.append(
                    "ActionsPending: Run 'python3 scripts/configure.py --sync-workspace-actions' with 3LO OAuth credentials"
                )
        if blocking_reasons:
            details_parts.append(f"Blocking: {','.join(blocking_reasons)}")
        if errors:
            details_parts.append(f"Errors: {len(errors)}")

        status = state
        if errors or state in ("FAILED", "ERROR", "INITIALIZATION_FAILED") or "FAIL" in state:
            status = "ERROR"
        elif blocking_reasons or state in ("PAUSED", "INITIALIZING") or ("ACTIONS" in connector_modes and (not is_action_configured or action_state != "ACTIVE")):
            status = "WARN"

        results.append((f"Connector ({data_source})", status, ", ".join(details_parts)))

    if not found_connectors:
        results.append(("Data Connectors", "WARN", "No active data connectors found (enable_connectors, enable_jira_connector, enable_confluence_connector, enable_slack_connector, enable_people_directory_connector, or enable_hubspot_connector may be false)"))

    return results


def check_search_engine(project_id, location, token):
    """Check search engine configuration."""
    url = f"https://discoveryengine.googleapis.com/v1beta/projects/{project_id}/locations/{location}/collections/default_collection/engines"
    res = make_request(url, token=token, project_id=project_id)
    if "_error" in res:
        return [("Search Engine", "ERROR", f"HTTP {res['_error']}: {res['_message']}")]

    engines = res.get("engines", [])
    if not engines:
        return [("Search Engine", "WARN", "No search engine provisioned in default_collection")]

    results = []
    for eng in engines:
        eng_id = eng.get("name", "").split("/")[-1]
        disp_name = eng.get("displayName", eng_id)
        data_stores = eng.get("dataStoreIds", [])
        results.append((f"Search App ({eng_id})", "ACTIVE", f"DisplayName: '{disp_name}', DataStores: {len(data_stores)}"))
    return results


def check_assistant(project_id, location, token):
    """Check governed assistant configuration."""
    url = f"https://discoveryengine.googleapis.com/v1beta/projects/{project_id}/locations/{location}/collections/default_collection/engines"
    engines_res = make_request(url, token=token, project_id=project_id)
    if "_error" in engines_res or not engines_res.get("engines"):
        return [("Assistant", "SKIPPED", "No search engine available")]

    results = []
    for eng in engines_res.get("engines", []):
        eng_name = eng.get("name")
        a_url = f"https://discoveryengine.googleapis.com/v1alpha/{eng_name}/assistants/default_assistant"
        a_res = make_request(a_url, token=token, project_id=project_id)
        if "_error" in a_res:
            results.append(("Assistant (default_assistant)", "WARN", f"Not found or inaccessible (HTTP {a_res['_error']})"))
        else:
            grounding = a_res.get("webGroundingType", "DISABLED")
            enabled_tools_map = a_res.get("enabledTools", {}) or {}
            enabled_tool_names = [
                ti.get("toolName")
                for v in enabled_tools_map.values()
                for ti in (v or {}).get("toolInfo", [])
                if isinstance(ti, dict) and ti.get("toolName")
            ]
            details = f"Web Grounding: {grounding}"
            if enabled_tool_names:
                details += f", EnabledTools: {','.join(enabled_tool_names)}"
            results.append(("Assistant (default_assistant)", "ACTIVE", details))
    return results


def check_user_store(project_id, location, token):
    """Check default_user_store auto-registration settings."""
    url = f"https://discoveryengine.googleapis.com/v1beta/projects/{project_id}/locations/{location}/userStores/default_user_store"
    res = make_request(url, token=token, project_id=project_id)
    if "_error" in res:
        return [("User Store", "ERROR", f"HTTP {res['_error']}: {res['_message']}")]

    auto_reg = res.get("enableLicenseAutoRegister", False)
    auto_update = res.get("enableExpiredLicenseAutoUpdate", False)
    def_cfg = res.get("defaultLicenseConfig", "None")
    cfg_short = def_cfg.split("/")[-1] if def_cfg else "None"

    status = "ACTIVE" if auto_reg else "WARN"
    details = f"Auto-Register: {auto_reg}, Auto-Update: {auto_update}, DefaultConfig: {cfg_short}"
    return [("User Store (default_user_store)", status, details)]


def check_license_configs(project_id, location, token):
    """Check project-level license configurations."""
    url = f"https://discoveryengine.googleapis.com/v1beta/projects/{project_id}/locations/{location}/licenseConfigs"
    res = make_request(url, token=token, project_id=project_id)
    if "_error" in res:
        return [("License Configs", "ERROR", f"HTTP {res['_error']}: {res['_message']}")]

    cfgs = res.get("licenseConfigs", [])
    if not cfgs:
        return [("License Configs", "WARN", "No distributed license configs found for this project")]

    results = []
    for c in cfgs:
        cfg_name = c.get("name", "").split("/")[-1]
        state = c.get("state", "UNKNOWN")
        seats = c.get("licenseCount", "0")
        results.append((f"License Config ({cfg_name})", state, f"Seats: {seats}"))
    return results


def check_geap_governance(project_id, location, token):
    """Verify GEAP Governance Foundation APIs and Agent Registry control plane reachability."""
    results = []
    su_url = f"https://serviceusage.googleapis.com/v1/projects/{project_id}/services?filter=state:ENABLED&pageSize=200"
    su_res = make_request(su_url, token=token, project_id=project_id)
    if "_error" in su_res:
        results.append(("GEAP Foundation APIs", "ERROR", f"HTTP {su_res['_error']}: {su_res['_message'][:120]}"))
        return results

    enabled_set = set()
    for svc in su_res.get("services", []):
        cfg_name = svc.get("config", {}).get("name")
        if cfg_name:
            enabled_set.add(cfg_name)
        elif svc.get("name"):
            enabled_set.add(svc["name"].split("/")[-1])

    missing = [api for api in GEAP_FOUNDATION_APIS if api not in enabled_set]
    enabled_count = len(GEAP_FOUNDATION_APIS) - len(missing)
    if not missing:
        results.append((
            "GEAP Foundation APIs",
            "ACTIVE",
            f"{enabled_count}/{len(GEAP_FOUNDATION_APIS)} enabled (agentregistry, modelarmor, iap, apptopology...)"
        ))
    else:
        preview = ", ".join(missing[:4]) + ("..." if len(missing) > 4 else "")
        results.append((
            "GEAP Foundation APIs",
            "ERROR",
            f"{enabled_count}/{len(GEAP_FOUNDATION_APIS)} enabled; missing: {preview}"
        ))

    reg_loc = "global"
    reg_url = f"https://agentregistry.googleapis.com/v1alpha/projects/{project_id}/locations/{reg_loc}/agents"
    reg_res = make_request(reg_url, token=token, project_id=project_id)
    if "_error" in reg_res:
        results.append((
            "GEAP Agent Registry",
            "ERROR",
            f"HTTP {reg_res['_error']}: {reg_res['_message'][:120]}"
        ))
    else:
        agents = reg_res.get("agents", [])
        names = [a.get("displayName") or a.get("name", "").split("/")[-1] for a in agents[:3]]
        names_suffix = f" [{', '.join(names)}]" if names else ""
        results.append((
            "GEAP Agent Registry",
            "ACTIVE",
            f"Control plane reachable (Discovered agents: {len(agents)}{names_suffix})"
        ))

    return results


def print_row(component, status, details):
    status_icon = {
        "ACTIVE": "[PASS]",
        "STATE_ACTIVE": "[PASS]",
        "WARN": "[WARN]",
        "ERROR": "[FAIL]",
        "SKIPPED": "[SKIP]"
    }.get(status, f"[{status}]")
    print(f"  {status_icon:<8} | {component:<32} | {details}")


def verify_project(project_id, location, token, expected_seats=None, silent=False, geap_governance_mode="none"):
    all_checks = []
    all_checks.extend(check_user_store(project_id, location, token))
    all_checks.extend(check_license_configs(project_id, location, token))
    all_checks.extend(check_data_connectors(project_id, location, token))
    all_checks.extend(check_search_engine(project_id, location, token))
    all_checks.extend(check_assistant(project_id, location, token))
    if geap_governance_mode == "foundation":
        all_checks.extend(check_geap_governance(project_id, location, token))

    has_failures = False
    for comp, stat, det in all_checks:
        if not silent:
            print_row(comp, stat, det)
        if stat in ("ERROR", "FAIL"):
            has_failures = True

    if not silent:
        console_url = f"https://console.cloud.google.com/gen-app-builder/engines?project={project_id}"
        print(f"\n  • Gemini Enterprise Console : {console_url}")
        if geap_governance_mode == "foundation":
            print(f"  • GEAP Agent Registry       : https://console.cloud.google.com/agent-registry?project={project_id}")
            print(f"  • GEAP Model Armor          : https://console.cloud.google.com/security/model-armor?project={project_id}")
            print(f"  • GEAP Topology Graph       : https://console.cloud.google.com/net-intelligence/topology?project={project_id}")
        print()

    return not has_failures, all_checks


def main():
    parser = argparse.ArgumentParser(description="Verify Gemini Enterprise provisioned components across environments.")
    parser.add_argument("--config-file", default="config/license_allocations.json", help="Path to license allocations configuration file.")
    parser.add_argument("--tfvars-file", default="terraform.tfvars", help="Path to terraform.tfvars file for detecting governance mode.")
    parser.add_argument("--governance-mode", choices=["none", "foundation"], help="Override GEAP governance mode check ('none' or 'foundation').")
    parser.add_argument("--project", help="Verify a single GCP project ID directly.")
    parser.add_argument("--location", default="global", help="Discovery Engine location (default: global).")
    parser.add_argument("--wait", default="0s", help="Wait duration polling for connectors to become ACTIVE (e.g. 15m, 30s).")
    parser.add_argument("--json", action="store_true", help="Output verification summary in JSON format.")

    args = parser.parse_args()
    effective_gov_mode = args.governance_mode or detect_governance_mode(args.tfvars_file)

    try:
        max_wait_seconds = parse_duration(args.wait)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    projects_to_verify = []

    if args.project:
        projects_to_verify.append({"project_id": args.project})
    elif os.path.exists(args.config_file):
        try:
            with open(args.config_file, "r") as f:
                cfg = json.load(f)
                args.location = cfg.get("location", args.location)
                for item in cfg.get("allocations", []):
                    p_id = item.get("project_id")
                    if p_id:
                        projects_to_verify.append({
                            "project_id": p_id,
                            "seat_count": item.get("seat_count", 0)
                        })
        except Exception as e:
            print(f"Error loading configuration file {args.config_file}: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # If user explicitly specified a non-existent config file:
        if args.config_file != "config/license_allocations.json":
            print(f"Error: Configuration file not found: {args.config_file}", file=sys.stderr)
            sys.exit(1)
        # Fallback: query terraform outputs
        try:
            tf_out = subprocess.check_output(["terraform", "output", "-json", "project_ids"], text=True)
            proj_map = json.loads(tf_out)
            for env, p_id in proj_map.items():
                projects_to_verify.append({"project_id": p_id})
        except Exception:
            print("No config file found and could not read terraform output. Specify --project <ID> directly.", file=sys.stderr)
            sys.exit(1)

    if not projects_to_verify:
        print("No projects identified for verification.", file=sys.stderr)
        sys.exit(1)

    token = get_access_token()

    if not args.json:
        print("\nStarting Prism — Gemini Enterprise Post-Deployment Verification...")

    start_time = time.time()
    poll_interval = 15
    json_results = []
    overall_success = True

    while True:
        json_results = []
        overall_success = True

        for proj in projects_to_verify:
            p_id = proj["project_id"]
            if not args.json and max_wait_seconds == 0:
                print(f"\n================================================================================")
                print(f" Verifying Environment Project: {p_id}")
                print(f" Location: {args.location}")
                print(f"================================================================================")

            success, checks = verify_project(
                project_id=p_id,
                location=args.location,
                token=token,
                expected_seats=proj.get("seat_count"),
                silent=args.json or (max_wait_seconds > 0),
                geap_governance_mode=effective_gov_mode,
            )

            if not success:
                overall_success = False

            proj_entry = {
                "project_id": p_id,
                "success": success,
                "geap_governance_mode": effective_gov_mode,
                "checks": [{"component": c[0], "status": c[1], "details": c[2]} for c in checks],
                "console_url": f"https://console.cloud.google.com/gen-app-builder/engines?project={p_id}"
            }
            if effective_gov_mode == "foundation":
                proj_entry["geap_console_urls"] = {
                    "agent_registry": f"https://console.cloud.google.com/agent-registry?project={p_id}",
                    "model_armor": f"https://console.cloud.google.com/security/model-armor?project={p_id}",
                    "topology": f"https://console.cloud.google.com/net-intelligence/topology?project={p_id}",
                }
            json_results.append(proj_entry)

        has_creating = any(
            c["status"] in ("CREATING", "INITIALIZING", "STATE_CREATING", "UPDATING")
            for r in json_results
            for c in r["checks"]
        )
        # If everything succeeded (and nothing is still creating when waiting) or no waiting requested, break
        elapsed = time.time() - start_time
        if (overall_success and not has_creating) or elapsed >= max_wait_seconds:
            break

        if not args.json:
            pending = [
                f"{r['project_id']}:{c['component']}={c['status']}"
                for r in json_results
                for c in r["checks"]
                if c["status"] in ("ERROR", "FAIL", "CREATING", "INITIALIZING", "STATE_CREATING", "UPDATING")
            ]
            pending_str = f" ({', '.join(pending)})" if pending else ""
            print(f"  [WAIT] Components not ready{pending_str}. Waiting {poll_interval}s ({int(elapsed)}s / {max_wait_seconds}s elapsed)...")
        time.sleep(poll_interval)

    # If wait mode was active and not json, print final report
    if max_wait_seconds > 0 and not args.json:
        print("\nFinal Verification Report:")
        for proj_res in json_results:
            print(f"\n================================================================================")
            print(f" Project: {proj_res['project_id']}")
            print(f"================================================================================")
            for c in proj_res["checks"]:
                print_row(c["component"], c["status"], c["details"])
            print(f"\n  • Gemini Enterprise Console : {proj_res['console_url']}")
            if effective_gov_mode == "foundation":
                print(f"  • GEAP Agent Registry       : https://console.cloud.google.com/agent-registry?project={proj_res['project_id']}")
                print(f"  • GEAP Model Armor          : https://console.cloud.google.com/security/model-armor?project={proj_res['project_id']}")
                print(f"  • GEAP Topology Graph       : https://console.cloud.google.com/net-intelligence/topology?project={proj_res['project_id']}")
            print()

    if args.json:
        output_data = {
            "verified": overall_success,
            "projects": json_results
        }
        print(json.dumps(output_data, indent=2))
    else:
        status_msg = "All checks PASSED." if overall_success else "Some checks FAILED or require attention."
        print(f"Verification completed: {status_msg}\n")

    sys.exit(0 if overall_success else 1)


if __name__ == "__main__":
    main()
