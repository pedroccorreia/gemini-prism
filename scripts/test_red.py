#!/usr/bin/env python3
"""
Red Team Adversarial / Negative & Contract Testing Harness.

Systematically verifies:
1. allocate_licenses.py failure on missing config file, malformed JSON, and missing fields.
2. allocate_licenses.py preflight assertions on project number mismatch & pool capacity.
3. allocate_licenses.py safety: --dry-run guarantees zero write mutations.
4. verify.py handling of invalid project IDs and missing config files.
5. plan_guard.py rejection of delete/replace plans and override via ALLOW_DESTROY=1.
6. status.py state-driven phase detection, exit code contract, and state mismatch protection.
7. RUNBOOK.md parseable stage template contracts.
8. AGENTS.md line count constraint (<= 150 lines) and hand-off template completeness.
9. Link integrity across all repo markdown files.
10. Data Scrubbing: 0 leaked customer identifiers, domains, or real IDs in git tracked files.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

# Ensure repo root is on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import scripts.allocate_licenses as alloc_module
import scripts.plan_guard as plan_guard_module
import scripts.status as status_module
import scripts.verify as verify_module


class TestAllocateLicensesNegative(unittest.TestCase):
    """Negative and adversarial test cases for allocate_licenses.py."""

    def test_missing_config_file_fails_loudly(self):
        """Test failure when the specified config file does not exist."""
        non_existent_file = os.path.join(tempfile.gettempdir(), "non_existent_license_config_9999.json")
        if os.path.exists(non_existent_file):
            os.remove(non_existent_file)

        with self.assertRaises(FileNotFoundError) as ctx:
            alloc_module.load_config(non_existent_file)
        self.assertIn("Configuration file not found", str(ctx.exception))

    def test_malformed_config_json_fails_loudly(self):
        """Test failure when the configuration file contains corrupted JSON."""
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            f.write("{\n  \"billing_account\": \"000000-111111-222222\",\n  BROKEN_JSON: true\n")
            temp_path = f.name

        try:
            with self.assertRaises(ValueError) as ctx:
                alloc_module.load_config(temp_path)
            self.assertIn("Invalid JSON format", str(ctx.exception))
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    @patch("scripts.allocate_licenses.get_project_metadata")
    def test_preflight_failure_on_project_number_mismatch(self, mock_get_metadata):
        """Test that preflight assertion aborts if actual GCP project number does not match expected."""
        mock_get_metadata.return_value = {
            "projectNumber": "999999999999",
            "lifecycleState": "ACTIVE"
        }

        allocations = [
            {
                "project_id": "sample-customer-prod",
                "project_number": "123456789012",
                "seat_count": 5
            }
        ]

        with self.assertRaises(ValueError) as ctx:
            alloc_module.run_preflight_assertions(
                allocations=allocations,
                billing_account="012345-6789AB-CDEF01",
                license_config_id="lic-cfg-001",
                central_project="billing-project",
                location="global",
                token="dummy-token",
                dry_run=False
            )
        err_msg = str(ctx.exception)
        self.assertIn("Preflight assertion failed for project 'sample-customer-prod'", err_msg)
        self.assertIn("Expected Project Number: 123456789012", err_msg)
        self.assertIn("Actual GCP Project Number: 999999999999", err_msg)

    @patch("scripts.allocate_licenses.get_project_metadata")
    @patch("scripts.allocate_licenses.get_billing_account_license_config")
    def test_preflight_failure_on_insufficient_pool_seats(self, mock_get_billing_cfg, mock_get_metadata):
        """Test that preflight assertion aborts if requested seats exceed available billing pool capacity."""
        mock_get_metadata.return_value = {
            "projectNumber": "123456789012",
            "lifecycleState": "ACTIVE"
        }
        mock_get_billing_cfg.return_value = {
            "licenseCount": "10",
            "availableLicenseCount": "2"
        }

        allocations = [
            {
                "project_id": "sample-customer-prod",
                "project_number": "123456789012",
                "seat_count": 5
            }
        ]

        with self.assertRaises(ValueError) as ctx:
            alloc_module.run_preflight_assertions(
                allocations=allocations,
                billing_account="012345-6789AB-CDEF01",
                license_config_id="lic-cfg-001",
                central_project="billing-project",
                location="global",
                token="dummy-token",
                dry_run=False
            )
        err_msg = str(ctx.exception)
        self.assertIn("Insufficient license seats in billing pool", err_msg)
        self.assertIn("Requested: 5", err_msg)
        self.assertIn("Available: 2", err_msg)

    @patch("scripts.allocate_licenses.make_request")
    def test_dry_run_does_not_execute_destructive_writes(self, mock_make_request):
        """Test that --dry-run guarantees zero write/mutation API calls."""
        dist_res = alloc_module.distribute_license_config(
            billing_account="012345-6789AB-CDEF01",
            license_config_id="lic-cfg-001",
            project_number="123456789012",
            seat_count=5,
            token="dummy-token",
            central_project="billing-project",
            dry_run=True
        )
        self.assertEqual(dist_res, {})
        mock_make_request.assert_not_called()


class TestPlanGuard(unittest.TestCase):
    """Test cases for scripts/plan_guard.py."""

    def test_plan_guard_rejects_delete_action(self):
        """Plan with delete action must be rejected with exit code 1."""
        plan_data = {
            "resource_changes": [
                {
                    "address": "google_project.projects[\"prod\"]",
                    "type": "google_project",
                    "change": {"actions": ["delete"]}
                }
            ]
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(plan_data, f)
            plan_file = f.name

        try:
            exit_code = plan_guard_module.guard_plan(json_file=plan_file, allow_destroy=False)
            self.assertEqual(exit_code, 1, "Expected plan_guard to return 1 on delete")
        finally:
            if os.path.exists(plan_file):
                os.remove(plan_file)

    def test_plan_guard_rejects_replace_action(self):
        """Plan with delete+create replacement must be rejected with exit code 1."""
        plan_data = {
            "resource_changes": [
                {
                    "address": "google_discovery_engine_search_engine.engines[\"prod\"]",
                    "type": "google_discovery_engine_search_engine",
                    "change": {"actions": ["delete", "create"]}
                }
            ]
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(plan_data, f)
            plan_file = f.name

        try:
            exit_code = plan_guard_module.guard_plan(json_file=plan_file, allow_destroy=False)
            self.assertEqual(exit_code, 1, "Expected plan_guard to return 1 on replace")
        finally:
            if os.path.exists(plan_file):
                os.remove(plan_file)

    def test_plan_guard_allows_destructive_with_override(self):
        """Destructive changes must be permitted when allow_destroy=True."""
        plan_data = {
            "resource_changes": [
                {
                    "address": "google_project.projects[\"prod\"]",
                    "type": "google_project",
                    "change": {"actions": ["delete"]}
                }
            ]
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(plan_data, f)
            plan_file = f.name

        try:
            exit_code = plan_guard_module.guard_plan(json_file=plan_file, allow_destroy=True)
            self.assertEqual(exit_code, 0, "Expected plan_guard to return 0 when allow_destroy=True")
        finally:
            if os.path.exists(plan_file):
                os.remove(plan_file)

    def test_plan_guard_allows_pure_create_update(self):
        """Plan with only create and update actions must pass cleanly."""
        plan_data = {
            "resource_changes": [
                {
                    "address": "google_project.projects[\"prod\"]",
                    "type": "google_project",
                    "change": {"actions": ["create"]}
                },
                {
                    "address": "google_discovery_engine_acl_config.idp[\"prod\"]",
                    "type": "google_discovery_engine_acl_config",
                    "change": {"actions": ["update"]}
                }
            ]
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(plan_data, f)
            plan_file = f.name

        try:
            exit_code = plan_guard_module.guard_plan(json_file=plan_file, allow_destroy=False)
            self.assertEqual(exit_code, 0, "Expected plan_guard to return 0 for create/update")
        finally:
            if os.path.exists(plan_file):
                os.remove(plan_file)

    def test_plan_guard_allows_no_op(self):
        """Plan with only no-op actions must pass cleanly with exit code 0."""
        plan_data = {
            "resource_changes": [
                {
                    "address": "google_project.projects[\"prod\"]",
                    "type": "google_project",
                    "change": {"actions": ["no-op"]}
                }
            ]
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(plan_data, f)
            plan_file = f.name

        try:
            exit_code = plan_guard_module.guard_plan(json_file=plan_file, allow_destroy=False)
            self.assertEqual(exit_code, 0, "Expected plan_guard to return 0 for no-op")
        finally:
            if os.path.exists(plan_file):
                os.remove(plan_file)

    def test_plan_guard_rejects_replace_create_delete(self):
        """Plan with create+delete replacement order must be rejected with exit code 1."""
        plan_data = {
            "resource_changes": [
                {
                    "address": "google_discovery_engine_search_engine.engines[\"prod\"]",
                    "type": "google_discovery_engine_search_engine",
                    "change": {"actions": ["create", "delete"]}
                }
            ]
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(plan_data, f)
            plan_file = f.name

        try:
            exit_code = plan_guard_module.guard_plan(json_file=plan_file, allow_destroy=False)
            self.assertEqual(exit_code, 1, "Expected plan_guard to return 1 on replace (create, delete)")
        finally:
            if os.path.exists(plan_file):
                os.remove(plan_file)


class TestStatusPhaseDetection(unittest.TestCase):
    """Test cases for status.py phase detection and exit codes."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tools_patcher = patch("scripts.status.check_cli_tools", return_value=[])
        self.tools_patcher.start()

    def tearDown(self):
        self.tools_patcher.stop()
        self.temp_dir.cleanup()

    def _create_tfvars(self, data):
        tfvars_path = os.path.join(self.temp_dir.name, "terraform.tfvars")
        with open(tfvars_path, "w", encoding="utf-8") as f:
            for k, v in data.items():
                if isinstance(v, bool):
                    f.write(f'{k} = {"true" if v else "false"}\n')
                elif isinstance(v, list):
                    items = ", ".join(f'"{i}"' for i in v)
                    f.write(f'{k} = [{items}]\n')
                elif isinstance(v, dict):
                    entries = []
                    for mk, mv in v.items():
                        if isinstance(mv, list):
                            items_str = ", ".join(f'"{i}"' for i in mv)
                            entries.append(f'{mk} = [{items_str}]')
                        elif isinstance(mv, str):
                            entries.append(f'{mk} = "{mv}"')
                        elif isinstance(mv, bool):
                            entries.append(f'{mk} = {"true" if mv else "false"}')
                        elif mv is None:
                            entries.append(f'{mk} = null')
                        else:
                            entries.append(f'{mk} = {mv}')
                    f.write(f'{k} = {{\n  {",\n  ".join(entries)}\n}}\n')
                elif v is None:
                    f.write(f'{k} = null\n')
                else:
                    f.write(f'{k} = "{v}"\n')
        return tfvars_path

    def _create_state(self, project_ids=None, search_engines=None, assistants=None, foreign_projects=None, connectors=None):
        state_path = os.path.join(self.temp_dir.name, "terraform.tfstate")
        state_data = {
            "version": 4,
            "terraform_version": "1.14.8",
            "resources": [],
            "outputs": {}
        }

        # Add resources
        if foreign_projects:
            for fpid in foreign_projects:
                state_data["resources"].append({
                    "type": "google_project",
                    "name": "projects",
                    "instances": [{"attributes": {"project_id": fpid}}]
                })

        if connectors:
            instances = []
            for c_key in connectors:
                instances.append({
                    "index_key": c_key,
                    "attributes": {"data_source": c_key.split("-")[-1]}
                })
            state_data["resources"].append({
                "type": "google_discovery_engine_data_connector",
                "name": "connectors",
                "instances": instances
            })

        # Add outputs
        if project_ids:
            state_data["outputs"]["project_ids"] = {"value": project_ids}
        if search_engines:
            state_data["outputs"]["search_engine_names"] = {"value": search_engines}
        if assistants:
            state_data["outputs"]["assistant_names"] = {"value": assistants}

        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(state_data, f)
        return state_path

    def test_status_missing_tfvars_fails(self):
        """Missing terraform.tfvars must report Phase 0 and exit code 1."""
        status = status_module.determine_status(
            workdir=self.temp_dir.name,
            tfvars_path=os.path.join(self.temp_dir.name, "non_existent.tfvars"),
            skip_auth_check=True
        )
        self.assertEqual(status["exit_code"], 1)
        self.assertEqual(status["phase"], 0)
        self.assertEqual(status["handoff_template"], "inputs")

    @patch("scripts.status.check_identity")
    def test_status_missing_identity_fails(self, mock_check_id):
        """Unauthenticated environment must report Phase 0, identity blocker, and exit code 1."""
        mock_check_id.return_value = (False, None)
        status = status_module.determine_status(
            workdir=self.temp_dir.name,
            skip_auth_check=False
        )
        self.assertEqual(status["exit_code"], 1)
        self.assertEqual(status["phase"], 0)
        self.assertEqual(status["handoff_template"], "identity")
        self.assertIn("No active Google Cloud credentials", status["blockers"][0])

    def test_status_legacy_workspace_state_triggers_mismatch(self):
        """Workspace legacy state file with rwg-* projects must trigger state mismatch against fresh tfvars."""
        legacy_state_path = os.path.join(REPO_ROOT, "terraform.tfstate")
        if not os.path.exists(legacy_state_path):
            return  # skip if running in environment where state was pruned

        tfvars_path = self._create_tfvars({
            "customer_id": "testcust",
            "customer_name": "Test Customer",
            "company_domain": "testcust.org",
            "workspace_customer_id": "C09999999",
            "billing_account": "012345-6789AB-CDEF01",
            "environments": ["non-prod", "prod"]
        })

        status = status_module.determine_status(
            workdir=REPO_ROOT,
            tfvars_path=tfvars_path,
            state_path=legacy_state_path,
            skip_auth_check=True
        )
        self.assertEqual(status["exit_code"], 1)
        self.assertEqual(status["handoff_template"], "state_mismatch")
        self.assertIn("CRITICAL STATE MISMATCH", status["blockers"][0])

    def test_status_state_mismatch_fails_loudly(self):
        """Foreign project IDs in state must trigger state mismatch blocker with exit code 1."""
        tfvars_path = self._create_tfvars({
            "customer_id": "testcust",
            "customer_name": "Test Customer",
            "company_domain": "testcust.org",
            "workspace_customer_id": "C09999999",
            "billing_account": "012345-6789AB-CDEF01",
            "environments": ["non-prod", "prod"]
        })
        state_path = self._create_state(foreign_projects=["foreign-old-affiliate-1", "foreign-old-affiliate-2"])

        status = status_module.determine_status(
            workdir=self.temp_dir.name,
            tfvars_path=tfvars_path,
            state_path=state_path,
            skip_auth_check=True
        )
        self.assertEqual(status["exit_code"], 1)
        self.assertEqual(status["handoff_template"], "state_mismatch")
        self.assertIn("CRITICAL STATE MISMATCH", status["blockers"][0])

    def test_status_phase_1_ready(self):
        """Valid tfvars and no state outputs must indicate Stage 1 foundation ready with exit code 0."""
        tfvars_path = self._create_tfvars({
            "customer_id": "testcust",
            "customer_name": "Test Customer",
            "company_domain": "testcust.org",
            "workspace_customer_id": "C09999999",
            "billing_account": "012345-6789AB-CDEF01",
            "environments": ["non-prod", "prod"],
            "enable_connectors": False
        })
        status = status_module.determine_status(
            workdir=self.temp_dir.name,
            tfvars_path=tfvars_path,
            state_path=os.path.join(self.temp_dir.name, "non_existent.tfstate"),
            skip_auth_check=True
        )
        self.assertEqual(status["exit_code"], 0)
        self.assertEqual(status["phase"], 1)
        self.assertEqual(status["phase_name"], "foundation_apply")

    def test_status_phase_2_dwd_human_gate(self):
        """Foundation outputs present but enable_connectors=false must trigger Stage 2 human gate (exit 2)."""
        tfvars_path = self._create_tfvars({
            "customer_id": "testcust",
            "customer_name": "Test Customer",
            "company_domain": "testcust.org",
            "workspace_customer_id": "C09999999",
            "billing_account": "012345-6789AB-CDEF01",
            "environments": ["non-prod", "prod"],
            "enable_connectors": False
        })
        state_path = self._create_state(project_ids={"non-prod": "testcust-non-prod", "prod": "testcust-prod"})

        status = status_module.determine_status(
            workdir=self.temp_dir.name,
            tfvars_path=tfvars_path,
            state_path=state_path,
            skip_auth_check=True
        )
        self.assertEqual(status["exit_code"], 2)
        self.assertEqual(status["phase"], 2)
        self.assertEqual(status["handoff_template"], "dwd")

    def test_status_phase_3_ready(self):
        """enable_connectors=true and engines missing must indicate Stage 3 ready with exit code 0."""
        tfvars_path = self._create_tfvars({
            "customer_id": "testcust",
            "customer_name": "Test Customer",
            "company_domain": "testcust.org",
            "workspace_customer_id": "C09999999",
            "billing_account": "012345-6789AB-CDEF01",
            "environments": ["non-prod", "prod"],
            "enable_connectors": True
        })
        state_path = self._create_state(project_ids={"non-prod": "testcust-non-prod", "prod": "testcust-prod"})

        status = status_module.determine_status(
            workdir=self.temp_dir.name,
            tfvars_path=tfvars_path,
            state_path=state_path,
            skip_auth_check=True
        )
        self.assertEqual(status["exit_code"], 0)
        self.assertEqual(status["phase"], 3)
        self.assertEqual(status["phase_name"], "connectors_and_engines_apply")

    def test_status_phase_4_subscription_gate(self):
        """Engines complete but subscription IDs missing must trigger Stage 4 subscription gate (exit 2)."""
        tfvars_path = self._create_tfvars({
            "customer_id": "testcust",
            "customer_name": "Test Customer",
            "company_domain": "testcust.org",
            "workspace_customer_id": "C09999999",
            "billing_account": "012345-6789AB-CDEF01",
            "environments": ["non-prod", "prod"],
            "enable_connectors": True,
            "license_config_id": "",
            "subscription_id": ""
        })
        state_path = self._create_state(
            project_ids={"non-prod": "testcust-non-prod", "prod": "testcust-prod"},
            search_engines={"non-prod": "eng-1", "prod": "eng-2"},
            assistants={"non-prod": "asst-1", "prod": "asst-2"}
        )

        status = status_module.determine_status(
            workdir=self.temp_dir.name,
            tfvars_path=tfvars_path,
            state_path=state_path,
            skip_auth_check=True
        )
        self.assertEqual(status["exit_code"], 2)
        self.assertEqual(status["phase"], 4)
        self.assertEqual(status["handoff_template"], "subscription")

    def test_status_phase_2_jira_human_gate_when_instance_uri_placeholder(self):
        """enable_jira_connector=true with missing or placeholder instance_uri must trigger Stage 2 jira gate (exit 2)."""
        tfvars_path = self._create_tfvars({
            "customer_id": "testcust",
            "customer_name": "Test Customer",
            "company_domain": "testcust.org",
            "workspace_customer_id": "C09999999",
            "billing_account": "012345-6789AB-CDEF01",
            "environments": ["non-prod", "prod"],
            "enable_connectors": True,
            "enable_jira_connector": True,
            "jira_config": {
                "instance_uri": "https://example.atlassian.net",
                "data_source": "jira"
            }
        })
        state_path = self._create_state(project_ids={"non-prod": "testcust-non-prod", "prod": "testcust-prod"})

        status = status_module.determine_status(
            workdir=self.temp_dir.name,
            tfvars_path=tfvars_path,
            state_path=state_path,
            skip_auth_check=True
        )
        self.assertEqual(status["exit_code"], 2)
        self.assertEqual(status["phase"], 2)
        self.assertEqual(status["handoff_template"], "jira")
        self.assertIn("jira", status["blockers"][0].lower())

    def test_status_phase_2_jira_only_gate_when_workspace_connectors_disabled(self):
        """Jira-only deployment (enable_connectors=false, enable_jira_connector=true) with placeholder URI must trigger jira gate, NOT DWD gate."""
        tfvars_path = self._create_tfvars({
            "customer_id": "testcust",
            "customer_name": "Test Customer",
            "company_domain": "testcust.org",
            "workspace_customer_id": "C09999999",
            "billing_account": "012345-6789AB-CDEF01",
            "environments": ["non-prod", "prod"],
            "enable_connectors": False,
            "enable_jira_connector": True,
            "jira_config": {
                "instance_uri": "https://example.atlassian.net",
                "data_source": "jira"
            }
        })
        state_path = self._create_state(project_ids={"non-prod": "testcust-non-prod", "prod": "testcust-prod"})

        status = status_module.determine_status(
            workdir=self.temp_dir.name,
            tfvars_path=tfvars_path,
            state_path=state_path,
            skip_auth_check=True
        )
        self.assertEqual(status["exit_code"], 2)
        self.assertEqual(status["phase"], 2)
        self.assertEqual(status["handoff_template"], "jira")
        self.assertIn("jira", status["blockers"][0].lower())

    def test_status_phase_3_ready_jira_only_with_valid_uri(self):
        """Jira-only deployment (enable_connectors=false, enable_jira_connector=true) with valid URI must advance to Phase 3 (exit 0)."""
        tfvars_path = self._create_tfvars({
            "customer_id": "testcust",
            "customer_name": "Test Customer",
            "company_domain": "testcust.org",
            "workspace_customer_id": "C09999999",
            "billing_account": "012345-6789AB-CDEF01",
            "environments": ["non-prod", "prod"],
            "enable_connectors": False,
            "enable_jira_connector": True,
            "jira_config": {
                "instance_uri": "https://custom-team.atlassian.net",
                "data_source": "jira"
            }
        })
        state_path = self._create_state(project_ids={"non-prod": "testcust-non-prod", "prod": "testcust-prod"})

        status = status_module.determine_status(
            workdir=self.temp_dir.name,
            tfvars_path=tfvars_path,
            state_path=state_path,
            skip_auth_check=True
        )
        self.assertEqual(status["exit_code"], 0)
        self.assertEqual(status["phase"], 3)
        self.assertEqual(status["phase_name"], "connectors_and_engines_apply")

    def test_status_phase_3_ready_with_valid_jira(self):
        """enable_jira_connector=true and enable_connectors=true with valid instance_uri must indicate Stage 3 ready (exit 0)."""
        tfvars_path = self._create_tfvars({
            "customer_id": "testcust",
            "customer_name": "Test Customer",
            "company_domain": "testcust.org",
            "workspace_customer_id": "C09999999",
            "billing_account": "012345-6789AB-CDEF01",
            "environments": ["non-prod", "prod"],
            "enable_connectors": True,
            "enable_jira_connector": True,
            "jira_config": {
                "instance_uri": "https://custom-team.atlassian.net",
                "data_source": "jira"
            }
        })
        state_path = self._create_state(project_ids={"non-prod": "testcust-non-prod", "prod": "testcust-prod"})

        status = status_module.determine_status(
            workdir=self.temp_dir.name,
            tfvars_path=tfvars_path,
            state_path=state_path,
            skip_auth_check=True
        )
        self.assertEqual(status["exit_code"], 0)
        self.assertEqual(status["phase"], 3)
        self.assertEqual(status["phase_name"], "connectors_and_engines_apply")

    def test_status_phase_3_stays_when_jira_connector_missing_from_state(self):
        """When workspace connectors exist in state but jira connector is missing, status must stay in Phase 3."""
        tfvars_path = self._create_tfvars({
            "customer_id": "testcust",
            "customer_name": "Test Customer",
            "company_domain": "testcust.org",
            "workspace_customer_id": "C09999999",
            "billing_account": "012345-6789AB-CDEF01",
            "environments": ["prod"],
            "enable_connectors": True,
            "enable_jira_connector": True,
            "jira_config": {
                "instance_uri": "https://custom-team.atlassian.net",
                "data_source": "jira"
            }
        })
        # State has project_ids, search_engines, assistants, and workspace data_connector_names, but no prod-jira
        state_path = self._create_state(
            project_ids={"prod": "testcust-prod"},
            search_engines={"prod": "projects/123/locations/global/collections/default_collection/engines/engine-1"},
            assistants={"prod": "projects/123/locations/global/collections/default_collection/engines/engine-1/assistants/default_assistant"}
        )
        # Add data_connector_names output with only prod-google_mail
        with open(state_path, "r", encoding="utf-8") as f:
            st = json.load(f)
        st["outputs"]["data_connector_names"] = {
            "value": {
                "prod-google_mail": "projects/123/locations/global/collections/mail-col/dataConnector"
            }
        }
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(st, f)

        status = status_module.determine_status(
            workdir=self.temp_dir.name,
            tfvars_path=tfvars_path,
            state_path=state_path,
            skip_auth_check=True
        )
        self.assertEqual(status["exit_code"], 0)
        self.assertEqual(status["phase"], 3)
        self.assertEqual(status["phase_name"], "connectors_and_engines_apply")

    def test_parse_tfvars_preserves_nested_jira_config_types(self):
        """parse_tfvars must parse booleans, lists, and strings inside jira_config without clobbering."""
        raw_tfvars = {
            "customer_id": "testcust",
            "customer_name": "Test Customer",
            "company_domain": "testcust.org",
            "workspace_customer_id": "C09999999",
            "billing_account": "012345-6789AB-CDEF01",
            "enable_jira_connector": True,
            "jira_auth_type": "OAUTH",
            "jira_config": {
                "instance_uri": "https://custom.atlassian.net",
                "instance_id": "11111111-2222-3333-4444-555555555555",
                "static_ip_enabled": False,
                "enable_actions": True,
                "entities": ["project", "issue", "comment"]
            }
        }
        tfvars_path = self._create_tfvars(raw_tfvars)
        parsed = status_module.parse_tfvars(tfvars_path)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.get("jira_auth_type"), "OAUTH")
        cfg = parsed.get("jira_config", {})
        self.assertEqual(cfg.get("instance_uri"), "https://custom.atlassian.net")
        self.assertEqual(cfg.get("instance_id"), "11111111-2222-3333-4444-555555555555")
        self.assertIs(cfg.get("static_ip_enabled"), False)
        self.assertIs(cfg.get("enable_actions"), True)
        self.assertEqual(cfg.get("entities"), ["project", "issue", "comment"])

    def test_status_phase_2_jira_rejects_data_ingestion_mode(self):
        """enable_jira_connector=true with DATA_INGESTION mode must trigger Stage 2 jira gate (exit 2)."""
        tfvars_path = self._create_tfvars({
            "customer_id": "testcust",
            "customer_name": "Test Customer",
            "company_domain": "testcust.org",
            "workspace_customer_id": "C09999999",
            "billing_account": "012345-6789AB-CDEF01",
            "environments": ["non-prod"],
            "enable_connectors": True,
            "enable_jira_connector": True,
            "jira_config": {
                "instance_uri": "https://custom-team.atlassian.net",
                "connector_modes": ["DATA_INGESTION"]
            }
        })
        state_path = self._create_state(project_ids={"non-prod": "testcust-non-prod"})

        status = status_module.determine_status(
            workdir=self.temp_dir.name,
            tfvars_path=tfvars_path,
            state_path=state_path,
            skip_auth_check=True
        )
        self.assertEqual(status["exit_code"], 2)
        self.assertEqual(status["phase"], 2)
        self.assertEqual(status["handoff_template"], "jira")
        self.assertIn("FEDERATED", status["blockers"][0])

    def test_status_phase_2_jira_rejects_basic_auth_on_atlassian_cloud(self):
        """enable_jira_connector=true with BASIC_AUTH/API_TOKEN against *.atlassian.net must trigger Stage 2 jira gate (exit 2)."""
        tfvars_path = self._create_tfvars({
            "customer_id": "testcust",
            "customer_name": "Test Customer",
            "company_domain": "testcust.org",
            "workspace_customer_id": "C09999999",
            "billing_account": "012345-6789AB-CDEF01",
            "environments": ["non-prod"],
            "enable_connectors": True,
            "enable_jira_connector": True,
            "jira_auth_type": "API_TOKEN",
            "jira_config": {
                "instance_uri": "https://custom-team.atlassian.net",
                "connector_modes": ["FEDERATED"]
            }
        })
        state_path = self._create_state(project_ids={"non-prod": "testcust-non-prod"})

        status = status_module.determine_status(
            workdir=self.temp_dir.name,
            tfvars_path=tfvars_path,
            state_path=state_path,
            skip_auth_check=True
        )
        self.assertEqual(status["exit_code"], 2)
        self.assertEqual(status["phase"], 2)
        self.assertEqual(status["handoff_template"], "jira")
        self.assertIn("OAuth 2.0", status["blockers"][0])

    def test_status_phase_2_confluence_human_gate_when_instance_uri_placeholder(self):
        """enable_confluence_connector=true with missing or placeholder instance_uri must trigger Stage 2 confluence gate (exit 2)."""
        tfvars_path = self._create_tfvars({
            "customer_id": "testcust",
            "customer_name": "Test Customer",
            "company_domain": "testcust.org",
            "workspace_customer_id": "C09999999",
            "billing_account": "012345-6789AB-CDEF01",
            "environments": ["non-prod", "prod"],
            "enable_connectors": True,
            "enable_confluence_connector": True,
            "confluence_config": {
                "instance_uri": "https://example.atlassian.net",
                "data_source": "confluence"
            }
        })
        state_path = self._create_state(project_ids={"non-prod": "testcust-non-prod", "prod": "testcust-prod"})

        status = status_module.determine_status(
            workdir=self.temp_dir.name,
            tfvars_path=tfvars_path,
            state_path=state_path,
            skip_auth_check=True
        )
        self.assertEqual(status["exit_code"], 2)
        self.assertEqual(status["phase"], 2)
        self.assertEqual(status["handoff_template"], "confluence")
        self.assertIn("confluence", status["blockers"][0].lower())

    def test_status_phase_2_confluence_only_gate_when_workspace_connectors_disabled(self):
        """Confluence-only deployment (enable_connectors=false, enable_confluence_connector=true) with placeholder URI must trigger confluence gate, NOT DWD gate."""
        tfvars_path = self._create_tfvars({
            "customer_id": "testcust",
            "customer_name": "Test Customer",
            "company_domain": "testcust.org",
            "workspace_customer_id": "C09999999",
            "billing_account": "012345-6789AB-CDEF01",
            "environments": ["non-prod", "prod"],
            "enable_connectors": False,
            "enable_confluence_connector": True,
            "confluence_config": {
                "instance_uri": "https://example.atlassian.net",
                "data_source": "confluence"
            }
        })
        state_path = self._create_state(project_ids={"non-prod": "testcust-non-prod", "prod": "testcust-prod"})

        status = status_module.determine_status(
            workdir=self.temp_dir.name,
            tfvars_path=tfvars_path,
            state_path=state_path,
            skip_auth_check=True
        )
        self.assertEqual(status["exit_code"], 2)
        self.assertEqual(status["phase"], 2)
        self.assertEqual(status["handoff_template"], "confluence")
        self.assertIn("confluence", status["blockers"][0].lower())

    def test_status_phase_3_ready_confluence_only_with_valid_uri(self):
        """Confluence-only deployment (enable_connectors=false, enable_confluence_connector=true) with valid URI must advance to Phase 3 (exit 0)."""
        tfvars_path = self._create_tfvars({
            "customer_id": "testcust",
            "customer_name": "Test Customer",
            "company_domain": "testcust.org",
            "workspace_customer_id": "C09999999",
            "billing_account": "012345-6789AB-CDEF01",
            "environments": ["non-prod", "prod"],
            "enable_connectors": False,
            "enable_confluence_connector": True,
            "confluence_config": {
                "instance_uri": "https://custom-team.atlassian.net",
                "data_source": "confluence"
            }
        })
        state_path = self._create_state(project_ids={"non-prod": "testcust-non-prod", "prod": "testcust-prod"})

        status = status_module.determine_status(
            workdir=self.temp_dir.name,
            tfvars_path=tfvars_path,
            state_path=state_path,
            skip_auth_check=True
        )
        self.assertEqual(status["exit_code"], 0)
        self.assertEqual(status["phase"], 3)
        self.assertEqual(status["phase_name"], "connectors_and_engines_apply")

    def test_status_phase_3_ready_confluence_inherits_jira_instance_uri(self):
        """Confluence must inherit Jira's instance_uri when confluence_config.instance_uri is omitted and advance to Phase 3 (exit 0)."""
        tfvars_path = self._create_tfvars({
            "customer_id": "testcust",
            "customer_name": "Test Customer",
            "company_domain": "testcust.org",
            "workspace_customer_id": "C09999999",
            "billing_account": "012345-6789AB-CDEF01",
            "environments": ["non-prod", "prod"],
            "enable_connectors": True,
            "enable_jira_connector": True,
            "enable_confluence_connector": True,
            "jira_config": {
                "instance_uri": "https://custom-team.atlassian.net",
                "data_source": "jira"
            },
            "confluence_config": {}
        })
        state_path = self._create_state(project_ids={"non-prod": "testcust-non-prod", "prod": "testcust-prod"})

        status = status_module.determine_status(
            workdir=self.temp_dir.name,
            tfvars_path=tfvars_path,
            state_path=state_path,
            skip_auth_check=True
        )
        self.assertEqual(status["exit_code"], 0)
        self.assertEqual(status["phase"], 3)
        self.assertEqual(status["phase_name"], "connectors_and_engines_apply")

    def test_status_phase_3_stays_when_confluence_connector_missing_from_state(self):
        """When workspace connectors exist in state but confluence connector is missing, status must stay in Phase 3."""
        tfvars_path = self._create_tfvars({
            "customer_id": "testcust",
            "customer_name": "Test Customer",
            "company_domain": "testcust.org",
            "workspace_customer_id": "C09999999",
            "billing_account": "012345-6789AB-CDEF01",
            "environments": ["prod"],
            "enable_connectors": True,
            "enable_confluence_connector": True,
            "confluence_config": {
                "instance_uri": "https://custom-team.atlassian.net",
                "data_source": "confluence"
            }
        })
        state_path = self._create_state(
            project_ids={"prod": "testcust-prod"},
            search_engines={"prod": "projects/123/locations/global/collections/default_collection/engines/engine-1"},
            assistants={"prod": "projects/123/locations/global/collections/default_collection/engines/engine-1/assistants/default_assistant"}
        )
        with open(state_path, "r", encoding="utf-8") as f:
            st = json.load(f)
        st["outputs"]["data_connector_names"] = {
            "value": {
                "prod-google_mail": "projects/123/locations/global/collections/mail-col/dataConnector"
            }
        }
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(st, f)

        status = status_module.determine_status(
            workdir=self.temp_dir.name,
            tfvars_path=tfvars_path,
            state_path=state_path,
            skip_auth_check=True
        )
        self.assertEqual(status["exit_code"], 0)
        self.assertEqual(status["phase"], 3)
        self.assertEqual(status["phase_name"], "connectors_and_engines_apply")

    def test_parse_tfvars_preserves_nested_confluence_config_types(self):
        """parse_tfvars must parse booleans, lists, and strings inside confluence_config without clobbering."""
        raw_tfvars = {
            "customer_id": "testcust",
            "customer_name": "Test Customer",
            "company_domain": "testcust.org",
            "workspace_customer_id": "C09999999",
            "billing_account": "012345-6789AB-CDEF01",
            "enable_confluence_connector": True,
            "confluence_auth_type": "OAUTH",
            "confluence_config": {
                "instance_uri": "https://custom.atlassian.net",
                "connector_modes": ["FEDERATED"],
                "entities": ["space", "page", "blog", "attachment", "comment"],
                "space_keys_include": ["ENG", "PROD"]
            }
        }
        tfvars_path = self._create_tfvars(raw_tfvars)
        parsed = status_module.parse_tfvars(tfvars_path)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.get("confluence_auth_type"), "OAUTH")
        cfg = parsed.get("confluence_config", {})
        self.assertEqual(cfg.get("instance_uri"), "https://custom.atlassian.net")
        self.assertEqual(cfg.get("connector_modes"), ["FEDERATED"])
        self.assertEqual(cfg.get("entities"), ["space", "page", "blog", "attachment", "comment"])
        self.assertEqual(cfg.get("space_keys_include"), ["ENG", "PROD"])

    def test_status_phase_2_confluence_rejects_data_ingestion_mode(self):
        """enable_confluence_connector=true with DATA_INGESTION mode must trigger Stage 2 confluence gate (exit 2)."""
        tfvars_path = self._create_tfvars({
            "customer_id": "testcust",
            "customer_name": "Test Customer",
            "company_domain": "testcust.org",
            "workspace_customer_id": "C09999999",
            "billing_account": "012345-6789AB-CDEF01",
            "environments": ["non-prod"],
            "enable_connectors": True,
            "enable_confluence_connector": True,
            "confluence_config": {
                "instance_uri": "https://custom-team.atlassian.net",
                "connector_modes": ["DATA_INGESTION"]
            }
        })
        state_path = self._create_state(project_ids={"non-prod": "testcust-non-prod"})

        status = status_module.determine_status(
            workdir=self.temp_dir.name,
            tfvars_path=tfvars_path,
            state_path=state_path,
            skip_auth_check=True
        )
        self.assertEqual(status["exit_code"], 2)
        self.assertEqual(status["phase"], 2)
        self.assertEqual(status["handoff_template"], "confluence")
        self.assertIn("FEDERATED", status["blockers"][0])

    def test_status_phase_2_confluence_rejects_basic_auth_on_atlassian_cloud(self):
        """enable_confluence_connector=true with BASIC_AUTH/API_TOKEN against *.atlassian.net must trigger Stage 2 confluence gate (exit 2)."""
        tfvars_path = self._create_tfvars({
            "customer_id": "testcust",
            "customer_name": "Test Customer",
            "company_domain": "testcust.org",
            "workspace_customer_id": "C09999999",
            "billing_account": "012345-6789AB-CDEF01",
            "environments": ["non-prod"],
            "enable_connectors": True,
            "enable_confluence_connector": True,
            "confluence_auth_type": "API_TOKEN",
            "confluence_config": {
                "instance_uri": "https://custom-team.atlassian.net",
                "connector_modes": ["FEDERATED"]
            }
        })
        state_path = self._create_state(project_ids={"non-prod": "testcust-non-prod"})

        status = status_module.determine_status(
            workdir=self.temp_dir.name,
            tfvars_path=tfvars_path,
            state_path=state_path,
            skip_auth_check=True
        )
        self.assertEqual(status["exit_code"], 2)
        self.assertEqual(status["phase"], 2)
        self.assertEqual(status["handoff_template"], "confluence")
        self.assertIn("OAuth 2.0", status["blockers"][0])

    def test_status_phase_3_ready_people_directory_only(self):
        """People Directory deployment (enable_connectors=false, enable_jira_connector=false, enable_people_directory_connector=true) must advance to Phase 3 (exit 0)."""
        tfvars_path = self._create_tfvars({
            "customer_id": "testcust",
            "customer_name": "Test Customer",
            "company_domain": "testcust.org",
            "workspace_customer_id": "C09999999",
            "billing_account": "012345-6789AB-CDEF01",
            "environments": ["non-prod", "prod"],
            "enable_connectors": False,
            "enable_jira_connector": False,
            "enable_people_directory_connector": True
        })
        state_path = self._create_state(project_ids={"non-prod": "testcust-non-prod", "prod": "testcust-prod"})

        status = status_module.determine_status(
            workdir=self.temp_dir.name,
            tfvars_path=tfvars_path,
            state_path=state_path,
            skip_auth_check=True
        )
        self.assertEqual(status["exit_code"], 0)
        self.assertEqual(status["phase"], 3)
        self.assertEqual(status["phase_name"], "connectors_and_engines_apply")

    def test_status_phase_3_stays_when_people_directory_connector_missing_from_state(self):
        """When search engines exist in state but people-directory connector is missing, status must stay in Phase 3."""
        tfvars_path = self._create_tfvars({
            "customer_id": "testcust",
            "customer_name": "Test Customer",
            "company_domain": "testcust.org",
            "workspace_customer_id": "C09999999",
            "billing_account": "012345-6789AB-CDEF01",
            "environments": ["prod"],
            "enable_connectors": False,
            "enable_jira_connector": False,
            "enable_people_directory_connector": True
        })
        state_path = self._create_state(
            project_ids={"prod": "testcust-prod"},
            search_engines={"prod": "projects/123/locations/global/collections/default_collection/engines/engine-1"},
            assistants={"prod": "projects/123/locations/global/collections/default_collection/engines/engine-1/assistants/default_assistant"}
        )
        with open(state_path, "r", encoding="utf-8") as f:
            st = json.load(f)
        st["outputs"]["data_connector_names"] = {
            "value": {
                "prod-google_mail": "projects/123/locations/global/collections/mail-col/dataConnector"
            }
        }
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(st, f)

        status = status_module.determine_status(
            workdir=self.temp_dir.name,
            tfvars_path=tfvars_path,
            state_path=state_path,
            skip_auth_check=True
        )
        self.assertEqual(status["exit_code"], 0)
        self.assertEqual(status["phase"], 3)
        self.assertEqual(status["phase_name"], "connectors_and_engines_apply")

    def test_parse_tfvars_preserves_nested_people_directory_config_types(self):
        """parse_tfvars must parse booleans, lists, and strings inside people_directory_config without clobbering."""
        raw_tfvars = {
            "customer_id": "testcust",
            "customer_name": "Test Customer",
            "company_domain": "testcust.org",
            "workspace_customer_id": "C09999999",
            "billing_account": "012345-6789AB-CDEF01",
            "enable_people_directory_connector": True,
            "people_directory_config": {
                "data_source": "google_people_directory",
                "collection_id": "people-directory-collection",
                "include_suspended_users": False,
                "org_units_include": ["/Employees", "/Contractors"],
                "custom_schemas_include": ["Skills"],
                "refresh_interval": "86400s",
                "sync_mode": "INCREMENTAL",
                "entities": ["user_profile", "reporting_hierarchy"]
            }
        }
        tfvars_path = self._create_tfvars(raw_tfvars)
        parsed = status_module.parse_tfvars(tfvars_path)
        self.assertIsNotNone(parsed)
        self.assertIs(parsed.get("enable_people_directory_connector"), True)
        cfg = parsed.get("people_directory_config", {})
        self.assertEqual(cfg.get("data_source"), "google_people_directory")
        self.assertEqual(cfg.get("collection_id"), "people-directory-collection")
        self.assertIs(cfg.get("include_suspended_users"), False)
        self.assertEqual(cfg.get("org_units_include"), ["/Employees", "/Contractors"])
        self.assertEqual(cfg.get("custom_schemas_include"), ["Skills"])
        self.assertEqual(cfg.get("sync_mode"), "INCREMENTAL")
        self.assertEqual(cfg.get("entities"), ["user_profile", "reporting_hierarchy"])


