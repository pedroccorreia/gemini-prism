#!/usr/bin/env python3
"""
Allocate, distribute, and manage Gemini Enterprise seat licenses across GCP customer environment projects.
"""

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request


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
    print("Error obtaining GCP access token via gcloud.", file=sys.stderr)
    print("Please ensure you are authenticated: run 'gcloud auth application-default login' or 'gcloud auth login'", file=sys.stderr)
    sys.exit(1)


def make_request(url, method="GET", body=None, token=None, project_id=None, max_retries=5, backoff_factor=1.5):
    """
    Execute REST API request to Google Cloud APIs with exponential backoff on transient errors.
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    if project_id:
        headers["x-goog-user-project"] = project_id

    data = json.dumps(body).encode("utf-8") if body else None

    attempt = 0
    while True:
        attempt += 1
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req) as resp:
                content = resp.read().decode("utf-8")
                return json.loads(content) if content else {}
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8")
            # Retry on rate limit (429) or transient server errors (500, 502, 503, 504)
            if e.code in (429, 500, 502, 503, 504) and attempt <= max_retries:
                sleep_sec = backoff_factor ** attempt
                print(f"  [WARN] HTTP {e.code} for {url}. Retrying in {sleep_sec:.1f}s (attempt {attempt}/{max_retries})...", file=sys.stderr)
                time.sleep(sleep_sec)
                continue
            print(f"HTTP Error {e.code} for {url}: {err_body}", file=sys.stderr)
            raise RuntimeError(f"GCP API request failed: HTTP {e.code} - {err_body}") from e
        except urllib.error.URLError as e:
            if attempt <= max_retries:
                sleep_sec = backoff_factor ** attempt
                print(f"  [WARN] Network error for {url}: {e.reason}. Retrying in {sleep_sec:.1f}s (attempt {attempt}/{max_retries})...", file=sys.stderr)
                time.sleep(sleep_sec)
                continue
            print(f"Network request failed for {url}: {e.reason}", file=sys.stderr)
            raise RuntimeError(f"Network error calling {url}: {e.reason}") from e
        except Exception as e:
            print(f"Unexpected request failure for {url}: {e}", file=sys.stderr)
            raise


def poll_operation(operation_name, token, central_project=None, timeout_sec=180, poll_interval=3):
    """
    Poll a Google Cloud Discovery Engine long-running operation until completion.
    """
    url = f"https://discoveryengine.googleapis.com/v1beta/{operation_name}"
    elapsed = 0
    print(f"  • Polling operation {operation_name}...")

    while elapsed < timeout_sec:
        res = make_request(url, method="GET", token=token, project_id=central_project)
        if res.get("done"):
            if "error" in res:
                err_msg = res["error"].get("message", "Unknown error")
                err_code = res["error"].get("code", "UNKNOWN")
                raise RuntimeError(f"Operation {operation_name} failed with [{err_code}]: {err_msg}")
            print(f"  • Operation completed successfully.")
            return res.get("response", {})
        time.sleep(poll_interval)
        elapsed += poll_interval

    raise TimeoutError(f"Operation {operation_name} timed out after {timeout_sec} seconds")


def get_license_configs(project_id, location, token):
    """Fetch all licenseConfigs for the given project."""
    url = f"https://discoveryengine.googleapis.com/v1beta/projects/{project_id}/locations/{location}/licenseConfigs"
    res = make_request(url, token=token, project_id=project_id)
    return res.get("licenseConfigs", [])


def get_billing_account_license_config(billing_account, license_config_id, token, central_project):
    """Fetch details of the Billing Account level license config (falling back to central_project licenseConfig)."""
    url = f"https://discoveryengine.googleapis.com/v1alpha/billingAccounts/{billing_account}/billingAccountLicenseConfigs/{license_config_id}"
    try:
        return make_request(url, token=token, project_id=central_project)
    except Exception as orig_err:
        if central_project:
            try:
                fallback_url = f"https://discoveryengine.googleapis.com/v1beta/projects/{central_project}/locations/global/licenseConfigs/{license_config_id}"
                return make_request(fallback_url, token=token, project_id=central_project)
            except Exception:
                pass
        raise orig_err


def get_project_metadata(project_id, token):
    """Query Cloud Resource Manager API to retrieve project number and status."""
    url = f"https://cloudresourcemanager.googleapis.com/v1/projects/{project_id}"
    return make_request(url, token=token)


def run_preflight_assertions(allocations, billing_account, license_config_id, central_project, location, token, dry_run=False):
    """
    Verify project numbers match GCP project numbers and verify billing pool capacity.
    Fails loudly if any assertion fails.
    """
    print("\n-------------------------------------------------------")
    print(" Running Preflight Assertions")
    print("-------------------------------------------------------")

    # 1. Check Project Number match for each allocation
    for item in allocations:
        p_id = item.get("project_id")
        p_num = item.get("project_number")
        if not p_id or not p_num:
            raise ValueError(f"Preflight assertion failed: Missing 'project_id' or 'project_number' in allocation: {item}")

        expected_number = str(p_num).strip()
        print(f"  • Verifying project '{p_id}' matches expected Project Number {expected_number}...")

        try:
            metadata = get_project_metadata(p_id, token)
        except Exception as e:
            raise RuntimeError(f"Preflight assertion failed: Unable to fetch GCP metadata for project '{p_id}': {e}") from e

        actual_number = str(metadata.get("projectNumber", "")).strip()
        lifecycle_state = metadata.get("lifecycleState", "UNKNOWN")

        if lifecycle_state != "ACTIVE":
            raise ValueError(f"Preflight assertion failed: Project '{p_id}' lifecycle state is '{lifecycle_state}' (expected ACTIVE)!")

        if actual_number != expected_number:
            raise ValueError(
                f"Preflight assertion failed for project '{p_id}':\n"
                f"  Expected Project Number: {expected_number}\n"
                f"  Actual GCP Project Number: {actual_number}\n"
                f"  Resolution: Update configuration to match current GCP project state."
            )
        print(f"    [PASS] Project '{p_id}' verified (Number: {actual_number}, State: {lifecycle_state})")

    # 2. Check Billing Account Pool capacity
    print(f"\n  • Checking Billing Account pool '{billing_account}' / License Config '{license_config_id}'...")
    try:
        pool_cfg = get_billing_account_license_config(billing_account, license_config_id, token, central_project)
    except Exception as e:
        raise RuntimeError(
            f"Preflight assertion failed: Unable to query Billing Account License Config '{license_config_id}' "
            f"on Billing Account '{billing_account}': {e}"
        ) from e

    total_capacity = int(pool_cfg.get("licenseCount", "0"))
    available_capacity = pool_cfg.get("availableLicenseCount")

    total_requested_seats = sum(int(item.get("seat_count", 0)) for item in allocations)

    print(f"    Total Pool Capacity : {total_capacity}")
    if available_capacity is not None:
        available_seats = int(available_capacity)
        print(f"    Available Seats     : {available_seats}")
        print(f"    Requested Seats     : {total_requested_seats}")
        if total_requested_seats > available_seats:
            raise ValueError(
                f"Preflight assertion failed: Insufficient license seats in billing pool!\n"
                f"  Requested: {total_requested_seats}\n"
                f"  Available: {available_seats}\n"
                f"  Total Capacity: {total_capacity}"
            )
    else:
        print(f"    Requested Seats     : {total_requested_seats}")

    print("  [PASS] All preflight assertions passed.\n")


def list_allocations(central_project_id, location, token, config_data, json_output=False):
    """Display detailed summary of billing subscription and customer environment seat distributions."""
    billing_account = config_data.get("billing_account")
    sub_id = config_data.get("subscription_id", "N/A")
    sub_tier = config_data.get("subscription_tier", "Gemini Enterprise")
    lic_config = config_data.get("license_config_id", "N/A")

    allocations = config_data.get("allocations", [])
    results = []

    for item in allocations:
        p_id = item.get("project_id", "unknown")
        p_num = item.get("project_number", "")
        env_label = item.get("environment_name") or item.get("environment") or p_id
        target_seats = item.get("seat_count", 0)

        entry = {
            "project_id": p_id,
            "project_number": p_num,
            "environment": env_label,
            "target_seats": target_seats,
            "active_config": None,
            "allocated_seats": 0,
            "state": "NO_CONFIG"
        }

        try:
            cfgs = get_license_configs(p_id, location, token)
            active_cfg = (
                next((c for c in cfgs if c.get("state") == "ACTIVE" and not c.get("freeTrial")), None)
                or next((c for c in cfgs if c.get("state") == "ACTIVE"), None)
            )
            if active_cfg:
                cfg_name = active_cfg.get("name", "").split("/")[-1]
                count = int(active_cfg.get("licenseCount", "0"))
                state = active_cfg.get("state", "UNKNOWN")
                entry["active_config"] = active_cfg.get("name")
                entry["allocated_seats"] = count
                entry["state"] = state
            else:
                entry["state"] = "SKIPPED_0_SEATS" if target_seats == 0 else "NO_ACTIVE_CONFIG"
        except Exception as e:
            entry["state"] = f"ERROR: {e}"

        results.append(entry)

    if json_output:
        payload = {
            "billing_account": billing_account,
            "license_config_id": lic_config,
            "subscription_id": sub_id,
            "subscription_tier": sub_tier,
            "location": location,
            "allocations": results
        }
        print(json.dumps(payload, indent=2))
        return

    print(f"\n=======================================================")
    print(f" Gemini Enterprise Licensing Summary")
    print(f"=======================================================\n")
    print(f"Billing Account      : {billing_account}")
    print(f"License Config ID    : {lic_config}")
    print(f"Subscription ID      : {sub_id}")
    print(f"Subscription Tier    : {sub_tier}")
    print(f"Location             : {location}\n")

    print("Customer Environment Projects & Seat Allocations:")
    for entry in results:
        env_label = entry["environment"]
        p_id = entry["project_id"]
        p_num = entry["project_number"]
        if entry["active_config"]:
            cfg_name = entry["active_config"].split("/")[-1]
            print(f"  • {env_label:<16} | Project: {p_id:<22} (Project #{p_num}) | Seats: {entry['allocated_seats']} ({entry['state']}) | Config: {cfg_name}")
        else:
            print(f"  • {env_label:<16} | Project: {p_id:<22} (Project #{p_num}) | Status: {entry['state']}")
    print()


def emit_tfvars(allocations, location, token):
    """
    Query active license configs for all allocated projects and output
    the license_config_names block for terraform.tfvars.
    """
    lines = ["license_config_names = {"]
    found_any = False

    for item in allocations:
        p_id = item.get("project_id")
        env_key = item.get("environment") or p_id
        if not p_id:
            continue
        try:
            cfgs = get_license_configs(p_id, location, token)
            active_cfg = (
                next((c for c in cfgs if c.get("state") == "ACTIVE" and not c.get("freeTrial")), None)
                or next((c for c in cfgs if c.get("state") == "ACTIVE"), None)
            )
            if active_cfg:
                full_name = active_cfg.get("name")
                lines.append(f'  "{env_key}" = "{full_name}"')
                found_any = True
        except Exception as e:
            print(f"# Warning: error querying project '{p_id}': {e}", file=sys.stderr)

    lines.append("}")
    output_str = "\n".join(lines)

    if found_any:
        print("\n# Copy the following block into terraform.tfvars to manage user store defaults declaratively:")
        print(output_str)
        print()
    else:
        print("# No active license configs found on projects yet. Run --distribute first.", file=sys.stderr)
        print(output_str)

    return output_str


def distribute_license_config(billing_account, license_config_id, project_number, seat_count, token, central_project, location="global", dry_run=False):
    """Distribute licenseConfig seats from Billing Account level to target GCP project number with retry/backoff."""
    url = f"https://discoveryengine.googleapis.com/v1alpha/billingAccounts/{billing_account}/billingAccountLicenseConfigs/{license_config_id}:distributeLicenseConfig"
    payload = {
        "projectNumber": str(project_number),
        "location": location,
        "licenseCount": str(seat_count)
    }
    print(f"  • Distributing {seat_count} seat(s) to Project Number {project_number}...")
    if dry_run:
        print("    [DRY RUN] Skipped actual API distribution call.")
        return {}

    try:
        response = make_request(url, method="POST", body=payload, token=token, project_id=central_project)
    except RuntimeError as e:
        if ("HTTP 404" in str(e) or "HTTP 403" in str(e)) and license_config_id in ("internal_gemini_ent_plus", "free_trial_gemini"):
            import datetime
            today = datetime.date.today()
            next_year = today.replace(year=today.year + 1)
            fallback_url = f"https://discoveryengine.googleapis.com/v1alpha/projects/{project_number}/locations/{location}/licenseConfigs?licenseConfigId={license_config_id}"
            fallback_body = {
                "licenseCount": str(seat_count),
                "subscriptionTier": "SUBSCRIPTION_TIER_SEARCH_AND_ASSISTANT",
                "startDate": {"year": today.year, "month": today.month, "day": today.day},
                "endDate": {"year": next_year.year, "month": next_year.month, "day": next_year.day},
                "subscriptionTerm": "SUBSCRIPTION_TERM_ONE_YEAR",
                "autoRenew": True,
                "freeTrial": True
            }
            response = make_request(fallback_url, method="POST", body=fallback_body, token=token, project_id=str(project_number))
        else:
            raise

    # If the response returned an asynchronous Operation, poll it to completion
    if "name" in response and ("operations/" in response["name"] or response.get("done") is False):
        return poll_operation(response["name"], token=token, central_project=central_project)

    return response


def configure_auto_register(target_project_id, location, full_license_config_name, token, seat_count=None, dry_run=False):
    """Configure default_user_store on target project to enable automatic license registration on user login."""
    url = f"https://discoveryengine.googleapis.com/v1beta/projects/{target_project_id}/locations/{location}/userStores/default_user_store?updateMask=defaultLicenseConfig,enableLicenseAutoRegister,enableExpiredLicenseAutoUpdate"
    payload = {
        "defaultLicenseConfig": full_license_config_name,
        "enableLicenseAutoRegister": True,
        "enableExpiredLicenseAutoUpdate": True
    }

    cfg_short = full_license_config_name.split("/")[-1]
    quota_str = f" [Seats: {seat_count}]" if seat_count is not None else ""
    print(f"  • Project: {target_project_id:<22}{quota_str:<15} -> Setting defaultLicenseConfig: {cfg_short} (Auto-Register: ON)")
    if dry_run:
        return {}

    return make_request(url, method="PATCH", body=payload, token=token, project_id=target_project_id)


def load_config(config_file):
    """Load configuration from JSON file with strict validation."""
    if not os.path.exists(config_file):
        raise FileNotFoundError(f"Configuration file not found: {config_file}")
    with open(config_file, "r") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format in {config_file}: {e}") from e

    if not isinstance(data, dict):
        raise ValueError(f"Invalid configuration format in {config_file}: root must be a JSON object")

    required_fields = ["billing_account", "subscription_id", "allocations"]
    missing = [f for f in required_fields if f not in data or data[f] is None or data[f] == ""]
    if missing:
        raise ValueError(f"Missing required field(s) in {config_file}: {', '.join(missing)}")

    if not isinstance(data["allocations"], list):
        raise ValueError(f"Invalid 'allocations' in {config_file}: must be a list of allocation objects")

    return data


def validate_required_params(billing_account, license_config_id, project_id):
    """Ensure all required identification parameters are explicitly provided."""
    missing = []
    if not billing_account:
        missing.append("billing_account (--billing-account or config file)")
    if not license_config_id:
        missing.append("license_config_id (--license-config or config file)")
    if not project_id:
        missing.append("licensing_project (--project or config file)")

    if missing:
        print(f"Error: Missing required parameters: {', '.join(missing)}", file=sys.stderr)
        print("Please provide them via CLI arguments or through the configuration file.", file=sys.stderr)
        sys.exit(1)


def discover_billing_subscriptions(billing_account, central_project, token, json_output=False):
    """Discover all billingAccountLicenseConfigs on a Billing Account via v1alpha (with project-level fallback)."""
    url = f"https://discoveryengine.googleapis.com/v1alpha/billingAccounts/{billing_account}/billingAccountLicenseConfigs"
    res = make_request(url, token=token, project_id=central_project)
    cfgs = res.get("billingAccountLicenseConfigs", [])
    if not cfgs and central_project:
        try:
            cfgs = get_license_configs(central_project, "global", token)
        except Exception:
            cfgs = []

    if json_output:
        print(json.dumps(cfgs, indent=2))
        return cfgs

    print(f"\n=======================================================")
    print(f" Discovered Billing Account Subscriptions ({billing_account})")
    print(f"=======================================================\n")
    for c in cfgs:
        lic_id = c.get("name", "").split("/")[-1]
        sub_id = c.get("subscriptionName", "").split("/")[-1] or c.get("name", "")
        disp = c.get("subscriptionDisplayName") or c.get("subscriptionTier") or "N/A"
        state = c.get("state", "UNKNOWN")
        seats = c.get("licenseCount", "0")
        print(f"  • Display Name      : {disp} [{state}] (Seats: {seats})")
        print(f"    license_config_id = \"{lic_id}\"")
        print(f"    subscription_id   = \"{sub_id}\"\n")
    return cfgs


def main():
    parser = argparse.ArgumentParser(description="Distribute and configure Gemini Enterprise licenses across GCP customer environment projects.")
    parser.add_argument("--discover", action="store_true", help="Discover subscription_id and license_config_id from the Billing Account.")
    parser.add_argument("--list", action="store_true", help="List license configs and seat quotas across all customer environment projects.")
    parser.add_argument("--distribute", action="store_true", help="Distribute subscription seats from Billing Account to project numbers.")
    parser.add_argument("--configure-auto-register", action="store_true", help="Configure projects to auto-provision licenses upon user login.")
    parser.add_argument("--retract", action="store_true", help="Retract distributed licenses back to the Billing Account pool.")
    parser.add_argument("--config-file", default="config/license_allocations.json", help="Path to JSON configuration file.")
    parser.add_argument("--billing-account", help="Override Billing Account ID.")
    parser.add_argument("--license-config", help="Override Billing Account License Config ID.")
    parser.add_argument("--project", help="Override caller GCP Project ID for quota/billing.")
    parser.add_argument("--location", default="global", help="GCP Location (default: global).")
    parser.add_argument("--target-project", help="Target project ID for single project operations.")
    parser.add_argument("--dry-run", action="store_true", help="Simulate changes without calling GCP write endpoints.")
    parser.add_argument("--skip-preflight", action="store_true", help="Skip preflight assertion checks.")
    parser.add_argument("--json", action="store_true", help="Output summary in JSON format.")
    parser.add_argument("--emit-tfvars", action="store_true", help="Emit license_config_names HCL block for terraform.tfvars.")

    args = parser.parse_args()

    # Load configuration (allow --discover with explicit --billing-account before Stage 1 creates config_file)
    if args.discover and args.billing_account and not os.path.exists(args.config_file):
        config_data = {}
    else:
        try:
            config_data = load_config(args.config_file)
        except Exception as e:
            print(f"Error loading configuration: {e}", file=sys.stderr)
            sys.exit(1)

    project_id = args.project or config_data.get("licensing_project")
    billing_account = args.billing_account or config_data.get("billing_account")
    license_config_id = args.license_config or config_data.get("license_config_id")
    location = args.location or config_data.get("location") or "global"
    allocations = config_data.get("allocations", [])

    if not args.discover and not args.list and not args.distribute and not args.configure_auto_register and not args.retract and not args.emit_tfvars:
        parser.print_help()
        print("\nNote: Specify at least one action: --discover, --list, --distribute, --configure-auto-register, --retract, or --emit-tfvars.")
        sys.exit(1)

    token = get_access_token()

    if args.discover:
        discover_billing_subscriptions(billing_account, project_id, token, json_output=args.json)
        return

    # Validate essential identifiers
    validate_required_params(billing_account, license_config_id, project_id)

    if args.emit_tfvars:
        emit_tfvars(allocations, location, token)
        return

    if args.list:
        list_allocations(project_id, location, token, config_data=config_data, json_output=args.json)
        return

    # Run Preflight Assertions for state-modifying actions
    if not args.skip_preflight and (args.distribute or args.configure_auto_register):
        try:
            run_preflight_assertions(
                allocations=allocations,
                billing_account=billing_account,
                license_config_id=license_config_id,
                central_project=project_id,
                location=location,
                token=token,
                dry_run=args.dry_run
            )
        except Exception as e:
            print(f"\n[FATAL] Preflight check failed: {e}", file=sys.stderr)
            sys.exit(1)

    # If --distribute is requested
    if args.distribute:
        print(f"\n=======================================================")
        print(f" Prism: Distributing Subscription Seats from Billing Pool")
        print(f" Billing Account : {billing_account}")
        print(f" License Config  : {license_config_id}")
        print(f"=======================================================\n")

        for item in allocations:
            p_id = item.get("project_id")
            p_num = item.get("project_number")
            seats = item.get("seat_count", 0)

            if p_num and seats > 0:
                print(f"Project: {p_id:<22} (Project #{p_num}) - Allocating {seats} seat(s)")
                try:
                    existing_cfgs = get_license_configs(p_id, location, token) if p_id else []
                    active_cfg = (
                        next((c for c in existing_cfgs if c.get("state") == "ACTIVE" and not c.get("freeTrial")), None)
                        or (
                            next((c for c in existing_cfgs if c.get("state") == "ACTIVE"), None)
                            if license_config_id in ("internal_gemini_ent_plus", "free_trial_gemini")
                            else None
                        )
                    )
                    if active_cfg and int(active_cfg.get("licenseCount", "0")) >= int(seats):
                        cfg_short = active_cfg.get("name", "").split("/")[-1]
                        print(f"  • Already distributed ({active_cfg.get('licenseCount')} seat(s) active in {cfg_short}) — skipping duplicate distribution.")
                    else:
                        distribute_license_config(
                            billing_account=billing_account,
                            license_config_id=license_config_id,
                            project_number=p_num,
                            seat_count=seats,
                            token=token,
                            central_project=project_id,
                            location=location,
                            dry_run=args.dry_run
                        )
                except Exception as e:
                    print(f"\n[FATAL] Failed distributing licenses to {p_id}: {e}", file=sys.stderr)
                    sys.exit(1)
            elif p_num:
                print(f"Project: {p_id:<22} (Project #{p_num}) - Skipped (0 seats)")

        if args.dry_run:
            print("\n[DRY RUN] No distribution changes executed.")
        else:
            print("\nSeat distribution successfully completed across projects!")
        return

    # If --configure-auto-register is requested
    if args.configure_auto_register:
        print(f"\n=======================================================")
        print(f" Configuring Auto-Registration on User Login")
        print(f"=======================================================\n")

        target_projects = [args.target_project] if args.target_project else [item.get("project_id") for item in allocations if item.get("seat_count", 0) > 0]

        for t_proj in target_projects:
            if not t_proj:
                continue
            try:
                cfgs = get_license_configs(t_proj, location, token)
            except Exception as e:
                print(f"  • Project: {t_proj:<22} -> Error retrieving license configs: {e}", file=sys.stderr)
                continue

            active_cfg = (
                next((c for c in cfgs if c.get("state") == "ACTIVE" and not c.get("freeTrial")), None)
                or (
                    next((c for c in cfgs if c.get("state") == "ACTIVE"), None)
                    if license_config_id in ("internal_gemini_ent_plus", "free_trial_gemini")
                    else None
                )
            )
            if not active_cfg:
                print(f"  • Project: {t_proj:<22} -> Skipping (No active distributed licenseConfig found)")
                continue

            full_cfg_name = active_cfg["name"]
            seat_count = active_cfg.get("licenseCount", "1")
            try:
                configure_auto_register(t_proj, location, full_cfg_name, token, seat_count=seat_count, dry_run=args.dry_run)
            except Exception as e:
                print(f"\n[FATAL] Failed configuring auto-registration for {t_proj}: {e}", file=sys.stderr)
                sys.exit(1)

        if not args.target_project:
            for item in allocations:
                if item.get("seat_count", 0) == 0:
                    print(f"  • Project: {item.get('project_id'):<22} -> Skipped (0 seats allocated)")

        if args.dry_run:
            print("\n[DRY RUN] No changes executed.")
        else:
            print("\nAuto-registration configuration successfully applied to all target projects!")
        return

    # If --retract is requested
    if args.retract:
        print(f"\n=======================================================")
        print(f" Retracting Subscription Seats back to Billing Account")
        print(f" Billing Account : {billing_account}")
        print(f" License Config  : {license_config_id}")
        print(f"=======================================================\n")

        target_projects = [args.target_project] if args.target_project else [item.get("project_id") for item in allocations]

        for t_proj in target_projects:
            if not t_proj:
                continue
            try:
                cfgs = get_license_configs(t_proj, location, token)
            except Exception as e:
                print(f"  • Project: {t_proj:<22} -> Error retrieving license configs: {e}", file=sys.stderr)
                continue

            active_cfg = next((c for c in cfgs if c.get("state") == "ACTIVE" and not c.get("freeTrial")), None)
            if active_cfg:
                full_cfg_name = active_cfg["name"]
                print(f"  • Retracting license from {t_proj} ({full_cfg_name.split('/')[-1]})...")
                if not args.dry_run:
                    retract_url = f"https://discoveryengine.googleapis.com/v1alpha/billingAccounts/{billing_account}/billingAccountLicenseConfigs/{license_config_id}:retractLicenseConfig"
                    try:
                        make_request(retract_url, method="POST", body={"licenseConfig": full_cfg_name, "fullRetract": True}, token=token, project_id=project_id)
                    except Exception as e:
                        print(f"  [ERROR] Failed to retract license for {t_proj}: {e}", file=sys.stderr)

        if args.dry_run:
            print("\n[DRY RUN] No changes executed.")
        else:
            print("\nRetraction complete.")
        return


if __name__ == "__main__":
    main()
