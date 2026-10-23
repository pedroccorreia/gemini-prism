#!/usr/bin/env python3
"""
Plan Guard: Safety barrier preventing unintentional destroy or replace actions.
Inspects a Terraform plan and halts execution if any resource deletions or
replacements are detected, unless explicitly authorized via ALLOW_DESTROY=1.
"""

import argparse
import json
import os
import subprocess
import sys

for _p in ["/opt/homebrew/bin", "/usr/local/bin"]:
    if os.path.exists(_p) and _p not in os.environ.get("PATH", ""):
        os.environ["PATH"] = f"{_p}:{os.environ.get('PATH', '')}"


def parse_plan(plan_path, json_file=None):
    """
    Extract plan JSON either directly from a JSON file or by running `terraform show -json`.
    """
    if json_file:
        with open(json_file, "r") as f:
            return json.load(f)

    if not os.path.exists(plan_path):
        raise FileNotFoundError(f"Plan file not found: {plan_path}")

    # Check if the file is already plaintext JSON
    try:
        with open(plan_path, "r") as f:
            content = f.read().strip()
            if content.startswith("{") and content.endswith("}"):
                return json.loads(content)
    except Exception:
        pass

    # Otherwise invoke terraform show -json
    cmd = ["terraform", "show", "-json", plan_path]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(proc.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error reading plan with terraform show: {e.stderr}", file=sys.stderr)
        raise RuntimeError(f"terraform show failed: {e.stderr}") from e
    except json.JSONDecodeError as e:
        print(f"Failed to parse terraform show JSON output: {e}", file=sys.stderr)
        raise


def inspect_plan(plan_data):
    """
    Inspect resource_changes for destructive (delete / replace) operations.
    Returns (destructive_changes, stats_dict).
    """
    resource_changes = plan_data.get("resource_changes", [])
    destructive = []
    stats = {
        "create": 0,
        "update": 0,
        "delete": 0,
        "replace": 0,
        "read": 0,
        "no-op": 0
    }

    for rc in resource_changes:
        address = rc.get("address", "unknown")
        res_type = rc.get("type", "unknown")
        change = rc.get("change", {})
        actions = change.get("actions", [])

        if res_type == "local_file" and "delete" in actions and "create" in actions:
            stats["update"] += 1
            continue

        if "delete" in actions:
            if "create" in actions:
                stats["replace"] += 1
                action_desc = "replace"
            else:
                stats["delete"] += 1
                action_desc = "delete"
            destructive.append({
                "address": address,
                "type": res_type,
                "actions": actions,
                "action_desc": action_desc
            })
        elif "create" in actions:
            stats["create"] += 1
        elif "update" in actions:
            stats["update"] += 1
        elif "read" in actions:
            stats["read"] += 1
        elif "no-op" in actions:
            stats["no-op"] += 1

    return destructive, stats


def guard_plan(plan_path=None, json_file=None, allow_destroy=None):
    """
    Enforces the plan guard policy.
    Returns 0 if safe or authorized, 1 if unsafe destructive actions exist.
    """
    if allow_destroy is None:
        allow_destroy = os.environ.get("ALLOW_DESTROY") == "1"

    try:
        plan_data = parse_plan(plan_path, json_file=json_file)
    except Exception as e:
        print(f"[ERROR] Failed to load plan: {e}", file=sys.stderr)
        return 1

    destructive, stats = inspect_plan(plan_data)

    if destructive:
        print("\n================================================================================")
        print(" [PRISM PLAN GUARD] DESTRUCTIVE CHANGES DETECTED")
        print("================================================================================")
        for item in destructive:
            print(f"  • {item['action_desc'].upper():<8} : {item['address']} ({item['type']})")
        print("================================================================================\n")

        if allow_destroy:
            print("[WARNING] Destructive changes permitted via ALLOW_DESTROY=1. Proceeding with caution.\n")
            return 0
        else:
            print("[ERROR] Refusing execution: Plan contains deletions or replacements.", file=sys.stderr)
            print("Set ALLOW_DESTROY=1 only if you explicitly intend to destroy/replace these resources.\n", file=sys.stderr)
            return 1

    summary_str = f"creates: {stats['create']}, updates: {stats['update']}, no-ops: {stats['no-op']}"
    print(f"[OK] Plan guard passed: 0 deletions or replacements ({summary_str}).")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Guard Terraform plans against unintended deletions and replacements.")
    parser.add_argument("plan_path", nargs="?", default=".plans/foundation.tfplan", help="Path to Terraform plan file (.tfplan).")
    parser.add_argument("--json-file", help="Path to pre-converted plan JSON file (for testing).")
    parser.add_argument("--allow-destroy", action="store_true", help="Explicitly allow destructive changes (overrides ALLOW_DESTROY env).")

    args = parser.parse_args()

    allow_destroy = True if args.allow_destroy else None
    exit_code = guard_plan(plan_path=args.plan_path, json_file=args.json_file, allow_destroy=allow_destroy)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