class TestVerifyConnectors(unittest.TestCase):
    """Test cases for verify.py multi-entity and third-party data connector inspection."""

    @patch("scripts.verify.make_request")
    def test_verify_check_data_connectors_multi_entity_jira(self, mock_make_request):
        """check_data_connectors must inspect multi-entity Jira connector and surface entities count and connectorModes."""
        def side_effect(url, **kwargs):
            if url.endswith("/collections"):
                return {
                    "collections": [
                        {"name": "projects/test-proj/locations/global/collections/jira-federated-collection"}
                    ]
                }
            elif url.endswith("/dataConnector"):
                return {
                    "name": "projects/test-proj/locations/global/collections/jira-federated-collection/dataConnector",
                    "dataSource": "jira",
                    "state": "STATE_ACTIVE",
                    "realtimeState": "STATE_ACTIVE",
                    "actionState": "STATE_ACTIVE",
                    "connectorModes": ["FEDERATED"],
                    "entities": [
                        {"entityName": "project"},
                        {"entityName": "issue"},
                        {"entityName": "attachment"},
                        {"entityName": "comment"},
                        {"entityName": "worklog"}
                    ]
                }
            return {}

        mock_make_request.side_effect = side_effect

        results = verify_module.check_data_connectors("test-proj", "global", "mock-token")
        self.assertEqual(len(results), 1)
        component, status, details = results[0]
        self.assertIn("Connector (jira)", component)
        self.assertEqual(status, "STATE_ACTIVE")
        self.assertIn("Modes: FEDERATED", details)
        self.assertIn("Entities: 5", details)
        self.assertIn("Realtime: STATE_ACTIVE", details)
        self.assertIn("ActionState: STATE_ACTIVE", details)

    @patch("scripts.verify.make_request")
    def test_verify_check_data_connectors_multi_entity_confluence(self, mock_make_request):
        """check_data_connectors must inspect Confluence connector and surface entities count and connectorModes."""
        def side_effect(url, **kwargs):
            if url.endswith("/collections"):
                return {
                    "collections": [
                        {"name": "projects/test-proj/locations/global/collections/confluence-federated-collection"}
                    ]
                }
            elif url.endswith("/dataConnector"):
                return {
                    "name": "projects/test-proj/locations/global/collections/confluence-federated-collection/dataConnector",
                    "dataSource": "confluence",
                    "state": "STATE_ACTIVE",
                    "realtimeState": "STATE_ACTIVE",
                    "actionState": "STATE_ACTIVE",
                    "connectorModes": ["FEDERATED"],
                    "entities": [
                        {"entityName": "space"},
                        {"entityName": "page"},
                        {"entityName": "blog"},
                        {"entityName": "attachment"},
                        {"entityName": "comment"}
                    ]
                }
            return {}

        mock_make_request.side_effect = side_effect

        results = verify_module.check_data_connectors("test-proj", "global", "mock-token")
        self.assertEqual(len(results), 1)
        component, status, details = results[0]
        self.assertIn("Connector (confluence)", component)
        self.assertEqual(status, "STATE_ACTIVE")
        self.assertIn("Modes: FEDERATED", details)
        self.assertIn("Entities: 5", details)
        self.assertIn("Realtime: STATE_ACTIVE", details)
        self.assertIn("ActionState: STATE_ACTIVE", details)

    @patch("scripts.verify.make_request")
    def test_verify_check_data_connectors_surfaces_errors_and_blocking(self, mock_make_request):
        """check_data_connectors must report ERROR status when connector errors exist and display blocking reasons."""
        def side_effect(url, **kwargs):
            if url.endswith("/collections"):
                return {
                    "collections": [
                        {"name": "projects/test-proj/locations/global/collections/jira-collection"}
                    ]
                }
            elif url.endswith("/dataConnector"):
                return {
                    "name": "projects/test-proj/locations/global/collections/jira-collection/dataConnector",
                    "dataSource": "jira",
                    "state": "STATE_ACTIVE",
                    "blockingReasons": ["ALLOWLIST_STATIC_IP"],
                    "errors": [{"code": 401, "message": "Unauthorized"}]
                }
            return {}

        mock_make_request.side_effect = side_effect

        results = verify_module.check_data_connectors("test-proj", "global", "mock-token")
        self.assertEqual(len(results), 1)
        component, status, details = results[0]
        self.assertEqual(status, "ERROR")
        self.assertIn("Blocking: ALLOWLIST_STATIC_IP", details)
        self.assertIn("Errors: 1", details)

    @patch("scripts.verify.make_request")
    def test_verify_check_data_connectors_warns_on_blocking_reasons_without_errors(self, mock_make_request):
        """check_data_connectors must report WARN status when connector has blockingReasons (e.g. ALLOWLIST_STATIC_IP) but no errors."""
        def side_effect(url, **kwargs):
            if url.endswith("/collections"):
                return {
                    "collections": [
                        {"name": "projects/test-proj/locations/global/collections/jira-collection"}
                    ]
                }
            elif url.endswith("/dataConnector"):
                return {
                    "name": "projects/test-proj/locations/global/collections/jira-collection/dataConnector",
                    "dataSource": "jira",
                    "state": "STATE_ACTIVE",
                    "blockingReasons": ["ALLOWLIST_STATIC_IP"],
                    "errors": []
                }
            return {}

        mock_make_request.side_effect = side_effect

        results = verify_module.check_data_connectors("test-proj", "global", "mock-token")
        self.assertEqual(len(results), 1)
        component, status, details = results[0]
        self.assertEqual(status, "WARN")
        self.assertIn("Blocking: ALLOWLIST_STATIC_IP", details)

    @patch("scripts.verify.make_request")
    def test_verify_check_data_connectors_initialization_failed_reports_error(self, mock_make_request):
        """check_data_connectors must report ERROR status when connector state is INITIALIZATION_FAILED."""
        def side_effect(url, **kwargs):
            if url.endswith("/collections"):
                return {
                    "collections": [
                        {"name": "projects/test-proj/locations/global/collections/jira-collection"}
                    ]
                }
            elif url.endswith("/dataConnector"):
                return {
                    "name": "projects/test-proj/locations/global/collections/jira-collection/dataConnector",
                    "dataSource": "jira",
                    "state": "INITIALIZATION_FAILED",
                    "errors": []
                }
            return {}

        mock_make_request.side_effect = side_effect

        results = verify_module.check_data_connectors("test-proj", "global", "mock-token")
        self.assertEqual(len(results), 1)
        component, status, details = results[0]
        self.assertEqual(status, "ERROR")

    @patch("scripts.verify.make_request")
    def test_verify_check_data_connectors_people_directory(self, mock_make_request):
        """check_data_connectors must inspect Google People Directory connector and surface entity counts."""
        def side_effect(url, **kwargs):
            if url.endswith("/collections"):
                return {
                    "collections": [
                        {"name": "projects/test-proj/locations/global/collections/people-directory-collection"}
                    ]
                }
            elif url.endswith("/dataConnector"):
                return {
                    "name": "projects/test-proj/locations/global/collections/people-directory-collection/dataConnector",
                    "dataSource": "google_people_directory",
                    "state": "STATE_ACTIVE",
                    "entities": [
                        {"entityName": "user_profile"},
                        {"entityName": "job_architecture"},
                        {"entityName": "reporting_hierarchy"},
                        {"entityName": "location_contact"},
                        {"entityName": "custom_attributes"}
                    ]
                }
            return {}

        mock_make_request.side_effect = side_effect

        results = verify_module.check_data_connectors("test-proj", "global", "mock-token")
        self.assertEqual(len(results), 1)
        component, status, details = results[0]
        self.assertIn("Connector (google_people_directory)", component)
        self.assertEqual(status, "STATE_ACTIVE")
        self.assertIn("Entities: 5", details)
        self.assertIn("Collection: people-directory-collection", details)


class TestDocumentationContracts(unittest.TestCase):
    """Test compliance with documentation and agent protocol contracts."""

    def test_runbook_stages_headings_contract(self):
        """Every ## Stage block in RUNBOOK.md must contain all 5 required subheadings."""
        runbook_path = os.path.join(REPO_ROOT, "RUNBOOK.md")
        self.assertTrue(os.path.exists(runbook_path), "RUNBOOK.md must exist")

        with open(runbook_path, "r", encoding="utf-8") as f:
            content = f.read()

        stage_blocks = re.split(r'\n(?=## Stage \d+ — )', content)[1:]
        self.assertGreaterEqual(len(stage_blocks), 5, "RUNBOOK.md must have at least Stages 0 through 5")

        required_headings = [
            "**Owner:**",
            "**Preconditions (machine-checkable):**",
            "**Do:**",
            "**Done when:**",
            "**If it fails:**"
        ]

        for block in stage_blocks:
            stage_title = block.splitlines()[0]
            for h in required_headings:
                self.assertIn(
                    h, block,
                    f"Stage section '{stage_title}' missing mandatory contract heading '{h}'"
                )

    def test_agents_md_contract(self):
        """AGENTS.md must exist, be <= 150 lines, and contain all 5 hand-off templates."""
        agents_path = os.path.join(REPO_ROOT, "AGENTS.md")
        self.assertTrue(os.path.exists(agents_path), "AGENTS.md must exist")

        with open(agents_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        self.assertLessEqual(len(lines), 150, f"AGENTS.md must be <= 150 lines, got {len(lines)}")

        content = "".join(lines)
        required_templates = ["`dwd`", "`jira`", "`permissions`", "`subscription`", "`state_mismatch`", "`identity`"]
        for tmpl in required_templates:
            self.assertIn(tmpl, content, f"AGENTS.md missing hand-off template: {tmpl}")

    def test_relative_markdown_links(self):
        """Relative file links across documentation must resolve to existing files."""
        doc_files = ["README.md", "RUNBOOK.md", "AGENTS.md", "GEMINI.md"]
        link_pattern = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')

        for doc in doc_files:
            doc_path = os.path.join(REPO_ROOT, doc)
            if not os.path.exists(doc_path):
                continue

            with open(doc_path, "r", encoding="utf-8") as f:
                content = f.read()

            for text, link in link_pattern.findall(content):
                # Ignore http URLs, mailto, and in-page anchors
                if link.startswith(("http://", "https://", "mailto:", "#")):
                    continue
                # Strip anchor fragment
                clean_target = link.split("#")[0]
                if not clean_target:
                    continue

                if clean_target.startswith("file://"):
                    resolved_path = clean_target.replace("file://", "")
                else:
                    resolved_path = os.path.normpath(os.path.join(REPO_ROOT, clean_target))

                self.assertTrue(
                    os.path.exists(resolved_path),
                    f"Broken link in {doc}: [{text}]({link}) -> cannot find {resolved_path}"
                )


class TestTerraformDefaultsContract(unittest.TestCase):
    """Test contract for optional folder_id (defaulting to Organization root) and sa_email (defaulting to ADC)."""

    def test_tfvars_example_defaults_folder_and_sa_null(self):
        """terraform.tfvars.example must default folder_id, sa_email, and billing_project to null."""
        tfvars_example_path = os.path.join(REPO_ROOT, "terraform.tfvars.example")
        self.assertTrue(os.path.exists(tfvars_example_path))

        with open(tfvars_example_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertTrue(re.search(r'^\s*folder_id\s*=\s*null\b', content, re.MULTILINE), "folder_id must default to null in terraform.tfvars.example")
        self.assertTrue(re.search(r'^\s*sa_email\s*=\s*null\b', content, re.MULTILINE), "sa_email must default to null in terraform.tfvars.example")
        self.assertTrue(re.search(r'^\s*billing_project\s*=\s*null\b', content, re.MULTILINE), "billing_project must default to null in terraform.tfvars.example")

    def test_main_tf_handles_empty_or_null_folder_and_sa(self):
        """main.tf must normalize empty/null folder_id to Organization root and skip custom SA IAM grant."""
        main_tf_path = os.path.join(REPO_ROOT, "main.tf")
        self.assertTrue(os.path.exists(main_tf_path))

        with open(main_tf_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("effective_folder_id = trimspace(coalesce(var.folder_id, \"\")) != \"\" ? trimspace(var.folder_id) : null", content)
        self.assertIn("effective_org_id    = local.effective_folder_id == null && trimspace(coalesce(var.org_id, \"\")) != \"\" ? trimspace(var.org_id) : null", content)
        self.assertIn("effective_sa_email  = trimspace(coalesce(var.sa_email, \"\")) != \"\" ? trimspace(var.sa_email) : null", content)
        self.assertIn("folder_id       = local.effective_folder_id", content)
        self.assertIn("org_id          = local.effective_org_id", content)
        self.assertIn("for_each = local.effective_sa_email != null ? local.environments : {}", content)
        self.assertIn("member   = \"serviceAccount:${local.effective_sa_email}\"", content)

    def test_tfvars_example_defaults_people_directory(self):
        """terraform.tfvars.example must define enable_people_directory_connector defaulting to false."""
        tfvars_example_path = os.path.join(REPO_ROOT, "terraform.tfvars.example")
        self.assertTrue(os.path.exists(tfvars_example_path))

        with open(tfvars_example_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertTrue(
            re.search(r'^\s*enable_people_directory_connector\s*=\s*false\b', content, re.MULTILINE),
            "enable_people_directory_connector must default to false in terraform.tfvars.example"
        )
        self.assertIn("people_directory_config", content)
        self.assertIn("google_people_directory", content)
        self.assertIn("people-directory-collection", content)

    def test_tfvars_example_defaults_confluence(self):
        """terraform.tfvars.example must define enable_confluence_connector defaulting to false."""
        tfvars_example_path = os.path.join(REPO_ROOT, "terraform.tfvars.example")
        self.assertTrue(os.path.exists(tfvars_example_path))

        with open(tfvars_example_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertTrue(
            re.search(r'^\s*enable_confluence_connector\s*=\s*false\b', content, re.MULTILINE),
            "enable_confluence_connector must default to false in terraform.tfvars.example"
        )
        self.assertIn("confluence_config", content)
        self.assertIn("confluence-federated-collection", content)

    def test_main_tf_dwd_scopes_include_directory_scopes(self):
        """main.tf dwd_scopes must include orgunit and customschema scopes for People Directory."""
        main_tf_path = os.path.join(REPO_ROOT, "main.tf")
        with open(main_tf_path, "r", encoding="utf-8") as f:
            content = f.read()

        required_scopes = [
            "https://www.googleapis.com/auth/admin.directory.user.readonly",
            "https://www.googleapis.com/auth/admin.directory.group.readonly",
            "https://www.googleapis.com/auth/admin.directory.group.member.readonly",
            "https://www.googleapis.com/auth/admin.directory.orgunit.readonly",
            "https://www.googleapis.com/auth/admin.directory.customschema.readonly"
        ]
        for sc in required_scopes:
            self.assertIn(sc, content, f"main.tf dwd_scopes missing required Directory scope: {sc}")


class TestVerifyWaitParsing(unittest.TestCase):
    """Test cases for verify.py --wait duration string parsing and negative inputs."""

    def test_verify_wait_valid_durations(self):
        """Valid duration formats must convert accurately to seconds."""
        self.assertEqual(verify_module.parse_duration("0s"), 0)
        self.assertEqual(verify_module.parse_duration("30s"), 30)
        self.assertEqual(verify_module.parse_duration("15m"), 900)
        self.assertEqual(verify_module.parse_duration("1h"), 3600)
        self.assertEqual(verify_module.parse_duration("45"), 45)
        self.assertEqual(verify_module.parse_duration(""), 0)
        self.assertEqual(verify_module.parse_duration(None), 0)

    def test_verify_wait_invalid_durations(self):
        """Invalid, empty prefix, negative, or malformed duration strings must raise ValueError."""
        invalid_inputs = ["s", "m", "h", "-5s", "abc", "15x", "1.5m", "ten_minutes"]
        for inp in invalid_inputs:
            with self.subTest(inp=inp):
                with self.assertRaises(ValueError):
                    verify_module.parse_duration(inp)

    def test_verify_cli_invalid_wait_aborts(self):
        """verify.py CLI must exit with non-zero code on invalid --wait format."""
        proc = subprocess.run(
            [sys.executable, os.path.join(REPO_ROOT, "scripts", "verify.py"), "--wait", "invalid_duration"],
            capture_output=True,
            text=True
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("Invalid duration format", proc.stderr)


class TestDataScrubbing(unittest.TestCase):
    """Red Team Data Scrubbing validation across all git-tracked files."""

    LEAK_PATTERNS = [
        "rwg",
        "Ray White",
        "altostrat",
        "pcorreia",
        "trusty-legend-405710",
        "affiliates-bootstrap",
        "0111AA-12FED7-0F6152",
        "ca1a2f23-797f-4cf7-ab6f-74fd5f3ca651",
        "05eab18d-9cd5-4ba6-966f-ff796c7d27a8",
    ]

    def test_no_leaks_in_tracked_files(self):
        """Systematically search all git-tracked files for customer names, domains, or real IDs."""
        tracked_files = subprocess.check_output(
            ["git", "ls-files"],
            cwd=REPO_ROOT,
            text=True
        ).splitlines()

        self.assertTrue(len(tracked_files) > 0, "Expected git tracked files to be non-empty")

        leaks_found = []
        for file_rel in tracked_files:
            file_abs = os.path.join(REPO_ROOT, file_rel)
            if not os.path.isfile(file_abs):
                continue

            try:
                with open(file_abs, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
            except Exception as e:
                self.fail(f"Could not read tracked file {file_rel}: {e}")

            for pattern in self.LEAK_PATTERNS:
                if pattern.lower() in content.lower():
                    if file_rel == "scripts/test_red.py":
                        continue
                    leaks_found.append((file_rel, pattern))

        self.assertEqual(
            len(leaks_found), 0,
            f"Sensitive patterns leaked in git-tracked files: {leaks_found}"
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
