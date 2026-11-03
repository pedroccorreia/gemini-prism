# Deep Codebase Review & Engineering Roadmap — Prism (`gemini-prism`)

**Target Repository:** `.`
**Synthesis & Verification Date:** 2026-11-03

---

## Executive Summary & Production Readiness Assessment

**Prism (`gemini-prism`)** is an Infrastructure-as-Code (Terraform `>= 1.5.0`, `hashicorp/google` and `hashicorp/google-beta` providers `~> 7.41`, `hashicorp/local` provider `>= 2.0.0` per `versions.tf:1–17`) and zero-dependency Python 3 (`scripts/*.py`) automation framework for provisioning multi-environment (`non-prod`, `prod`) **Google Cloud Gemini Enterprise (Discovery Engine)** deployments across customer environments. It orchestrates a 6-stage (`Stage 0`–`Stage 5`), human-gated deployment pipeline spanning GCP project creation (`google_project.projects` at `main.tf:505–513`), Cloud Identity user groups (`google_cloud_identity_group.users` at `main.tf:571–585`), Discovery Engine User Stores (`google_discovery_engine_user_store.default` at `main.tf:588–601`), unified Data Connectors (`google_discovery_engine_data_connector.connectors` at `main.tf:604–673` for Google Workspace via Domain-Wide Delegation, Atlassian Jira, Atlassian Confluence, Slack Enterprise, and Google People Directory), Search Engines (`google_discovery_engine_search_engine.engines` at `main.tf:676–703`), governed `default_assistant` resources (`google_discovery_engine_assistant.default` at `main.tf:717–737`), Low-Code Marketing Asset Pack packaging and API deployment (`catalog/marketing/`, `scripts/package_marketing_assets.py`, `scripts/deploy_marketing_assets.py`), and Cloud Billing Account subscription seat distribution (`scripts/allocate_licenses.py`).

### Baseline Verification Summary (Empirical Working Tree State)

All baseline verification commands were executed strictly read-only (`PYTHONDONTWRITEBYTECODE=1`) in `.`:

#### 1. `git status --porcelain` & `git diff --stat`
```text
$ git status --porcelain
 M .github/issues/04_people_directory_connector.md
 M .gitignore
 M AGENTS.md
 M Makefile
 M PRACTITIONERS_GUIDE.md
 M README.md
 M RUNBOOK.md
 M main.tf
 M outputs.tf
 M scripts/allocate_licenses.py
 M scripts/status.py
 M scripts/test_red.py
?? catalog/
?? scripts/deploy_marketing_assets.py
?? scripts/package_marketing_assets.py

$ git diff --stat
 .github/issues/04_people_directory_connector.md |   4 +-
 .gitignore                                      |   1 +
 AGENTS.md                                       |  18 +-
 Makefile                                        |  15 +-
 PRACTITIONERS_GUIDE.md                          | 157 ++++---
 README.md                                       |   8 +
 RUNBOOK.md                                      |  55 ++-
 main.tf                                         | 150 ++++++-
 outputs.tf                                      |  50 ++-
 scripts/allocate_licenses.py                    |  20 +-
 scripts/status.py                               | 173 ++++++--
 scripts/test_red.py                             | 552 +++++++++++++++++++++++-
 12 files changed, 1029 insertions(+), 174 deletions(-)
```

#### 2. Summary of Diagnostic Verification Commands

| Verification Command | Exit Code | Empirical Output | Root Cause |
| :--- | :---: | :--- | :--- |
| `git status --porcelain && git diff --stat` | `0` | `12 files changed, 1029 insertions(+), 174 deletions(-)` + 3 untracked paths (`catalog/`, `scripts/deploy_marketing_assets.py`, `scripts/package_marketing_assets.py`) | Uncommitted multi-branch changes for Slack `v3` (`FEDERATED` + `ACTIONS`), Confluence credential fallback, and Low-Code Marketing Asset Pack |
| `terraform fmt -check -diff` | `0` | Clean (zero formatting diffs) | All `.tf` files adhere to canonical HCL formatting |
| `PYTHONDONTWRITEBYTECODE=1 python3 -B scripts/package_marketing_assets.py --check` | `0` | `Status       : PASS`<br>`Budget Usage : 3 / 3 max items (2 low-code agents, 1 shared skills)` | Marketing catalog validator passes on `brand-kit-governance`, `video-social-motion-agent`, and `visual-copy-campaign-agent` |
| `terraform validate -no-color` | **`1`** | **16 `Error: Reference to undeclared input variable` blocks** in `main.tf:337` (`var.slack_auth_type`), `340` (`var.slack_auth`), `341` (`var.slack_config`), `345, 346, 347` (`var.slack_auth`), and `352, 353 [x3], 358, 360, 363, 365, 368, 371` (`var.slack_config`) (with further references to `var.enable_slack_connector`, `var.slack_config`, and `var.slack_auth` at `main.tf:377–420, 677, 707, 718` and `outputs.tf:171, 178, 201–204`) | `enable_slack_connector`, `slack_auth_type`, `slack_auth`, and `slack_config` are referenced in `main.tf` and `outputs.tf` but missing from `variables.tf` (`CODE-01`, `DEPLOY-01`, `DOC-01`) |
| `PYTHONDONTWRITEBYTECODE=1 GH_TOKEN= GITHUB_TOKEN= GH_CONFIG_DIR=/tmp/empty_gh python3 -B scripts/test_red.py` | **`1`** | **`Ran 96 tests in 1.082s — FAILED (failures=4)`** across 13 `unittest.TestCase` classes (`2,651` lines in `scripts/test_red.py`):<br>1. `TestTerraformDefaultsContract.test_slack_v3_federated_defaults_contract` (`scripts/test_red.py:1723`): `AssertionError: None is not true`<br>2. `TestConfigureCLI.test_configure_interactive_questions_contract` (`scripts/test_red.py:1921`): `AssertionError: 'slack' not found in ['workspace', 'jira', 'confluence', 'people_directory']`<br>3. `TestConfigureCLI.test_configure_stage_0_safety_guard_forces_enable_false` (`scripts/test_red.py:2000`): `AssertionError: 1 != 0`<br>4. `TestConfigureCLI.test_configure_enable_connectors_stage_2_success` (`scripts/test_red.py:2053`): `AssertionError: False is not true` | Missing Slack defaults in `terraform.tfvars.example` and `variables.tf` (`CODE-01`), and missing `"slack"` / `"confluence"` support in `scripts/configure.py` (`CODE-02`, `DEPLOY-03`) |

### Production Readiness Verdict: **BLOCKED (Pre-Production / Broken Working Tree)**

The repository cannot currently execute a clean Stage 0 through Stage 5 customer deployment without code fixes:
1. **Immediate Build & Stage 0–3 Blockers (`CODE-01`, `CODE-02`, `DEPLOY-01`–`DEPLOY-03`, `DOC-01`, `DOC-02`):** Incomplete integration of the Slack `v3` (`FEDERATED` + `ACTIONS`) and Confluence connectors across `variables.tf`, `terraform.tfvars.example`, `Makefile`, and `scripts/configure.py` breaks `terraform validate`, `make plan-foundation`, `make plan-connectors`, `make enable-connectors`, `make slack-checklist`, and 4 unit tests in `scripts/test_red.py`.
2. **Security & State Exposure (`CODE-03`, `CODE-11`, `DEPLOY-09`):** `main.tf:213–226` strips Terraform's `sensitive` protection from `confluence_auth.client_secret`, `jira_auth.client_secret`, and `api_token` via `nonsensitive()` without re-wrapping the resulting `params` (`main.tf:309, 315`) or `action_params` (`main.tf:323`) values in `sensitive()`, exposing secrets in plaintext in `terraform plan`/`apply` output; `main.tf:344–348, 410–418` omits `nonsensitive()` on `var.slack_auth.client_id` in the `action_params` ternary condition; and `versions.tf:1–17` configures no remote state backend.
3. **Broken Stage 3, 4 & 5 Operational Loops (`CODE-04`, `CODE-05`, `CODE-08`, `DEPLOY-05`–`DEPLOY-08`):**
   - **Stage 3 (`DEPLOY-08`):** Provisioning `google_discovery_engine_search_engine.engines` with `search_add_ons = ["SEARCH_ADD_ON_LLM"]` (`main.tf:676–703`, line `697`) causes GCP to auto-create `default_assistant` server-side, so `google_discovery_engine_assistant.default` (`main.tf:717–737`) fails with `HTTP 409 ALREADY_EXISTS` on initial apply.
   - **Stage 4 (`CODE-04`, `CODE-05`, `DEPLOY-05`, `DEPLOY-06`):** `allocate_licenses.py --discover` crashes before reaching `if args.discover:` at line `452` when `subscription_id` is empty (`allocate_licenses.py:361–364, 434`); `run_preflight_assertions()` (`allocate_licenses.py:171–184`) checks gross requested seats instead of net delta seats (blocking idempotent re-runs and `--configure-auto-register`); and `Makefile:78–79` (`make licenses`) never writes `license_config_names` back into `terraform.tfvars` or updates `google_discovery_engine_user_store.default` (`main.tf:588–601`), trapping `make status` (`status.py:658–673`) in Stage 4.
   - **Stage 5 (`CODE-08`, `DEPLOY-07`):** `check_data_connectors()` (`verify.py:130–131`) overwrites connector state `"INITIALIZING"` to `status = "WARN"`, causing `has_creating` (`verify.py:345–349`) to evaluate to `False` and `make verify` to exit `0` on the first poll iteration without waiting, while `verify_project()` (`verify.py:229–248`) accepts `expected_seats` and never checks it.
4. **Documentation & CLI Invocation Drift (`DOC-01`–`DOC-12`):** `AGENTS.md:6, 26, 42` and `.agent/workflows/deploy.md:7, 11` instruct running `make status --json` (which fails in GNU Make with `make: unrecognized option '--json'`); `PRACTITIONERS_GUIDE.md:133, 136–151` lists 9 DWD OAuth scopes (contradicting 12 scopes in `PRACTITIONERS_GUIDE.md:628`, `RUNBOOK.md:156, 192`, and `main.tf:482–495`); `PRACTITIONERS_GUIDE.md:188–200` documents `DATA_INGESTION` for Jira (violating `AGENTS.md:15, 22`); and `main.tf:455` uses `DATA_INGESTION` for `people_directory` without an explicit exception in `AGENTS.md:15, 22`.

---

## Part 1: Existing Issues & Actionable Improvements — Code (`CODE-01` – `CODE-14`)

### Summary Table (`CODE-01` – `CODE-14`)

| ID | Severity | File(s) & Line(s) | Summary | Roadmap Ref |
| :--- | :---: | :--- | :--- | :---: |
| **`CODE-01`** | **Critical** | `main.tf:331–422, 477, 677, 707, 718`; `outputs.tf:166–209`; `variables.tf:79–90, 268–302`; `terraform.tfvars.example:81–94` | Undeclared Slack variables (`enable_slack_connector`, `slack_auth_type`, `slack_auth`, `slack_config`) break `terraform validate` (16 errors) and `test_red.py:1723` | `RM-01` |
| **`CODE-02`** | **Critical** | `scripts/configure.py:38–91, 102–180, 270–328, 357–446, 449–580, 871–944, 1037–1041` | `configure.py` omits `"slack"` across Stage 0/2 logic, hardcodes `valid_set` at line `1037` (rejecting `"confluence"` & `"slack"`), and only audits Foundation/Jira inputs (`3 failing tests` at `test_red.py:1921, 2000, 2053`) | `RM-01` |
| **`CODE-03`** | **High** | `main.tf:163–181, 208–226, 306–324, 344–348, 410–418, 604–673`; `variables.tf:160–172, 254–266` | `nonsensitive()` in `main.tf:213–226` leaks Confluence/Jira OAuth secrets and API tokens in plaintext plan output; `main.tf:410` evaluates sensitive `var.slack_auth.client_id` without `nonsensitive()` | `RM-03` |
| **`CODE-04`** | **High** | `scripts/allocate_licenses.py:348–369, 432–455`; `main.tf:740–760` | `--discover` Catch-22: `load_config()` at line `434` aborts on empty `subscription_id` (`361–364`) before reaching `if args.discover:` at line `452` | `RM-05` |
| **`CODE-05`** | **High** | `scripts/allocate_licenses.py:168–188, 468–482, 503–528, 569`; `Makefile:75–79`; `scripts/status.py:658–673` | `run_preflight_assertions()` compares gross `total_requested_seats` against remaining `availableLicenseCount` instead of net delta seats, breaking re-runs and `--configure-auto-register` | `RM-05` |
| **`CODE-06`** | **High** | `main.tf:436–471`; `variables.tf:44–48, 209–235`; `outputs.tf:143–164`; `terraform.tfvars.example:8, 84–94`; `scripts/status.py:894–921`; `scripts/test_red.py:1744` | `people_directory_environment_connectors` ignores `var.people_directory_config` (`data_source`, `sync_mode`, `entities`), conflicts with `terraform.tfvars.example:85, 92–93` / `outputs.tf:149` / `status.py:907–916` / `AGENTS.md:15, 22`, and passes unvalidated `var.workspace_admin_email` | `RM-01`, `RM-07` |
| **`CODE-07`** | **High** | `scripts/status.py:41–110`; `scripts/configure.py:197–257` | Duplicated regex HCL parser (`parse_tfvars`) truncates `#` inside quoted strings (`status.py:57`, `configure.py:213`), fails on nested maps (`extra_params`), and diverges on empty maps (`status.py:62` vs `configure.py:218`) | `RM-07` |
| **`CODE-08`** | **High** | `scripts/verify.py:71–74, 92, 127–138, 198–215, 229–248, 305–365`; `scripts/allocate_licenses.py:51`; `scripts/status.py:748, 803` | `verify_project()` ignores `expected_seats` (`229, 331`), exits `0` on `WARN`/`SKIPPED`/`EXPIRED` (`241`), overwrites `INITIALIZING` to `WARN` (`130–131`), never refreshes OAuth token in `--wait` (`305, 315`), and omits socket timeouts | `RM-06` |
| **`CODE-09`** | **High** | `scripts/test_red.py:2336–2378`; `scripts/create_github_issues.sh:7, 40–95` | `test_create_github_issues_script_registration_and_args` runs `create_github_issues.sh` with ambient `gh` auth / `GITHUB_TOKEN`, risking live GitHub issue creation on `org-owner/gemini-prism` | `RM-04` |
| **`CODE-10`** | **Medium** | `scripts/status.py:113–121, 131–165, 183, 271, 297, 576–628, 932, 967` | `status.py` (`parse_state`, `determine_status`, `check_identity`) silently ignores corrupted `terraform.tfstate` (`_error`), skips Workspace connector state checks in Stage 3, ignores `--deep`, and checks ADC by file existence only | `RM-07`, `RM-08` |
| **`CODE-11`** | **Medium** | `scripts/configure.py:412–416, 567–576, 890–894`; `Makefile:66–73` | `update_tfvars()` writes `.env.jira` with unescaped single quotes (`export TF_VAR_jira_auth='{jira_auth_str}'`), non-atomic `os.chmod(..., 0o600)`, no `Makefile` sourcing, and no `.env.confluence`/`.env.slack` parity | `RM-03` |
| **`CODE-12`** | **Medium** | `main.tf:505–513, 740–760`; `variables.tf:1–78`; `versions.tf:1–17`; `bootstrap.sh:41–58` | Missing `validation {}` blocks on `customer_id`, `workspace_customer_id`, `billing_account`, `location`; `substr` trailing space risk at `main.tf:507`; `non-prod` fallback & missing `file_permission = "0600"` on `local_file.license_allocations` (`main.tf:740–760`); unguarded `terraform apply` in `bootstrap.sh:42` | `RM-08`, `RM-09` |
| **`CODE-13`** | **Low** | `scripts/test_red.py:406–429, 2299–2311`; `.github/workflows/terraform.yml:28–41` | Non-hermetic test dependency on `REPO_ROOT/terraform.tfstate` (`test_status_legacy_workspace_state_triggers_mismatch`) and hardcoded Git branch allowlist (`test_git_branch_contract`); missing `package_marketing_assets.py --check` in CI | `RM-04` |
| **`CODE-14`** | **Medium** | `scripts/deploy_marketing_assets.py:39, 134–169, 213–271, 693–726, 865`; `main.tf:30–34`; `Makefile:30, 93–94`; `scripts/test_red.py:2559–2648` | `discover_environment()` skips Prism's `drive-collection_google_drive` DataStore (`preferred_prefixes` expects `"google-drive"`) and hardcodes `default_collection`; `_publish_and_enable_agent()` swallows publish/review/enable HTTP errors; `--dry-run` builds `.zip` and requires live GCP auth | `RM-04`, `RM-11` |

---

### Detailed Code Findings & Actionable Fixes

#### `CODE-01` [Critical] — Undeclared Slack Connector Variables in `variables.tf` and `terraform.tfvars.example` Break `terraform validate` and Test Suite
- **Category:** Code / Terraform IaC
- **Severity:** `Critical`
- **Exact File(s) & Line(s):**
  - `./main.tf` (lines `331–422`, `477`, `677`, `707`, `718`)
  - `./outputs.tf` (lines `166–209`)
  - `./variables.tf` (lines `79–90`, `268–302`)
  - `./terraform.tfvars.example` (lines `19`, `81–94`)
  - `./scripts/test_red.py` (lines `1714–1729`)
- **Evidence Quote / Snippet:**
  - `main.tf:330–355`:
```hcl
  # Map user-friendly Slack auth type to canonical Discovery Engine auth_type
  effective_slack_auth_type = {
    "OAUTH"      = "OAUTH"
    "OAUTH2"     = "OAUTH"
    "BOT_TOKEN"  = "API_TOKEN"
    "USER_TOKEN" = "API_TOKEN"
    "API_TOKEN"  = "API_TOKEN"
  }[var.slack_auth_type]

  effective_slack_team_id = try(coalesce(
    trimspace(nonsensitive(try(var.slack_auth.team_id, ""))),
    trimspace(try(var.slack_config.team_id, ""))
  ), "")

  effective_slack_token = try(coalesce(
    trimspace(try(var.slack_auth.bot_token, "")),
    trimspace(try(var.slack_auth.user_token, "")),
    trimspace(try(var.slack_auth.api_token, ""))
  ), "")

  # Default data source version: Discovery Engine production pins "slack" to v3 (PUBLIC_GA Federated + Actions)
  default_slack_version     = 3
  effective_slack_version   = coalesce(var.slack_config.data_source_version, local.default_slack_version)
  effective_slack_modes     = coalesce(var.slack_config.enable_actions, false) ? distinct(concat(coalesce(var.slack_config.connector_modes, ["FEDERATED"]), ["ACTIONS"])) : coalesce(var.slack_config.connector_modes, ["FEDERATED"])
  is_slack_federated        = contains(local.effective_slack_modes, "FEDERATED") || local.effective_slack_version >= 3
  effective_slack_sync_mode = local.is_slack_federated ? null : (upper(coalesce(var.slack_config.sync_mode, "PERIODIC")) == "INCREMENTAL" ? "PERIODIC" : coalesce(var.slack_config.sync_mode, "PERIODIC"))
```
  - `main.tf:376–386`:
```hcl
  # Slack Enterprise connector per environment (when enabled)
  slack_environment_connectors = var.enable_slack_connector ? {
    for env_key, env_val in local.environments :
    "${env_key}-slack" => {
      env_key             = env_key
      connector           = "slack"
      data_source         = coalesce(var.slack_config.data_source, "slack")
      data_source_version = local.is_slack_federated ? null : local.effective_slack_version
      display_name        = "Slack Enterprise"
      collection_id       = try(coalesce(trimspace(var.slack_config.collection_id)), "") != "" ? trimspace(var.slack_config.collection_id) : "slack-collection"
      project_id          = google_project.projects[env_key].project_id
```
  - `outputs.tf:166–175`:
```hcl
output "slack_checklist" {
  description = "Slack Enterprise connector configuration and onboarding checklist per environment"
  value = {
    for k, v in local.environments : k => {
      project_id              = google_project.projects[k].project_id
      instance_uri            = try(coalesce(var.slack_config.instance_uri), "")
      team_id                 = try(nonsensitive(local.effective_slack_team_id), local.effective_slack_team_id)
      auth_type               = local.effective_slack_auth_type
      data_source_version     = local.effective_slack_version
      oauth_callback_url      = "https://vertexaisearch.cloud.google.com/oauth-redirect"
```
  - `variables.tf:79–90`:
```hcl
variable "planned_connectors" {
  type        = list(string)
  description = "List of enterprise connectors planned for deployment (workspace, jira, confluence, people_directory)"
  default     = ["workspace"]

  validation {
    condition = alltrue([
      for c in var.planned_connectors : contains(["workspace", "jira", "confluence", "people_directory"], c)
    ])
    error_message = "Each element of planned_connectors must be one of: 'workspace', 'jira', 'confluence', 'people_directory'."
  }
}
```
  - `scripts/test_red.py:1714–1729`:
```python
    def test_slack_v3_federated_defaults_contract(self):
        """Slack connector defaults must align with Discovery Engine v3 PUBLIC_GA Federated + Actions spec."""
        with open(os.path.join(REPO_ROOT, "variables.tf"), "r", encoding="utf-8") as f:
            vars_content = f.read()
        with open(os.path.join(REPO_ROOT, "terraform.tfvars.example"), "r", encoding="utf-8") as f:
            example_content = f.read()
        with open(os.path.join(REPO_ROOT, "main.tf"), "r", encoding="utf-8") as f:
            main_content = f.read()

        self.assertTrue(re.search(r'^\s*enable_slack_connector\s*=\s*false\b', example_content, re.MULTILINE))
        self.assertTrue(re.search(r'^\s*slack_auth_type\s*=\s*"OAUTH"', example_content, re.MULTILINE))
        self.assertIn('entities                     = optional(list(string), ["conversation", "message", "file"])', vars_content)
        self.assertIn('incremental_refresh_interval = optional(string, "10800s")', vars_content)
        self.assertIn('"unused_auth_param" = "unused"', main_content)
        self.assertIn('https://mcp.slack.com', main_content)
        self.assertIn('"ByoOAuth"', main_content)
```
- **Problem Description:**
  `main.tf` (`330–422`, `477`, `677`, `707`, `718` — where `local.slack_environment_connectors` is merged into `local.environment_connectors` at line `477` and provisioned by the unified `resource "google_discovery_engine_data_connector" "connectors"` at `main.tf:604–673`) and `outputs.tf` (`166–209` — `output "slack_checklist"`) reference `var.enable_slack_connector`, `var.slack_auth_type`, `var.slack_auth`, and `var.slack_config`. However:
  1. `variables.tf` ends at line `302` after `confluence_config` without declaring any of those 4 Slack variables, and `variables.tf:86` omits `"slack"` from `var.planned_connectors`.
  2. `terraform.tfvars.example` ends at line `94` after `people_directory_config` without `enable_slack_connector = false`, `slack_auth_type = "OAUTH"`, or `slack_config = { ... }`.
  3. Running `terraform validate -no-color` fails with exit code `1` and 16 `Error: Reference to undeclared input variable` blocks (`main.tf:337, 340, 341, 345, 346, 347, 352, 353 [x3], 358, 360, 363, 365, 368, 371`), and `TestTerraformDefaultsContract.test_slack_v3_federated_defaults_contract` fails at `scripts/test_red.py:1723` with `AssertionError: None is not true`.
- **Concrete Actionable Improvement:**
  1. In `variables.tf:81, 86, 88`, add `"slack"` to `planned_connectors`:
     `for c in var.planned_connectors : contains(["workspace", "jira", "confluence", "slack", "people_directory"], c)`
  2. Append the complete, contract-compliant Slack variable declarations to `variables.tf` (covering all 7 attributes accessed on `var.slack_auth` in `main.tf:340–415`, all 20 attributes accessed on `var.slack_config` in `main.tf:341–421` and `outputs.tf:171–204`, and the exact string literals asserted by `scripts/test_red.py:1725–1726`):
     - `variable "enable_slack_connector"` (`type = bool`, `default = false`)
     - `variable "slack_auth_type"` (`type = string`, `default = "OAUTH"`, validating `contains(["OAUTH", "OAUTH2", "BOT_TOKEN", "USER_TOKEN", "API_TOKEN"], var.slack_auth_type)`)
     - `variable "slack_auth"` (`sensitive = true`, `default = {}`, `type = object({ team_id = optional(string, ""), bot_token = optional(string, ""), user_token = optional(string, ""), api_token = optional(string, ""), client_id = optional(string, ""), client_secret = optional(string, ""), refresh_token = optional(string, "") })`)
     - `variable "slack_config"` (`default = {}`, `type = object({ instance_uri = optional(string, ""), team_id = optional(string, ""), collection_id = optional(string, "slack-collection"), data_source = optional(string, "slack"), data_source_version = optional(number, 3), connector_modes = optional(list(string), ["FEDERATED"]), sync_mode = optional(string, "PERIODIC"), refresh_interval = optional(string, "86400s"), incremental_refresh_interval = optional(string, "10800s"), entities = optional(list(string), ["conversation", "message", "file"]), static_ip_enabled = optional(bool, false), enable_actions = optional(bool, false), enabled_actions = optional(list(string), []), channels_include = optional(list(string), []), channels_exclude = optional(list(string), []), include_private_channels = optional(bool, false), include_dms = optional(bool, false), auto_run_disabled = optional(bool, false), incremental_sync_disabled = optional(bool, false), extra_params = optional(map(string), {}) })`, with `validation` enforcing `contains(coalesce(var.slack_config.connector_modes, ["FEDERATED"]), "FEDERATED") && !contains(coalesce(var.slack_config.connector_modes, ["FEDERATED"]), "DATA_INGESTION")`)
  3. Append the default Slack block (`enable_slack_connector = false`, `slack_auth_type = "OAUTH"`, `slack_config = { ... }`) to `terraform.tfvars.example`.

---

#### `CODE-02` [Critical] — Incomplete Slack & Confluence Integration in `scripts/configure.py` Breaks Stage 0 Combo-Box, Stage 2 `enable-connectors`, and 3 Unit Tests
- **Category:** Code / Python CLI (`scripts/configure.py`)
- **Severity:** `Critical`
- **Exact File(s) & Line(s):**
  - `./scripts/configure.py` (lines `38–91`, `102–180`, `270–328`, `357–446`, `449–580`, `871–944`, `1037–1041`)
  - `./scripts/test_red.py` (lines `1907–1932`, `1989–2009`, `2021–2054`)
- **Evidence Quote / Snippet:**
  - `scripts/configure.py:470–475`:
```python
    # Stage 0 Safety Guard
    if stage == 0 and not allow_enable:
        updates["enable_connectors"] = False
        updates["enable_jira_connector"] = False
        updates["enable_confluence_connector"] = False
        updates["enable_people_directory_connector"] = False
```
  - `scripts/configure.py:921–926`:
```python
    updates = {
        "enable_connectors": ("workspace" in planned),
        "enable_jira_connector": ("jira" in planned),
        "enable_confluence_connector": ("confluence" in planned),
        "enable_people_directory_connector": ("people_directory" in planned),
    }
```
  - `scripts/configure.py:1037–1041`:
```python
            valid_set = {"workspace", "jira", "people_directory"}
            for c in planned:
                if c not in valid_set:
                    print(f"Error: Invalid connector '{c}'. Allowed: 'workspace', 'jira', 'people_directory'", file=sys.stderr)
                    sys.exit(1)
```
- **Problem Description:**
  `scripts/configure.py` was only partially updated during the Confluence and Slack branch merges, causing four distinct defects (three of which directly cause unit test failures in `scripts/test_red.py`):
  1. **Hardcoded `valid_set` in `--apply-json` / `--connectors` (`configure.py:1037–1041`)**: `valid_set` is hardcoded to `{"workspace", "jira", "people_directory"}`. Passing `"confluence"` (even though `"confluence"` is in `CONNECTOR_OPTIONS` at lines `65–77`) or `"slack"` via `--apply-json` prints `Error: Invalid connector ...` and exits with code `1`. This directly causes `TestConfigureCLI.test_configure_stage_0_safety_guard_forces_enable_false` to fail at `scripts/test_red.py:2000` with `AssertionError: 1 != 0`.
  2. **Missing `"slack"` Entry in `CONNECTOR_OPTIONS` (`configure.py:38–91`)**: `CONNECTOR_OPTIONS` only defines `"workspace"`, `"jira"`, `"confluence"`, and `"people_directory"`, so `get_interactive_questions()` (`configure.py:330–354`) omits `"slack"`. This causes `TestConfigureCLI.test_configure_interactive_questions_contract` to fail at `scripts/test_red.py:1921` with `AssertionError: 'slack' not found in ['workspace', 'jira', 'confluence', 'people_directory']`.
  3. **Missing `enable_slack_connector` in `determine_stage()`, `update_tfvars()`, and `enable_connectors()` (`configure.py:302–309, 471–475, 489, 519–530, 871–944`)**: `update_tfvars()` omits `updates["enable_slack_connector"] = False` in the Stage 0 Safety Guard (`471–475`) and omits `"enable_slack_connector"` from the `flag` loop (`489`) and `skip_keys` (`519–530`). Meanwhile, `enable_connectors()` (`871–944`) neither validates `slack_config` prerequisites nor includes `"enable_slack_connector": ("slack" in planned)` in `updates` (`921–926`). This causes `TestConfigureCLI.test_configure_enable_connectors_stage_2_success` to fail at `scripts/test_red.py:2053` with `AssertionError: False is not true`.
  4. **Incomplete Variable Audit (`configure.py:102–180, 357–446`)**: `VARIABLE_METADATA` and `audit_inputs()` only audit Foundation and Jira variables (`jira_config.instance_uri`, `TF_VAR_jira_auth`), ignoring Confluence, Slack, and People Directory (`workspace_admin_email`).
- **Concrete Actionable Improvement:**
  1. Add the `"slack"` connector dict to `CONNECTOR_OPTIONS` (`configure.py:38–91`) with `"value": "slack"`, `"docs_url": "https://docs.cloud.google.com/gemini/enterprise/docs/connectors/slack"`, and `"enable_flag": "enable_slack_connector"`.
  2. Replace `valid_set = {"workspace", "jira", "people_directory"}` at `configure.py:1037` with `valid_set = {opt["value"] for opt in CONNECTOR_OPTIONS}` (note: each dict in `CONNECTOR_OPTIONS` uses the key `"value"`, not `"id"`).
  3. Add `"enable_slack_connector"` to `determine_stage()` (`302–309`), `update_tfvars()` (`471–475`, `489`, `519–530`), and `enable_connectors()` (`871–944`, validating `slack_config.instance_uri` and `FEDERATED` mode and setting `"enable_slack_connector": ("slack" in planned)`).
  4. Expand `VARIABLE_METADATA` (`102–180`) and `audit_inputs()` (`357–446`) to validate Confluence, Slack, and People Directory (`workspace_admin_email`) inputs.

---

#### `CODE-03` [High] — `nonsensitive()` Strips Secret Protection in `main.tf`, Leaking OAuth Secrets and API Tokens in Terraform Plan Output, While `main.tf:410` Evaluates Sensitive `var.slack_auth.client_id` Without `nonsensitive()`
- **Category:** Code / Security & Terraform IaC
- **Severity:** `High`
- **Exact File(s) & Line(s):**
  - `./main.tf` (lines `163–181`, `208–226`, `306–324`, `344–348`, `410–418`, `604–673`)
  - `./variables.tf` (lines `160–172`, `254–266`)
- **Evidence Quote / Snippet:**
  - `main.tf:213–226`:
```hcl
  effective_confluence_client_secret = try(coalesce(
    trimspace(nonsensitive(try(var.confluence_auth.client_secret, ""))),
    trimspace(nonsensitive(try(var.jira_auth.client_secret, "")))
  ), "")

  effective_confluence_user_account = try(coalesce(
    trimspace(nonsensitive(try(var.confluence_auth.user_account, ""))),
    trimspace(nonsensitive(try(var.jira_auth.user_account, "")))
  ), "")

  effective_confluence_api_token = try(coalesce(
    trimspace(nonsensitive(try(var.confluence_auth.api_token, ""))),
    trimspace(nonsensitive(try(var.jira_auth.api_token, "")))
  ), "")
```
  - `main.tf:306–324`:
```hcl
      params = local.effective_confluence_data_source == "confluence_server" ? merge(
        { "api_token_type" = "BASIC_AUTH" },
        local.effective_confluence_user_account != "" ? { "username" = local.effective_confluence_user_account } : {},
        local.effective_confluence_api_token != "" ? { "password" = local.effective_confluence_api_token } : {},
        coalesce(var.confluence_config.extra_params, {})
        ) : merge(
        local.effective_confluence_instance_uri != "" ? { "instance_uri" = local.effective_confluence_instance_uri } : {},
        local.effective_confluence_instance_id != "" ? { "instance_id" = local.effective_confluence_instance_id } : {},
        local.effective_confluence_client_id != "" ? { "client_id" = local.effective_confluence_client_id } : {},
        local.effective_confluence_client_secret != "" ? { "client_secret" = local.effective_confluence_client_secret } : {},
        coalesce(var.confluence_config.extra_params, {})
      )
      action_params = merge(
        local.effective_confluence_instance_uri != "" ? { "instance_uri" = local.effective_confluence_instance_uri } : {},
        local.effective_confluence_instance_id != "" ? { "instance_id" = local.effective_confluence_instance_id } : {},
        { "auth_type" = "OAUTH" },
        local.effective_confluence_client_id != "" ? { "client_id" = local.effective_confluence_client_id } : {},
        local.effective_confluence_client_secret != "" ? { "client_secret" = local.effective_confluence_client_secret } : {}
      )
```
  - `main.tf:344–348`:
```hcl
  effective_slack_token = try(coalesce(
    trimspace(try(var.slack_auth.bot_token, "")),
    trimspace(try(var.slack_auth.user_token, "")),
    trimspace(try(var.slack_auth.api_token, ""))
  ), "")
```
  - `main.tf:410–418`:
```hcl
      action_params = trimspace(try(coalesce(var.slack_auth.client_id), "")) != "" ? {
        "auth_type"     = "OAUTH"
        "auth_key"      = "ByoOAuth"
        "client_id"     = var.slack_auth.client_id
        "client_secret" = try(coalesce(var.slack_auth.client_secret), "")
        } : {
        "auth_type" = "OAUTH"
        "auth_key"  = "OAuth"
      }
```
- **Problem Description:**
  1. **Plaintext Secret Exposure via `nonsensitive()` (`main.tf:213–226, 306–324, 612, 656`)**: Although `var.jira_auth` (`variables.tf:171`) and `var.confluence_auth` (`variables.tf:265`) are declared with `sensitive = true`, `main.tf:213–226` calls `nonsensitive()` directly on `client_secret` and `api_token` when computing `local.effective_confluence_client_secret` and `local.effective_confluence_api_token`. Those stripped values are then placed into `local.confluence_environment_connectors[...].params` (`main.tf:309, 315`) and `.action_params` (`main.tf:323`) and passed directly to `resource "google_discovery_engine_data_connector" "connectors"` (`params = each.value.params` at `main.tf:612`, `action_params = each.value.action_params` at `main.tf:656`) without re-applying `sensitive()`. As a result, `terraform plan` and `terraform apply` print plaintext Atlassian OAuth `client_secret` and `api_token` (`password`) values to stdout and CI logs.
  2. **Unguarded Sensitive Ternary Predicate in `main.tf:165–180, 344–348, 410–418`**: Once `var.slack_auth` is declared with `sensitive = true` in `variables.tf` (matching `var.jira_auth` and `var.confluence_auth`), evaluating `trimspace(try(coalesce(var.slack_auth.client_id), "")) != ""` at `main.tf:410` (and `var.jira_auth.* != ""` at `main.tf:165–180`, `local.effective_slack_token != ""` at `main.tf:407`) uses a sensitive value as a ternary condition whose two branches return maps with different keys (`4 keys` vs `2 keys`), which fails in Terraform unless the boolean condition is wrapped in `nonsensitive(...)`.
- **Concrete Actionable Improvement:**
  1. Wrap only boolean emptiness predicates (`!= ""`) in `nonsensitive(...)` (e.g., `nonsensitive(trimspace(try(coalesce(var.slack_auth.client_id), "")) != "")` at `main.tf:410` and `nonsensitive(trimspace(try(coalesce(var.jira_auth.client_secret), "")) != "")` at `main.tf:172, 180`).
  2. Keep secret values (`client_secret`, `api_token`, `password`, `auth_token`) wrapped in `sensitive(...)` inside `params` and `action_params` (`main.tf:166, 172, 180, 309, 315, 323, 407, 414`).

---

#### `CODE-04` [High] — `--discover` Catch-22 in `scripts/allocate_licenses.py`: `load_config()` Rejects Empty `subscription_id` Before `--discover` Can Execute
- **Category:** Code / Python CLI (`scripts/allocate_licenses.py`)
- **Severity:** `High`
- **Exact File(s) & Line(s):**
  - `./scripts/allocate_licenses.py` (lines `348–369`, `432–454`)
  - `./main.tf` (lines `740–760`)
- **Evidence Quote / Snippet:**
  - `scripts/allocate_licenses.py:361–364`:
```python
    required_fields = ["billing_account", "subscription_id", "allocations"]
    missing = [f for f in required_fields if f not in data or data[f] is None or data[f] == ""]
    if missing:
        raise ValueError(f"Missing required field(s) in {config_file}: {', '.join(missing)}")
```
  - `scripts/allocate_licenses.py:432–454`:
```python
    # Load configuration
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
```
  - `main.tf:740–748`:
```hcl
resource "local_file" "license_allocations" {
  filename = "${path.module}/config/license_allocations.json"
  content = jsonencode({
    licensing_project = try(coalesce(var.billing_project, try(values(google_project.projects)[0].project_id, "")), "")
    billing_account   = var.billing_account
    license_config_id = var.license_config_id
    subscription_id   = var.subscription_id
    subscription_tier = var.subscription_tier
    location          = var.location
```
- **Problem Description:**
  `python3 scripts/allocate_licenses.py --discover` is documented in `AGENTS.md:101, 124` and `RUNBOOK.md:277` as the discovery helper to find `subscription_id` and `license_config_id` from the Billing Account when those IDs are unknown. However, `main()` unconditionally calls `load_config(args.config_file)` at line `434` **before** checking `if args.discover:` at line `452`. When `subscription_id` is not yet set in `terraform.tfvars` (default `""` in `variables.tf:134`), `local_file.license_allocations` (`main.tf:746`) writes `"subscription_id": ""` to `config/license_allocations.json`, causing `load_config()` at line `364` to raise `ValueError: Missing required field(s) in config/license_allocations.json: subscription_id` and exit with code `1`! Furthermore, if `config/license_allocations.json` does not exist yet, running `--discover --billing-account <id> --project <id>` fails with `FileNotFoundError` at line `351`.
- **Concrete Actionable Improvement:**
  Pass `require_subscription=not (args.discover or args.list)` to `load_config()` (or handle `if args.discover:` before strict `required_fields` validation), allow `config/license_allocations.json` to be optional when `--billing-account` and `--project` are supplied on the CLI (or fall back to `parse_tfvars("terraform.tfvars")`), and validate `billing_account` before invoking `discover_billing_subscriptions()`.

---

#### `CODE-05` [High] — `run_preflight_assertions()` Compares Gross Requested Seats Against Remaining `availableLicenseCount`, Breaking Idempotent Re-runs and `--configure-auto-register`
- **Category:** Code / Python CLI (`scripts/allocate_licenses.py`)
- **Severity:** `High`
- **Exact File(s) & Line(s):**
  - `./scripts/allocate_licenses.py` (lines `168–188`, `467–482`, `503–528`, `569`)
  - `./Makefile` (lines `75–79`)
  - `./scripts/status.py` (lines `658–673`)
- **Evidence Quote / Snippet:**
  - `scripts/allocate_licenses.py:171–184`:
```python
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
```
  - `scripts/allocate_licenses.py:467–469`:
```python
    # Run Preflight Assertions for state-modifying actions
    if not args.skip_preflight and (args.distribute or args.configure_auto_register):
        try:
```
  - `scripts/allocate_licenses.py:503–506`:
```python
                    if active_cfg and current_seats >= int(seats):
                        print(f"  • Already distributed ({current_seats} seat(s) active in {cfg_short}) — skipping duplicate distribution.")
                    else:
                        delta_seats = int(seats) - current_seats
```
  - `Makefile:75–79`:
```makefile
licenses-dryrun:
	python3 scripts/allocate_licenses.py --distribute --dry-run

licenses: licenses-dryrun
	python3 scripts/allocate_licenses.py --distribute
```
- **Problem Description:**
  1. **Gross-vs-Delta Capacity Check Breaks Idempotency and `--configure-auto-register` (`allocate_licenses.py:171–184, 468`)**: While `--distribute` (`503–506`) is delta-aware (`delta_seats = int(seats) - current_seats`), `run_preflight_assertions()` (`171–184`) sums gross `total_requested_seats = sum(int(item.get("seat_count", 0)) for item in allocations)` and requires `total_requested_seats <= available_seats` before both `--distribute` and `--configure-auto-register` (`line 468`). Once seats are distributed on the first run of `make licenses` (reducing `availableLicenseCount` in the billing pool to `0`), any subsequent idempotent re-run of `make licenses`, `make licenses-dryrun`, incremental seat adjustment, or `--configure-auto-register` fails at line `179` with `ValueError: Preflight assertion failed: Insufficient license seats in billing pool!`.
  2. **Early `return` Prevents Flag Composition (`allocate_licenses.py:528, 569`)**: `if args.distribute:` ends with `return` at line `528` (and `if args.configure_auto_register:` ends with `return` at line `569`), so passing `--distribute --configure-auto-register --emit-tfvars` in a single invocation silently skips `--configure-auto-register` and `--emit-tfvars`.
  3. **Stage 4 Loop Not Closed by `make licenses` (`Makefile:78–79`, `status.py:658–673`)**: `status.py:658–662` checks `lic_config_names = tfvars.get("license_config_names", {})`, but `Makefile:78–79` only executes `python3 scripts/allocate_licenses.py --distribute` and never writes `license_config_names` back to `terraform.tfvars`.
- **Concrete Actionable Improvement:**
  1. In `run_preflight_assertions()` (`allocate_licenses.py:158–188`), query each project's active `licenseCount` via `get_license_configs()` and compute net additional seats required (`net_requested_seats = sum(max(0, int(item.get("seat_count", 0)) - current_seats) ...)`), and skip pool capacity checks when running `--configure-auto-register` without `--distribute`.
  2. Remove the early `return` statements at `allocate_licenses.py:528` and `569` so `--distribute`, `--configure-auto-register`, and `--emit-tfvars` can be combined.
  3. Update `Makefile:78–79` (`licenses` target) and `allocate_licenses.py` to persist `license_config_names` into `terraform.tfvars` after distributing seats.

---

#### `CODE-06` [High] — `people_directory_environment_connectors` Hardcodes Attributes (Ignoring `var.people_directory_config`), Conflicts with `terraform.tfvars.example` / `outputs.tf` / `status.py` / `AGENTS.md`, and Passes Unvalidated `var.workspace_admin_email`
- **Category:** Code / Terraform IaC & Python Status Engine
- **Severity:** `High`
- **Exact File(s) & Line(s):**
  - `./main.tf` (lines `436–471`)
  - `./variables.tf` (lines `44–48`, `209–235`)
  - `./outputs.tf` (lines `143–164`)
  - `./terraform.tfvars.example` (lines `8`, `84–94`)
  - `./scripts/status.py` (lines `894–921`)
  - `./scripts/test_red.py` (lines `1731–1745`)
- **Evidence Quote / Snippet:**
  - `main.tf:436–466`:
```hcl
  effective_people_directory_data_source = "native_cloud_identity"

  # Google Cloud Identity / Workspace People & Org Directory connector per environment (when enabled)
  people_directory_environment_connectors = var.enable_people_directory_connector ? {
    for env_key, env_val in local.environments :
    "${env_key}-people-directory" => {
      env_key             = env_key
      connector           = "people_directory"
      data_source         = local.effective_people_directory_data_source
      data_source_version = null
      display_name        = coalesce(var.people_directory_config.display_name, "Google People Directory")
      collection_id       = coalesce(var.people_directory_config.collection_id, "people-directory-collection")
      project_id          = google_project.projects[env_key].project_id
      entities = [
        {
          entity_name = "users"
          params      = length(local.people_directory_entity_params) > 0 ? jsonencode(local.people_directory_entity_params) : null
        }
      ]
      connector_modes              = ["DATA_INGESTION"]
      sync_mode                    = "PERIODIC"
      refresh_interval             = coalesce(var.people_directory_config.refresh_interval, "86400s")
      incremental_refresh_interval = null
      static_ip_enabled            = false
      auto_run_disabled            = coalesce(var.people_directory_config.auto_run_disabled, false)
      incremental_sync_disabled    = false
      instance_uri                 = ""
      params = {
        "impersonated_user_email_address" = var.workspace_admin_email
        "super_admin_service_account"     = "service-${google_project.projects[env_key].number}@gcp-sa-discoveryengine.iam.gserviceaccount.com"
      }
```
  - `variables.tf:44–48`:
```hcl
variable "workspace_admin_email" {
  type        = string
  description = "The email address of a Google Workspace Administrator (optional)"
  default     = null
}
```
  - `variables.tf:215–227`:
```hcl
variable "people_directory_config" {
  type = object({
    data_source             = optional(string, "native_cloud_identity")
    collection_id           = optional(string, "people-directory-collection")
    display_name            = optional(string, "Google People Directory")
    include_suspended_users = optional(bool, false)
    org_units_include       = optional(list(string), []) # Target specific OUs (e.g. /Employees)
    custom_schemas_include  = optional(list(string), []) # Include custom employee attributes
    refresh_interval        = optional(string, "86400s") # Daily synchronization
    sync_mode               = optional(string, "PERIODIC")
    entities                = optional(list(string), ["users"])
    auto_run_disabled       = optional(bool, false)
  })
```
  - `terraform.tfvars.example:84–94`:
```hcl
people_directory_config = {
  data_source             = "google_people_directory"
  collection_id           = "people-directory-collection"
  display_name            = "Google People Directory"
  include_suspended_users = false
  org_units_include       = [] # e.g. ["/Employees", "/Contractors"]
  custom_schemas_include  = [] # e.g. ["Skills", "Certifications"]
  refresh_interval        = "86400s"
  sync_mode               = "INCREMENTAL"
  entities                = ["user_profile", "job_architecture", "reporting_hierarchy", "location_contact", "custom_attributes"]
}
```
- **Problem Description:**
  1. **Schema Drift Across `variables.tf`, `main.tf`, `terraform.tfvars.example`, `outputs.tf`, `status.py`, and `test_red.py`**: While `variables.tf:215–227` already defaults `people_directory_config` to `data_source = optional(string, "native_cloud_identity")`, `sync_mode = optional(string, "PERIODIC")`, and `entities = optional(list(string), ["users"])`, `main.tf:436, 449–456` hardcodes those three values (ignoring `var.people_directory_config.data_source`, `sync_mode`, and `entities`). Meanwhile, `terraform.tfvars.example:85, 92–93`, `outputs.tf:149`, and `scripts/status.py:907–910` still specify the legacy values `"google_people_directory"`, `"INCREMENTAL"`, and `["user_profile", "job_architecture", "reporting_hierarchy", "location_contact", "custom_attributes"]`, and `scripts/test_red.py:1744` (`test_tfvars_example_defaults_people_directory`) explicitly asserts `self.assertIn("google_people_directory", content)`.
  2. **Unvalidated Required `var.workspace_admin_email` (`main.tf:464`, `variables.tf:44–48`)**: When `var.enable_people_directory_connector = true`, `main.tf:464` passes `"impersonated_user_email_address" = var.workspace_admin_email`. Yet `variables.tf:44–48` sets `default = null`, `terraform.tfvars.example:8` sets `"admin@example.com"`, and neither Terraform nor `status.py`/`configure.py` validates that `workspace_admin_email` is non-null and non-placeholder when `enable_people_directory_connector = true`.
  3. **DWD Scope Count Drift in `status.py:912–916` vs `outputs.tf:155–160`**: `outputs.tf:155–160` lists 4 Directory scopes (including `https://www.googleapis.com/auth/directory.readonly`), whereas the fallback in `scripts/status.py:912–916` only lists 3 scopes.
  4. **Undocumented Exception to `AGENTS.md:15, 22` (`FEDERATED` vs `DATA_INGESTION`)**: `main.tf:455` sets `connector_modes = ["DATA_INGESTION"]` because Discovery Engine's `native_cloud_identity` data source requires periodic ingestion, which directly conflicts with `AGENTS.md:15, 22` unless `native_cloud_identity` is documented as an explicit exception.
- **Concrete Actionable Improvement:**
  1. Add a `lifecycle { precondition { ... } }` block on `google_discovery_engine_data_connector.connectors` (`main.tf:604–673`) and checks in `status.py` and `configure.py` requiring a valid, non-placeholder `workspace_admin_email` whenever `enable_people_directory_connector = true`.
  2. Align `terraform.tfvars.example:84–94`, `outputs.tf:149–152`, `scripts/status.py:907–916` (including all 4 Directory scopes), and `scripts/test_red.py:1744` (`test_tfvars_example_defaults_people_directory`) with `"native_cloud_identity"`, `"PERIODIC"`, and `["users"]`, and document the `native_cloud_identity` `DATA_INGESTION` exception in `AGENTS.md:15, 22`.

---

#### `CODE-07` [High] — Duplicated, Divergent Regex HCL Parser (`parse_tfvars`) in `scripts/status.py` and `scripts/configure.py`
- **Category:** Code / Python Architecture
- **Severity:** `High`
- **Exact File(s) & Line(s):**
  - `./scripts/status.py` (lines `41–110`)
  - `./scripts/configure.py` (lines `197–257`)
- **Evidence Quote / Snippet:**
  - `scripts/status.py:53–65`:
```python
    # Remove single-line comments (# or //)
    lines = []
    for line in content.splitlines():
        line = re.sub(r'(?<!:)\/\/.*$', '', line)
        line = re.sub(r'#.*$', '', line)
        lines.append(line)
    clean_text = "\n".join(lines)

    # Strip inline empty maps (e.g. extra_params = {}) before matching top-level maps
    clean_text_for_maps = re.sub(r'([a-zA-Z0-9_-]+)\s*=\s*\{\s*\}', '', clean_text)

    # Match maps first: key = { ... }
    map_matches = re.findall(r'^\s*([a-zA-Z0-9_-]+)\s*=\s*\{(.*?)\}', clean_text_for_maps, re.MULTILINE | re.DOTALL)
```
  - `scripts/configure.py:210–218`:
```python
    lines = []
    for line in content.splitlines():
        line = re.sub(r'(?<!:)\/\/.*$', '', line)
        line = re.sub(r'#.*$', '', line)
        lines.append(line)
    clean_text = "\n".join(lines)

    # Match maps: key = { ... }
    map_matches = re.findall(r'^\s*([a-zA-Z0-9_-]+)\s*=\s*\{(.*?)\}', clean_text, re.MULTILINE | re.DOTALL)
```
- **Problem Description:**
  `parse_tfvars()` is duplicated across `scripts/status.py` and `scripts/configure.py` with divergent regex logic and four empirically verified parsing bugs:
  1. **Divergence on Inline Empty Maps (`extra_params = {}`)**: `status.py:62` strips `([a-zA-Z0-9_-]+)\s*=\s*\{\s*\}`, whereas `configure.py:218` does not. If `extra_params = {}` appears inside `jira_config`, `confluence_config`, or `slack_config`, `configure.py:218`'s non-greedy `\{(.*?)\}` stops at `extra_params`'s closing `}`, dropping all subsequent keys in that block from the map and letting `text_without_maps` (`configure.py:241`) leak the remaining map keys into the top-level dict.
  2. **Non-Empty Nested Maps Break Both Parsers**: If `extra_params = { "custom_key" = "custom_val" }` is non-empty, both `status.py:65` and `configure.py:218` terminate the outer map match at the inner `}` and leak subsequent keys (such as `static_ip_enabled`) to the top-level dict.
  3. **Top-Level Empty Maps Deleted in `status.py:62`**: `clean_text_for_maps = re.sub(r'([a-zA-Z0-9_-]+)\s*=\s*\{\s*\}', '', clean_text)` strips top-level empty maps such as `confluence_config = {}` or `license_config_names = {}` from `data` in `status.py`, whereas `configure.py:218` preserves `{}`.
  4. **Unquoted Comment Stripping (`#` inside strings)**: `re.sub(r'#.*$', '', line)` (`status.py:57`, `configure.py:213`) strips everything from `#` to end-of-line even when `#` is inside a double-quoted string literal (e.g., `assistant_instructions = "Use #help channel"`), corrupting the string and dropping the variable.
- **Concrete Actionable Improvement:**
  Consolidate `parse_tfvars()` into a shared module (`scripts/prism_core.py`) imported by both `status.py` and `configure.py`, using a character-scanning tokenizer that tracks string quotes (`"..."` with `\"` escapes) before stripping `#` / `//` comments and tracks brace depth (`{` / `}`) to parse nested maps accurately.

---

#### `CODE-08` [High] — `scripts/verify.py` Ignores `expected_seats`, Overwrites `INITIALIZING` to `WARN` (Bypassing `--wait`), Exits `0` on `WARN`/`SKIPPED`/`EXPIRED`, Never Refreshes OAuth Tokens, and Omits Socket Timeouts
- **Category:** Code / Verification Engine (`scripts/verify.py`)
- **Severity:** `High`
- **Exact File(s) & Line(s):**
  - `./scripts/verify.py` (lines `71–74`, `92`, `127–138`, `148–215`, `229–248`, `305–365`)
  - `./scripts/allocate_licenses.py` (line `51`)
  - `./scripts/status.py` (lines `748`, `803`)
- **Evidence Quote / Snippet:**
  - `scripts/verify.py:71–74`:
```python
    try:
        with urllib.request.urlopen(req) as resp:
            content = resp.read().decode("utf-8")
            return json.loads(content) if content else {}
```
  - `scripts/verify.py:127–133`:
```python
        status = state
        if errors or state in ("FAILED", "ERROR", "INITIALIZATION_FAILED") or "FAIL" in state:
            status = "ERROR"
        elif blocking_reasons or state in ("PAUSED", "INITIALIZING"):
            status = "WARN"

        results.append((f"Connector ({data_source})", status, ", ".join(details_parts)))
```
  - `scripts/verify.py:198–215`:
```python
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
```
  - `scripts/verify.py:229–242`:
```python
def verify_project(project_id, location, token, expected_seats=None, silent=False):
    all_checks = []
    all_checks.extend(check_user_store(project_id, location, token))
    all_checks.extend(check_license_configs(project_id, location, token))
    all_checks.extend(check_data_connectors(project_id, location, token))
    all_checks.extend(check_search_engine(project_id, location, token))
    all_checks.extend(check_assistant(project_id, location, token))

    has_failures = False
    for comp, stat, det in all_checks:
        if not silent:
            print_row(comp, stat, det)
        if stat in ("ERROR", "FAIL"):
            has_failures = True
```
  - `scripts/verify.py:345–353`:
```python
        has_creating = any(
            c["status"] in ("CREATING", "INITIALIZING", "STATE_CREATING", "UPDATING")
            for r in json_results
            for c in r["checks"]
        )
        # If everything succeeded (and nothing is still creating when waiting) or no waiting requested, break
        elapsed = time.time() - start_time
        if (overall_success and not has_creating) or elapsed >= max_wait_seconds:
            break
```
- **Problem Description:**
  1. **`expected_seats` Is Unused & Non-Active States Pass Verification (`verify.py:198–215, 229–242, 331`)**: `verify_project()` accepts `expected_seats=None` (`line 229`, passed as `expected_seats=proj.get("seat_count")` from `main()` at line `331`), but never passes `expected_seats` to `check_license_configs()` or references it anywhere in `verify_project()`. Moreover, missing collections (`92`), missing connectors (`136`), missing search engines (`150`), missing assistants (`166, 174`), disabled auto-registration (`193`), and missing license configs (`207`) all return `"WARN"` or `"SKIPPED"`, while `verify_project()` (`241`) only sets `has_failures = True` when `stat in ("ERROR", "FAIL")`.
  2. **`INITIALIZING` Overwritten to `"WARN"` Defeats `--wait` Polling (`verify.py:130–131, 345–353`)**: In `check_data_connectors()`, `elif blocking_reasons or state in ("PAUSED", "INITIALIZING"): status = "WARN"` overwrites `"INITIALIZING"` to `"WARN"`. Consequently, when `main()` checks `c["status"] in ("CREATING", "INITIALIZING", "STATE_CREATING", "UPDATING")` at line `346`, `c["status"]` is `"WARN"`, `has_creating` evaluates to `False`, and `make verify` (`--wait 15m`) exits `0` immediately on the first iteration without waiting for `"INITIALIZING"` connectors.
  3. **Stale OAuth Token in `while True:` Loop (`verify.py:305, 315–365`)**: `token = get_access_token()` is fetched once at line `305` outside the `while True:` polling loop (`line 315`), so wait durations exceeding token lifetime fail with HTTP 401.
  4. **Missing HTTP Socket Timeout (`verify.py:72`, `allocate_licenses.py:51`, `status.py:748, 803`)**: `urllib.request.urlopen(req)` is called without `timeout=...`, risking indefinite hangs on network stalls.
- **Concrete Actionable Improvement:**
  1. Pass `expected_seats` into `check_license_configs(project_id, location, token, expected_seats=None)` and return `"FAIL"` if active seats `< expected_seats` or `state not in ("ACTIVE", "STATE_ACTIVE")`.
  2. Preserve `status = "INITIALIZING"` in `check_data_connectors()` (`verify.py:130–131`) when `not blocking_reasons and state == "INITIALIZING"` so `has_creating` (`line 346`) polls until connectors finish initializing.
  3. Refresh `token = get_access_token()` inside `while True:` and pass `timeout=30` to `urllib.request.urlopen()` across `verify.py:72`, `allocate_licenses.py:51`, and `status.py:748, 803`.

---

#### `CODE-09` [High] — Unisolated Subprocess Call in `scripts/test_red.py` Can Create Live GitHub Issues on `org-owner/gemini-prism`
- **Category:** Code / Test Safety (`scripts/test_red.py` & `scripts/create_github_issues.sh`)
- **Severity:** `High`
- **Exact File(s) & Line(s):**
  - `./scripts/test_red.py` (lines `2336–2378`)
  - `./scripts/create_github_issues.sh` (lines `7`, `40–95`)
- **Evidence Quote / Snippet:**
  - `scripts/test_red.py:2346–2367`:
```python
        # Test targeted argument "05"
        proc_05 = subprocess.run(
            ["bash", script_path, "05"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True
        )
        self.assertEqual(proc_05.returncode, 0)
        self.assertIn("05_interactive_connector_onboarding.md", proc_05.stdout)
        self.assertIn("feat(onboarding)", proc_05.stdout)
        self.assertNotIn("01_confluence_connector.md", proc_05.stdout)

        # Test targeted argument "5" (unpadded numeric)
        proc_5 = subprocess.run(
            ["bash", script_path, "5"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True
        )
        self.assertEqual(proc_5.returncode, 0)
        self.assertIn("05_interactive_connector_onboarding.md", proc_5.stdout)
        self.assertNotIn("01_confluence_connector.md", proc_5.stdout)
```
  - `scripts/create_github_issues.sh:7`:
```bash
REPO="org-owner/gemini-prism"
```
  - `scripts/create_github_issues.sh:80–95`:
```bash
# 1. Check if gh CLI is authenticated
if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
  create_via_gh
  exit 0
fi

# 2. Check if GITHUB_TOKEN or GH_TOKEN is in environment
if [ -n "${GITHUB_TOKEN:-}" ]; then
  create_via_curl "${GITHUB_TOKEN}"
  exit 0
fi

if [ -n "${GH_TOKEN:-}" ]; then
  create_via_curl "${GH_TOKEN}"
  exit 0
fi
```
- **Problem Description:**
  `TestBranchAndIssueContracts.test_create_github_issues_script_registration_and_args` (`scripts/test_red.py:2336–2378`) runs `bash scripts/create_github_issues.sh 05` and `bash scripts/create_github_issues.sh 5` without passing a sanitized `env` dict to `subprocess.run()`. On any developer workstation where `gh auth status` succeeds or any CI runner where `GITHUB_TOKEN` or `GH_TOKEN` is exported in the environment, `create_github_issues.sh` executes `create_via_gh` (`lines 40–52`) or `create_via_curl` (`lines 54–78`) — **creating two real duplicate GitHub issues on `org-owner/gemini-prism` during a unit test run** — and then fails `self.assertIn("05_interactive_connector_onboarding.md", proc_05.stdout)` at line `2354` because `create_via_gh` and `create_via_curl` only print the issue title (`Creating Issue [Priority P5]: ...`), not the filename!
- **Concrete Actionable Improvement:**
  1. Pass a hermetic `env={**os.environ, "GITHUB_TOKEN": "", "GH_TOKEN": "", "GH_CONFIG_DIR": "/tmp/nonexistent", "PATH": "/usr/bin:/bin"}` to `subprocess.run()` in `scripts/test_red.py:2347–2375`, and add a `--dry-run` flag to `scripts/create_github_issues.sh`.
  2. In `scripts/create_github_issues.sh:71–75`, pass the JSON payload via stdin (`-d @- <<< "${payload}"`) and use `Authorization: Bearer ${token}`.

---

#### `CODE-10` [Medium] — `scripts/status.py` Silently Ignores Corrupted `terraform.tfstate`, Skips Workspace Connectors in Stage 3 State Verification, Ignores `--deep`, and Checks ADC by File Existence Only
- **Category:** Code / Phase Detection Engine (`scripts/status.py`)
- **Severity:** `Medium`
- **Exact File(s) & Line(s):**
  - `./scripts/status.py` (lines `113–121`, `131–165`, `183`, `271`, `297`, `575–628`, `932`, `967`)
- **Evidence Quote / Snippet:**
  - `scripts/status.py:113–121`:
```python
def parse_state(state_path):
    """Parse local terraform.tfstate if it exists."""
    if not os.path.exists(state_path):
        return None
    try:
        with open(state_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        return {"_error": str(e)}
```
  - `scripts/status.py:162–163`:
```python
    if adc_path and os.path.exists(adc_path):
        return True, "application_default_credentials"
```
  - `scripts/status.py:271`:
```python
    if state and "_error" not in state:
```
  - `scripts/status.py:297`:
```python
    state_outputs = state.get("outputs", {}) if state and "_error" not in state else {}
```
  - `scripts/status.py:575–585`:
```python
    # Collect provisioned connector keys from state if any optional connector is enabled
    connector_keys = set()
    if (enable_jira_connector or enable_confluence_connector or enable_slack_connector or enable_people_directory_connector) and state and "_error" not in state:
        for res in state.get("resources", []):
            if res.get("type") == "google_discovery_engine_data_connector":
                for inst in res.get("instances", []):
                    if inst.get("index_key"):
                        connector_keys.add(inst.get("index_key"))
        data_connectors_output = state_outputs.get("data_connector_names", {}).get("value", {})
        if isinstance(data_connectors_output, dict):
            connector_keys.update(data_connectors_output.keys())
```
- **Problem Description:**
  1. **Corrupted `terraform.tfstate` Silently Ignored (`status.py:113–121, 271, 297`)**: If `terraform.tfstate` exists on disk but contains malformed or truncated JSON, `parse_state()` returns `{"_error": str(e)}`. `determine_status()` checks `if state and "_error" not in state:`, bypassing the State Mismatch Guard (`271`) and treating `state_outputs` as `{}` (`297`), which falsely reports `phase: 1` (`next_action: "make plan-foundation && make apply-foundation"`, `exit_code: 0`) instead of halting on corrupted state.
  2. **Workspace Connectors Omitted from Stage 3 State Verification (`status.py:575–628`)**: `determine_status()` verifies `jira_connectors_present`, `confluence_connectors_present`, `slack_connectors_present`, and `people_directory_connectors_present` against `connector_keys` (populated from `google_discovery_engine_data_connector` instances and `state_outputs.get("data_connector_names", {})`), but never verifies that the Workspace connectors (`<env>-google_mail`, `<env>-google_calendar`, `<env>-google_drive`, `<env>-google_chat`) exist in `connector_keys` when `enable_connectors = true`.
  3. **Unimplemented `--deep` CLI Flag (`status.py:183, 932, 967`)**: `--deep` (`"Perform deep drift check via terraform plan."` at line `932`) is passed to `determine_status(..., deep=args.deep)` at line `967`, but `deep` is never read inside `determine_status()`.
  4. **Existence-Only ADC Fallback (`status.py:162–163`)**: When `gcloud auth print-access-token` fails, `check_identity()` returns `(True, "application_default_credentials")` based solely on `os.path.exists(adc_path)` without verifying whether the ADC file is valid JSON or has an active token (`gcloud auth application-default print-access-token`).
- **Concrete Actionable Improvement:**
  1. In `determine_status()`, return an immediate Phase 0 error (`exit_code: 1`, `handoff_template: "state_mismatch"`) when `state and "_error" in state`.
  2. Include `enable_connectors` in the `connector_keys` collection guard (`status.py:577`) and check `workspace_connectors_present` for all configured `workspace_connectors`.
  3. Implement `deep=True` in `determine_status()` via `terraform plan -detailed-exitcode -input=false`, and validate ADC tokens in `check_identity()`.

---

#### `CODE-11` [Medium] — `.env.jira` Written by `scripts/configure.py` Is Never Sourced by `Makefile`, Uses Unescaped Single Quotes, and Lacks `.env.confluence` / `.env.slack` Parity
- **Category:** Code / Security & Credential Persistence (`scripts/configure.py`, `Makefile`)
- **Severity:** `Medium`
- **Exact File(s) & Line(s):**
  - `./scripts/configure.py` (lines `412–416`, `566–576`, `890–894`)
  - `./Makefile` (lines `66–73`)
- **Evidence Quote / Snippet:**
  - `scripts/configure.py:566–576`:
```python
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
```
  - `Makefile:66–69`:
```makefile
plan-connectors:
	@mkdir -p .plans
	terraform plan -input=false -out=.plans/connectors.tfplan
	python3 scripts/plan_guard.py .plans/connectors.tfplan
```
- **Problem Description:**
  1. **Disconnected Credential Persistence**: `update_tfvars()` writes `jira_auth` to `.env.jira` (`configure.py:566–576`), excludes `"jira_auth"` from `terraform.tfvars` (`line 529`), and checks `os.path.exists(os.path.join(workdir, ".env.jira"))` in both `audit_inputs()` (`line 414`) and `enable_connectors()` (`line 892`). However, `Makefile:66–73` (`plan-connectors`, `apply-connectors`) never sources `.env.jira` before invoking `terraform plan`, so `make check-inputs` and `make enable-connectors` pass while `make plan-connectors` runs with an empty `var.jira_auth = {}`!
  2. **Unescaped Single Quotes & Non-Atomic `0o600` Permissions**: `f"export TF_VAR_jira_auth='{jira_auth_str}'\n"` does not escape single quotes (`shlex.quote()`), and `open(env_jira_path, "w")` creates the file with default umask permissions before `os.chmod(env_jira_path, 0o600)` executes.
  3. **No `.env.confluence` or `.env.slack` Equivalent**: `configure.py` has no equivalent helper for `confluence_auth` (`TF_VAR_confluence_auth`) or `slack_auth` (`TF_VAR_slack_auth`).
- **Concrete Actionable Improvement:**
  Use `shlex.quote()` and `os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)` when writing `.env.jira`, `.env.confluence`, and `.env.slack` in `scripts/configure.py`, and source any present `.env.*` files automatically in `Makefile`'s `plan-foundation` and `plan-connectors` recipes.

---

#### `CODE-12` [Medium] — Missing Variable `validation {}` Blocks, Project Name Truncation (`substr`), `non-prod` Fallback & Default `0777` Mode on `local_file.license_allocations`, and Unguarded `bootstrap.sh`
- **Category:** Code / Terraform IaC & Bootstrap (`main.tf`, `variables.tf`, `versions.tf`, `bootstrap.sh`)
- **Severity:** `Medium`
- **Exact File(s) & Line(s):**
  - `./main.tf` (lines `14`, `505–513`, `740–760`)
  - `./variables.tf` (lines `1–16`, `28–42`, `62–65`)
  - `./versions.tf` (lines `1–17`)
  - `./bootstrap.sh` (lines `41–58`)
- **Evidence Quote / Snippet:**
  - `main.tf:505–513`:
```hcl
resource "google_project" "projects" {
  for_each        = local.environments
  name            = substr("${var.customer_name} ${each.value.display_name}", 0, 30)
  project_id      = each.value.project_id
  folder_id       = local.effective_folder_id
  org_id          = local.effective_org_id
  billing_account = var.billing_account
  deletion_policy = contains(["prod", "production"], lower(each.key)) ? "PREVENT" : "DELETE"
}
```
  - `main.tf:740–744`:
```hcl
resource "local_file" "license_allocations" {
  filename = "${path.module}/config/license_allocations.json"
  content = jsonencode({
    licensing_project = try(coalesce(var.billing_project, try(values(google_project.projects)[0].project_id, "")), "")
    billing_account   = var.billing_account
```
  - `bootstrap.sh:41–42`:
```bash
terraform init
terraform apply -var="sa_email=${SA_EMAIL}" -var="billing_project=${BOOTSTRAP_PROJECT}"
```
- **Problem Description:**
  1. **Missing Variable Validation Blocks (`variables.tf:1–16, 28–42, 62–65`)**: `customer_id`, `workspace_customer_id`, `billing_account`, and `location` have no `validation {}` blocks. Invalid GCP project IDs (`${var.project_id_prefix}${var.customer_id}-${env}` > 30 chars or uppercase at `main.tf:14`), malformed billing account IDs, or truncated project display names (`substr("${var.customer_name} ${each.value.display_name}", 0, 30)` at `main.tf:507` ending in a trailing space) fail only during live GCP API calls instead of `terraform validate`/`plan`.
  2. **Fallback `licensing_project` Picks `non-prod` & Default `0777` File Mode (`main.tf:740–744`)**: When `var.billing_project` is `null`, `values(google_project.projects)[0].project_id` selects the first key in lexicographical order (`"non-prod"`, which has `deletion_policy = "DELETE"` at line `512`). Additionally, `resource "local_file" "license_allocations"` omits `file_permission = "0600"` (defaulting to `"0777"` in `hashicorp/local`).
  3. **Legacy `bootstrap.sh` Bypasses `Makefile` and `plan_guard.py` (`bootstrap.sh:41–58`)**: `bootstrap.sh:42` runs unguarded `terraform apply` without `-var="enable_connectors=false"` or `scripts/plan_guard.py`.
- **Concrete Actionable Improvement:**
  1. Add regex and length `validation {}` blocks to `customer_id`, `workspace_customer_id` (`^C[0-9a-zA-Z]+$`), `billing_account` (`^[0-9A-F]{6}-[0-9A-F]{6}-[0-9A-F]{6}$`), and `location` (`contains(["global", "us", "eu"], var.location)`) in `variables.tf`.
  2. In `main.tf:507`, wrap `substr(...)` in `trimspace(substr(..., 0, 30))`; in `main.tf:740–744`, set `file_permission = "0600"` and prefer `"prod"` (`try(coalesce(var.billing_project, google_project.projects["prod"].project_id, values(google_project.projects)[0].project_id), "")`).
  3. Update `bootstrap.sh:41–58` to delegate to `make plan-foundation && make apply-foundation`.

---

#### `CODE-13` [Low] — Non-Hermetic State File Dependence and Hardcoded Branch Allowlist in `scripts/test_red.py`
- **Category:** Code / Test Suite (`scripts/test_red.py`, `.github/workflows/terraform.yml`)
- **Severity:** `Low`
- **Exact File(s) & Line(s):**
  - `./scripts/test_red.py` (lines `406–429`, `2299–2311`)
  - `./.github/workflows/terraform.yml` (lines `28–41`)
- **Evidence Quote / Snippet:**
  - `scripts/test_red.py:406–410`:
```python
    def test_status_legacy_workspace_state_triggers_mismatch(self):
        """Workspace legacy state file with legacy-* projects must trigger state mismatch against fresh tfvars."""
        legacy_state_path = os.path.join(REPO_ROOT, "terraform.tfstate")
        if not os.path.exists(legacy_state_path):
            return  # skip if running in environment where state was pruned
```
  - `scripts/test_red.py:2299–2311`:
```python
    def test_git_branch_contract(self):
        """Active git branch must be a recognized feature branch, main, or CI detached HEAD."""
        proc = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn(
            proc.stdout.strip(),
            ["Slack-Data-Connector", "feat/interactive-connector-onboarding", "main", ""]
        )
```
- **Problem Description:**
  1. **Non-Hermetic Workspace State Test (`test_red.py:406–429`)**: `test_status_legacy_workspace_state_triggers_mismatch` reads `os.path.join(REPO_ROOT, "terraform.tfstate")` if present on disk and asserts that it triggers `state_mismatch` against `customer_id = "testcust"`. If an operator has a valid `terraform.tfstate` in `REPO_ROOT` for `testcust` or an empty state file, the unit test fails non-hermetically.
  2. **Hardcoded Branch Name Allowlist (`test_red.py:2299–2311`)**: `test_git_branch_contract` fails on any new feature, bugfix, or release branch not listed in `["Slack-Data-Connector", "feat/interactive-connector-onboarding", "main", ""]`.
  3. **CI Workflow Missing Marketing Pack Check (`.github/workflows/terraform.yml:28–41`)**: `Makefile:97` runs `python3 scripts/package_marketing_assets.py --check`, but `.github/workflows/terraform.yml` omits that step.
- **Concrete Actionable Improvement:**
  Replace `os.path.join(REPO_ROOT, "terraform.tfstate")` in `test_status_legacy_workspace_state_triggers_mismatch` with a synthetic fixture in `self.temp_dir`; update `test_git_branch_contract` to match standard branch naming conventions (`r"^(main|master|feat/.*|fix/.*|chore/.*|release/.*|[A-Za-z0-9._-]+)$"`); and add `python3 scripts/package_marketing_assets.py --check` to `.github/workflows/terraform.yml`.

---

#### `CODE-14` [Medium] — `scripts/deploy_marketing_assets.py` Skips Prism-Provisioned Google Drive DataStore (`drive-collection`), Swallows Publish/Enable API Errors, Mutates Disk / Calls Live Auth in `--dry-run`, and Defaults to `"gemini-3.8-flash"`
- **Category:** Code / Marketing Pack API Deployer (`scripts/deploy_marketing_assets.py`, `Makefile`, `scripts/test_red.py`)
- **Severity:** `Medium`
- **Exact File(s) & Line(s):**
  - `./scripts/deploy_marketing_assets.py` (lines `39`, `133–169`, `213–271`, `693–726`, `865`)
  - `./main.tf` (lines `30–34`)
  - `./Makefile` (lines `30`, `93–94`)
  - `./scripts/test_red.py` (lines `2559–2648`)
- **Evidence Quote / Snippet:**
  - `scripts/deploy_marketing_assets.py:133–152`:
```python
    # Map relevant federated data stores attached to the engine
    ds_ids = selected_engine.get("dataStoreIds", [])
    preferred_prefixes = ("google-drive", "confluence", "slack")
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
```
  - `scripts/deploy_marketing_assets.py:220–253`:
```python
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
```
  - `scripts/deploy_marketing_assets.py:704–726`:
```python
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
```
- **Problem Description:**
  1. **DataStore Prefix Mismatch Silently Drops Prism-Provisioned Google Drive DataStore (`deploy_marketing_assets.py:134–152` vs `main.tf:30–34`)**: `discover_environment()` filters `selected_engine.get("dataStoreIds", [])` using `preferred_prefixes = ("google-drive", "confluence", "slack")` (`line 135`). However, `main.tf:30–34` provisions Google Drive with `collection = "drive-collection"`, which produces a Discovery Engine entity data store ID prefixed with `"drive-collection"` (e.g., `drive-collection_google_drive`), NOT `"google-drive"`! As a result, `ds_id.startswith(pref)` at line `138` evaluates to `False` and silently drops the Google Drive DataStore from `matched_ds_specs` (notice that `scripts/test_red.py:2630` mocked `"google-drive-actions-collection_google_drive"` instead of Prism's `"drive-collection_google_drive"`). Additionally, line `148` hardcodes `/collections/default_collection/dataStores/{ds_id}` instead of resolving the connector's collection path, and `connectors_by_source` (`lines 157–168`) keys connectors by raw `dc.get("dataSource")` (missing `"confluence_server"` when matched against blueprint `"confluence"` at line `413`).
  2. **Swallowed Publish, Review, Enable & Sharing Errors Return Exit Code `0` (`deploy_marketing_assets.py:213–271, 865`)**: `_publish_and_enable_agent()` catches `RuntimeError` on `:publish` (`229`), `:requestAgentReview` (`242`), `:enableAgent` (`252`), and `PATCH ?updateMask=sharingConfig` (`267`), storing the error in `publish_note`. Neither `deploy_shared_skill()`, `deploy_workflow_agent()`, nor `main()` checks whether the resulting agent reached `state == "ENABLED"` and `sharingConfig.scope == sharing_scope`, returning exit code `0` even when publishing or enabling failed.
  3. **Disk Mutation & Required Live GCP Auth in `--dry-run` (`deploy_marketing_assets.py:705–726`)**: `deploy_pack()` executes `packager.build_packages()` (`line 705`, which creates `dist/marketing/brand-kit-governance.zip` and `dist/marketing/marketing_catalog_manifest.json` on disk) and calls `get_access_token()` (`line 706`) and `discover_environment()` (`line 707`) before checking `if dry_run:` at line `718`.
  4. **Unrecognized Default Model ID & Limited Unit Test Coverage (`deploy_marketing_assets.py:39, 712`; `scripts/test_red.py:2559–2648`)**: `DEFAULT_MODEL = "gemini-3.8-flash"` (`line 39`) and fallback `("gemini-3.8-flash", "gemini-4-argon", ...)` (`line 712`) default to internal/unreleased model identifiers if `default_search_widget_config` lookup (`lines 173–187`) fails or returns no `modelConfigs`. Furthermore, `scripts/test_red.py:2559–2648` only has 2 unit tests for `deploy_marketing_assets.py`, leaving `deploy_shared_skill()`, `deploy_workflow_agent()`, `_publish_and_enable_agent()`, and `discover_environment()` (`drive-collection_google_drive`) untested.
- **Concrete Actionable Improvement:**
  1. In `discover_environment()` (`deploy_marketing_assets.py:135–152`), include `"drive-collection"` and `"google_drive"` in `preferred_prefixes` (`("drive-collection", "google-drive", "google_drive", "confluence", "slack")`) and normalize `"confluence_server"` -> `"confluence"` in `connectors_by_source` (`lines 164–167`).
  2. In `_publish_and_enable_agent()` (`lines 213–271`) and `deploy_pack()`, raise or return a non-zero exit code if `sharing_scope != "PRIVATE"` and the final agent state is not `"ENABLED"` (unless an explicit `--allow-partial-publish` flag is set).
  3. In `deploy_pack()` (`line 705`), call `packager.validate_catalog(catalog_dir)` instead of `packager.build_packages()` when `dry_run=True`, and add unit tests in `scripts/test_red.py` covering `discover_environment()` with `"drive-collection_google_drive"`, `deploy_shared_skill()`, `deploy_workflow_agent()`, and `_publish_and_enable_agent()`.

---

## Part 2: Existing Issues & Actionable Improvements — Deployment Process (`DEPLOY-*`)

### Summary Table (`DEPLOY-01` – `DEPLOY-14`)

| ID | Category | Severity | Stage(s) | Exact File(s) & Line(s) | Summary of Issue & Operational Failure Mode | Roadmap Ref |
| :--- | :---: | :---: | :---: | :--- | :--- | :---: |
| **`DEPLOY-01`** | `Deployment Process` | **Critical** | Stages 0–3, CI | `main.tf:330–422, 477, 677, 707, 718`; `outputs.tf:166–209`; `variables.tf:79–90, 268–302`; `terraform.tfvars.example:1–94` | `main.tf` and `outputs.tf` reference undeclared `var.enable_slack_connector`, `var.slack_auth_type`, `var.slack_auth`, and `var.slack_config`; `terraform validate` and all `make plan-*` targets abort with 16 errors. | `RM-01` |
| **`DEPLOY-02`** | `Deployment Process` | **Critical** | Stages 1–2 | `Makefile:1, 18–21, 45–64`; `scripts/status.py:396, 439, 555, 566, 930, 954–956` | `Makefile` omits the `slack-checklist` target emitted by `status.py` (`make: *** No rule to make target 'slack-checklist'. Stop.`) and omits `-var="enable_slack_connector=false"` from `plan-foundation`. | `RM-01` |
| **`DEPLOY-03`** | `Deployment Process` | **High** | Stages 0, 2 | `scripts/configure.py:38–91, 270–328, 330–355, 470–475, 488–497, 844–945, 1032–1041` | `configure.py` exits with code `1` on `"confluence"` or `"slack"` in `--apply-json`/`--connectors`, and omits `"slack"` from `CONNECTOR_OPTIONS`, Stage 0 safety guard (`update_tfvars`), `determine_stage`, and Stage 2 `enable_connectors`. | `RM-01` |
| **`DEPLOY-04`** | `Deployment Process` | **High** | Stages 2–3 | `scripts/configure.py:412–433, 566–576, 890–911`; `scripts/status.py:31–38, 464–570`; `Makefile:66–73`; `main.tf:463–466` | `.env.jira` written by `configure.py` is never sourced by `Makefile` during `plan-connectors`/`apply-connectors`; neither `configure.py` nor `status.py` checks `TF_VAR_confluence_auth` or `workspace_admin_email` (for People Directory). | `RM-03`, `RM-08` |
| **`DEPLOY-05`** | `Deployment Process` | **High** | Stage 4 | `Makefile:75–79`; `scripts/status.py:657–684`; `scripts/allocate_licenses.py:524–569`; `main.tf:588–601`; `outputs.tf:39–42` | `make licenses` runs `--distribute` and returns at line `528` without updating `license_config_names` in `terraform.tfvars` or running `--configure-auto-register` (looping `make status` in Stage 4); conversely, `status.py` advances to Stage 5 without checking `google_discovery_engine_user_store.default` attributes in `terraform.tfstate`. | `RM-05` |
| **`DEPLOY-06`** | `Deployment Process` | **High** | Stage 4 | `scripts/allocate_licenses.py:168–184, 361–364, 432–481, 500–506` | `load_config` requires non-empty `subscription_id` before `--discover` can run, and `run_preflight_assertions` compares gross `total_requested_seats` against remaining `availableLicenseCount`, blocking idempotent re-runs, `--configure-auto-register`, and seat scaling. | `RM-05` |
| **`DEPLOY-07`** | `Deployment Process` | **High** | Stage 5 | `scripts/verify.py:124–133, 198–215, 229–248, 345–353, 387`; `Makefile:84–85` | `check_data_connectors` overwrites `state == "INITIALIZING"` to `status = "WARN"`, causing `has_creating` in `main()` to evaluate `False` and `make verify WAIT=15m` to exit `0` on the first iteration without waiting; `expected_seats` in `verify_project` is unused. | `RM-06` |
| **`DEPLOY-08`** | `Deployment Process` | **High** | Stage 3 | `main.tf:676–703, 717–737`; `AGENTS.md:123`; `RUNBOOK.md:249` | Provisioning `google_discovery_engine_search_engine.engines` with `SEARCH_ADD_ON_LLM` auto-creates `default_assistant` in GCP, causing `google_discovery_engine_assistant.default` in Stage 3 to fail with HTTP `400`/`409 ALREADY_EXISTS`. | `RM-05` |
| **`DEPLOY-09`** | `Deployment Process` | **High** | All Stages | `versions.tf:1–17`; `Makefile:45–52, 66–73`; `scripts/plan_guard.py:48–134`; `scripts/status.py:113–121, 268–298` | Local-only `terraform.tfstate` lacks remote GCS backend locking, `make apply-*` applies `.plans/*.tfplan` without verifying `terraform.tfvars` freshness, and `status.py` silently ignores `_error` on corrupted state files. | `RM-04`, `RM-09` |
| **`DEPLOY-10`** | `Deployment Process` | **Medium** | Stages 1–5 | `scripts/status.py:183–186, 932, 961–968` | `--deep` CLI flag (`"Perform deep drift check via terraform plan."`) in `scripts/status.py` is accepted and passed as `deep=args.deep` to `determine_status()`, where it is never read or used (dead no-op). | `RM-08` |
| **`DEPLOY-11`** | `Deployment Process` | **Medium** | Stages 1, 2, 4 | `main.tf:42–53, 740–744`; `scripts/status.py:733–754`; `scripts/allocate_licenses.py:107–116, 138–141` | `main.tf` `local.base_services` omits `serviceusage.googleapis.com` and `cloudresourcemanager.googleapis.com` (causing `print_dwd_checklist` to silently swallow `403` errors and omit the 21-digit `client_id`), and `get_project_metadata` omits `x-goog-user-project`. | `RM-06`, `RM-08` |
| **`DEPLOY-12`** | `Deployment Process` | **Medium** | Stage 4 / Day-2 | `scripts/allocate_licenses.py:503–506, 590–599`; `RUNBOOK.md:304`; `AGENTS.md:125` | `allocate_licenses.py --distribute` skips seat reductions (`current_seats >= int(seats)`) and `--retract` hardcodes `"fullRetract": True`, providing no CLI mechanism for partial retraction (`fullRetract: false`) required by `RUNBOOK.md:304` and `AGENTS.md:125`. | `RM-05`, `RM-11` |
| **`DEPLOY-13`** | `Deployment Process` | **Medium** | Stages 0–1 | `bootstrap.sh:41–58` | `bootstrap.sh` executes unguarded `terraform apply` commands directly without `.tfplan` or `plan_guard.py`, omits `-var="enable_*=false"` stage overrides, and prints legacy manual commands (`terraform output dwd_checklist`, `terraform apply -var="enable_connectors=true"`). | `RM-02`, `RM-09` |
| **`DEPLOY-14`** | `Deployment Process` | **Low** | CI/CD | `.github/workflows/terraform.yml:22–40`; `Makefile:93–100` | `.github/workflows/terraform.yml` duplicates commands instead of running `make test`, omits `package_marketing_assets.py --check`, omits `-lockfile=readonly` on `terraform init`, and runs `test_red.py` without clearing ambient `GH_TOKEN`/`GITHUB_TOKEN`. | `RM-04` |

---

### Detailed Deployment Process Findings & Actionable Fixes

#### `DEPLOY-01` [Critical] — Stage 0–3 Deployment Blockade from Undeclared Slack Variables
- **ID:** `DEPLOY-01`
- **Category:** `Deployment Process`
- **Severity:** `Critical`
- **Stage(s) Impacted:** Stage 0 (`preflight_inputs`), Stage 1 (`foundation_apply`), Stage 3 (`connectors_and_engines_apply`), CI/CD (`make test`)
- **Exact File Path(s) & Line Numbers:**
  - `./main.tf` (Lines `330–422`, `477`, `677`, `707`, `718`)
  - `./outputs.tf` (Lines `166–209` — `output "slack_checklist"`)
  - `./variables.tf` (Lines `79–90` — `variable "planned_connectors"`, and EOF at Line `302`)
  - `./terraform.tfvars.example` (Lines `1–94`)
  - `./Makefile` (Lines `45–48`, `66–69`, `96–100`)
- **Evidence Quote/Snippet:**
  - `./main.tf` (Lines `330–355`):
```hcl
  # Map user-friendly Slack auth type to canonical Discovery Engine auth_type
  effective_slack_auth_type = {
    "OAUTH"      = "OAUTH"
    "OAUTH2"     = "OAUTH"
    "BOT_TOKEN"  = "API_TOKEN"
    "USER_TOKEN" = "API_TOKEN"
    "API_TOKEN"  = "API_TOKEN"
  }[var.slack_auth_type]

  effective_slack_team_id = try(coalesce(
    trimspace(nonsensitive(try(var.slack_auth.team_id, ""))),
    trimspace(try(var.slack_config.team_id, ""))
  ), "")

  effective_slack_token = try(coalesce(
    trimspace(try(var.slack_auth.bot_token, "")),
    trimspace(try(var.slack_auth.user_token, "")),
    trimspace(try(var.slack_auth.api_token, ""))
  ), "")

  # Default data source version: Discovery Engine production pins "slack" to v3 (PUBLIC_GA Federated + Actions)
  default_slack_version     = 3
  effective_slack_version   = coalesce(var.slack_config.data_source_version, local.default_slack_version)
  effective_slack_modes     = coalesce(var.slack_config.enable_actions, false) ? distinct(concat(coalesce(var.slack_config.connector_modes, ["FEDERATED"]), ["ACTIONS"])) : coalesce(var.slack_config.connector_modes, ["FEDERATED"])
  is_slack_federated        = contains(local.effective_slack_modes, "FEDERATED") || local.effective_slack_version >= 3
  effective_slack_sync_mode = local.is_slack_federated ? null : (upper(coalesce(var.slack_config.sync_mode, "PERIODIC")) == "INCREMENTAL" ? "PERIODIC" : coalesce(var.slack_config.sync_mode, "PERIODIC"))
```
  - `./main.tf` (Lines `376–386`):
```hcl
  # Slack Enterprise connector per environment (when enabled)
  slack_environment_connectors = var.enable_slack_connector ? {
    for env_key, env_val in local.environments :
    "${env_key}-slack" => {
      env_key             = env_key
      connector           = "slack"
      data_source         = coalesce(var.slack_config.data_source, "slack")
      data_source_version = local.is_slack_federated ? null : local.effective_slack_version
      display_name        = "Slack Enterprise"
      collection_id       = try(coalesce(trimspace(var.slack_config.collection_id)), "") != "" ? trimspace(var.slack_config.collection_id) : "slack-collection"
      project_id          = google_project.projects[env_key].project_id
```
  - `./variables.tf` (Lines `79–90`):
```hcl
variable "planned_connectors" {
  type        = list(string)
  description = "List of enterprise connectors planned for deployment (workspace, jira, confluence, people_directory)"
  default     = ["workspace"]

  validation {
    condition = alltrue([
      for c in var.planned_connectors : contains(["workspace", "jira", "confluence", "people_directory"], c)
    ])
    error_message = "Each element of planned_connectors must be one of: 'workspace', 'jira', 'confluence', 'people_directory'."
  }
}
```
- **Problem Description & Operational Failure Mechanism:**
  When the Slack Enterprise connector locals (`local.effective_slack_auth_type`, `local.effective_slack_team_id`, `local.effective_slack_token`, `local.default_slack_version`, `local.effective_slack_version`, `local.effective_slack_modes`, `local.is_slack_federated`, `local.effective_slack_sync_mode`, `local.slack_entity_params`, `local.slack_environment_connectors` in `main.tf:330–422`), `local.environment_connectors` (`main.tf:477`), `for_each` conditions on `google_discovery_engine_search_engine.engines` (`main.tf:677`), `google_discovery_engine_search_engine_iam_member.users` (`main.tf:707`), and `google_discovery_engine_assistant.default` (`main.tf:718`), and `output "slack_checklist"` (`outputs.tf:166–209`) were merged, the corresponding variable declarations (`enable_slack_connector`, `slack_auth_type`, `slack_auth`, `slack_config`) were not merged into `variables.tf` (which ends at line `302`) or `terraform.tfvars.example` (which ends at line `94`), and `variables.tf:86` still rejects `"slack"` in `planned_connectors`. Because Terraform validates the full root module graph before executing any plan, running `terraform validate`, `make test` (`Makefile:96–100`), `make plan-foundation` (`Makefile:45–48`), or `make plan-connectors` (`Makefile:66–69`) fails immediately with 16 `Error: Reference to undeclared input variable` errors (`var.slack_auth_type` at `main.tf:337`; `var.slack_auth` at `main.tf:340, 345, 346, 347`; `var.slack_config` at `main.tf:341, 352, 353 [x3], 358, 360, 363, 365, 368, 371`), and `TestTerraformDefaultsContract.test_slack_v3_federated_defaults_contract` fails at `scripts/test_red.py:1723`.
- **Concrete Actionable Improvement:**
  1. Declare `enable_slack_connector` (`type = bool`, `default = false`), `slack_auth_type` (`type = string`, `default = "OAUTH"`, validating `contains(["OAUTH", "OAUTH2", "BOT_TOKEN", "USER_TOKEN", "API_TOKEN"], var.slack_auth_type)`), `slack_auth` (`sensitive = true`, `default = {}`, `type = object({ bot_token = optional(string, ""), user_token = optional(string, ""), api_token = optional(string, ""), client_id = optional(string, ""), client_secret = optional(string, ""), team_id = optional(string, ""), refresh_token = optional(string, "") })`), and `slack_config` (`default = {}`, `type = object({ instance_uri = optional(string, ""), team_id = optional(string, ""), collection_id = optional(string, "slack-collection"), data_source = optional(string, "slack"), data_source_version = optional(number, 3), connector_modes = optional(list(string), ["FEDERATED"]), sync_mode = optional(string, "PERIODIC"), refresh_interval = optional(string, "86400s"), incremental_refresh_interval = optional(string, "10800s"), entities = optional(list(string), ["conversation", "message", "file"]), static_ip_enabled = optional(bool, false), enable_actions = optional(bool, false), enabled_actions = optional(list(string), []), channels_include = optional(list(string), []), channels_exclude = optional(list(string), []), include_private_channels = optional(bool, false), include_dms = optional(bool, false), auto_run_disabled = optional(bool, false), incremental_sync_disabled = optional(bool, false), extra_params = optional(map(string), {}) })` with `FEDERATED` mode validation) in `variables.tf`.
  2. Update `variables.tf:81–89` so `planned_connectors` includes `"slack"` (`contains(["workspace", "jira", "confluence", "slack", "people_directory"], c)`), and add the default `enable_slack_connector = false`, `slack_auth_type = "OAUTH"`, and `slack_config = { ... }` block to `terraform.tfvars.example`.
  3. Wrap `var.slack_auth.*` references in `main.tf:344–348` (`local.effective_slack_token`) and `main.tf:410–418` (`action_params` in `local.slack_environment_connectors`) with `nonsensitive(...)` (or avoid using a sensitive value in the ternary condition `trimspace(try(coalesce(var.slack_auth.client_id), "")) != ""`) so Terraform does not raise a sensitive conditional evaluation error once `var.slack_auth` is marked `sensitive = true`.

---

#### `DEPLOY-02` [Critical] — Missing `slack-checklist` Target and Missing `-var="enable_slack_connector=false"` Override in `Makefile`
- **ID:** `DEPLOY-02`
- **Category:** `Deployment Process`
- **Severity:** `Critical`
- **Stage(s) Impacted:** Stage 1 (`foundation_apply`), Stage 2 (`slack_authorization`)
- **Exact File Path(s) & Line Numbers:**
  - `./Makefile` (Lines `1`, `18–21`, `45–64`)
  - `./scripts/status.py` (Lines `396`, `439`, `550–558`, `566`, `930`, `954–956`)
  - `./AGENTS.md` (Line `83`)
  - `./RUNBOOK.md` (Lines `171`, `195`, `214`)
- **Evidence Quote/Snippet:**
  - `./Makefile` (Line `1`):
```makefile
.PHONY: status configure check-inputs enable-connectors plan-foundation apply-foundation dwd-checklist jira-checklist confluence-checklist people-checklist plan-connectors apply-connectors licenses-dryrun licenses licenses-list verify check-marketing package-marketing deploy-marketing test help
```
  - `./Makefile` (Lines `18–21`):
```makefile
	@echo "  dwd-checklist        - Print Google Workspace Domain-Wide Delegation authorization checklist"
	@echo "  jira-checklist       - Print Atlassian Jira connector onboarding checklist"
	@echo "  confluence-checklist - Print Atlassian Confluence connector onboarding checklist"
	@echo "  people-checklist     - Print Google People Directory connector onboarding checklist"
```
  - `./Makefile` (Lines `45–64`):
```makefile
plan-foundation:
	@mkdir -p .plans
	terraform plan -input=false -var="enable_connectors=false" -var="enable_jira_connector=false" -var="enable_confluence_connector=false" -var="enable_people_directory_connector=false" -out=.plans/foundation.tfplan
	python3 scripts/plan_guard.py .plans/foundation.tfplan

apply-foundation:
	python3 scripts/plan_guard.py .plans/foundation.tfplan
	terraform apply -input=false .plans/foundation.tfplan

dwd-checklist:
	@python3 scripts/status.py --dwd-checklist

jira-checklist:
	@python3 scripts/status.py --jira-checklist

confluence-checklist:
	@python3 scripts/status.py --confluence-checklist

people-checklist:
	@python3 scripts/status.py --people-directory-checklist
```
  - `./scripts/status.py` (Lines `550–558`):
```python
            return {
                "phase": 2,
                "phase_name": "slack_authorization",
                "owner": "human",
                "blockers": ["Slack Enterprise workspace URI / team_id not configured or placeholder in terraform.tfvars"],
                "next_action": "make slack-checklist",
                "handoff_template": "slack",
                "exit_code": 2
            }
```
- **Problem Description & Operational Failure Mechanism:**
  1. `scripts/status.py` (lines `396`, `439`, `555`, `566`), `AGENTS.md` (line `83`), `RUNBOOK.md` (lines `171`, `195`, `214`), and `PRACTITIONERS_GUIDE.md` (lines `227`, `310`, `364`, `558`) instruct operators and autonomous agents to run `make slack-checklist`, and `scripts/status.py` implements `--slack-checklist` (lines `854–891`, `930`, `954–956`). However, `Makefile` defines `dwd-checklist`, `jira-checklist`, `confluence-checklist`, and `people-checklist` (`Makefile:54–64`) while omitting `slack-checklist`. Running `make slack-checklist` fails immediately with `make: *** No rule to make target 'slack-checklist'.  Stop.` (exit code `2`).
  2. In `Makefile:47`, `plan-foundation` passes `-var="enable_connectors=false" -var="enable_jira_connector=false" -var="enable_confluence_connector=false" -var="enable_people_directory_connector=false"`, omitting `-var="enable_slack_connector=false"`. If `enable_slack_connector = true` is present in `terraform.tfvars` during Stage 1, `make plan-foundation` will attempt to plan `google_discovery_engine_data_connector.connectors["<env>-slack"]`, `google_discovery_engine_search_engine.engines` (`main.tf:677`), and `google_discovery_engine_assistant.default` (`main.tf:718`) in Stage 1.
- **Concrete Actionable Improvement:**
  1. Add `slack-checklist` to `.PHONY` (`Makefile:1`), `help` (`Makefile:21`), and the checklist target rules (`Makefile:64`) invoking `@python3 scripts/status.py --slack-checklist`.
  2. Append `-var="enable_slack_connector=false"` to the `terraform plan` command in `plan-foundation` (`Makefile:47`).

---

#### `DEPLOY-03` [High] — Stage 0 & Stage 2 Onboarding Failure for Slack and Confluence in `scripts/configure.py`
- **ID:** `DEPLOY-03`
- **Category:** `Deployment Process`
- **Severity:** `High`
- **Stage(s) Impacted:** Stage 0 (`make configure`, `configure.py --apply-json`), Stage 2 (`make enable-connectors`)
- **Exact File Path(s) & Line Numbers:**
  - `./scripts/configure.py` (Lines `38–91` — `CONNECTOR_OPTIONS`, `270–328` — `determine_stage`, `330–355` — `get_interactive_questions`, `470–475` & `488–497` & `519–530` — `update_tfvars`, `844–945` — `enable_connectors`, `1032–1041` — `main`)
- **Evidence Quote/Snippet:**
  - `./scripts/configure.py` (Lines `470–475`):
```python
    # Stage 0 Safety Guard
    if stage == 0 and not allow_enable:
        updates["enable_connectors"] = False
        updates["enable_jira_connector"] = False
        updates["enable_confluence_connector"] = False
        updates["enable_people_directory_connector"] = False
```
  - `./scripts/configure.py` (Lines `488–497`):
```python
    # 2. Update enable_* flags
    for flag in ["enable_connectors", "enable_jira_connector", "enable_confluence_connector", "enable_people_directory_connector"]:
        if flag in updates:
            val_bool = "true" if updates[flag] else "false"
            spacing = "    " if flag == "enable_connectors" else " "
            line = f"{flag}{spacing}= {val_bool}"
            if re.search(r'^\s*' + re.escape(flag) + r'\s*=.*$', content, re.MULTILINE):
                content = re.sub(r'^\s*' + re.escape(flag) + r'\s*=.*$', line, content, flags=re.MULTILINE)
            else:
                content += f"\n{line}\n"
```
  - `./scripts/configure.py` (Lines `921–927`):
```python
    updates = {
        "enable_connectors": ("workspace" in planned),
        "enable_jira_connector": ("jira" in planned),
        "enable_confluence_connector": ("confluence" in planned),
        "enable_people_directory_connector": ("people_directory" in planned),
    }
    update_tfvars(actual_tfvars, updates, stage=stage, allow_enable=True, workdir=workdir)
```
  - `./scripts/configure.py` (Lines `1032–1041`):
```python
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
```
- **Problem Description & Operational Failure Mechanism:**
  `scripts/configure.py` was only partially updated during the Confluence and Slack branch merges:
  1. **Hardcoded `valid_set` in `main()` (`configure.py:1037–1041`) Aborts on `"confluence"` and `"slack"`**: When an agent or operator executes `python3 scripts/configure.py --apply-json '{"planned_connectors": ["workspace", "confluence", "slack"]}'` (or `--connectors`), line `1037` checks `valid_set = {"workspace", "jira", "people_directory"}` and aborts with `sys.exit(1)` (`Error: Invalid connector 'confluence'. Allowed: 'workspace', 'jira', 'people_directory'`). This causes `TestConfigureCLI.test_configure_stage_0_safety_guard_forces_enable_false` (`scripts/test_red.py:2000`) to fail with `AssertionError: 1 != 0`.
  2. **Missing `"slack"` in `CONNECTOR_OPTIONS` (`configure.py:38–91`)**: Neither interactive Mode B (`make configure`) nor `get_interactive_questions()` (`configure.py:330–355`, invoked by `python3 scripts/status.py --json` / `make status ARGS="--json"`) includes `"slack"`, causing `TestConfigureCLI.test_configure_interactive_questions_contract` (`scripts/test_red.py:1921`) to fail with `AssertionError: 'slack' not found in ['workspace', 'jira', 'confluence', 'people_directory']`.
  3. **Missing `"enable_slack_connector"` in `update_tfvars` (`configure.py:470–475, 488–497, 519–530`), `determine_stage` (`configure.py:302–316`), and `enable_connectors` (`configure.py:871–944`)**: In Stage 0, `update_tfvars` does not force `enable_slack_connector = false`. In Stage 2, `make enable-connectors` (`enable_connectors`) never validates `slack_config` (`instance_uri` / `team_id`, `connector_modes`) and never sets `"enable_slack_connector": ("slack" in planned)` in `updates` (`configure.py:921–926`), causing `TestConfigureCLI.test_configure_enable_connectors_stage_2_success` (`scripts/test_red.py:2053`) to fail (`AssertionError: False is not true`) and leaving `status.py:433–442` permanently stuck in Stage 2.
- **Concrete Actionable Improvement:**
  1. Add `"slack"` to `CONNECTOR_OPTIONS` (`scripts/configure.py:38–91`) with `"value": "slack"`, `"enable_flag": "enable_slack_connector"`, and `"docs_url": "https://docs.cloud.google.com/gemini/enterprise/docs/connectors/slack"`.
  2. At `scripts/configure.py:1037`, derive `valid_set = {opt["value"] for opt in CONNECTOR_OPTIONS}` (using `"value"`, **not** `"id"`, as every dict in `CONNECTOR_OPTIONS` uses the key `"value"`).
  3. Add `"enable_slack_connector"` to the Stage 0 safety guard (`configure.py:471–475`), the `enable_*` writer loop (`configure.py:489`), `skip_keys` (`configure.py:519–530`), `determine_stage` (`configure.py:302–316`), and `enable_connectors` (`configure.py:871–944`, including Slack URI/`team_id` and `FEDERATED` mode validation).

---

#### `DEPLOY-04` [High] — Unsourced `.env.jira`, Unchecked Confluence Credentials, and Unchecked `workspace_admin_email` Between Stage 2 and Stage 3
- **ID:** `DEPLOY-04`
- **Category:** `Deployment Process`
- **Severity:** `High`
- **Stage(s) Impacted:** Stage 2 (`dwd_authorization`) -> Stage 3 (`connectors_and_engines_apply`)
- **Exact File Path(s) & Line Numbers:**
  - `./scripts/configure.py` (Lines `412–433`, `566–576`, `890–911`)
  - `./scripts/status.py` (Lines `31–38`, `464–570`, specifically `503–540`)
  - `./Makefile` (Lines `66–73`)
  - `./main.tf` (Lines `463–466`)
  - `./variables.tf` (Lines `44–48`)
  - `./terraform.tfvars.example` (Line `8`)
- **Evidence Quote/Snippet:**
  - `./scripts/configure.py` (Lines `566–576`):
```python
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
```
  - `./scripts/configure.py` (Lines `890–911`):
```python
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

    if "confluence" in planned:
        confluence_cfg = tfvars.get("confluence_config", {})
        confluence_uri = str(confluence_cfg.get("instance_uri", "")).strip()
        jira_cfg = tfvars.get("jira_config", {})
        jira_uri = str(jira_cfg.get("instance_uri", "")).strip()
        effective_uri = confluence_uri or jira_uri
        if not effective_uri or is_placeholder(effective_uri):
            errors.append("Confluence prerequisite missing: confluence_config.instance_uri (or fallback jira_config.instance_uri) must be configured.")

    if errors:
```
  - `./scripts/status.py` (Lines `503–540`):
```python
    if enable_confluence_connector:
        confluence_cfg = tfvars.get("confluence_config", {})
        jira_cfg = tfvars.get("jira_config", {})
        # Fall back to jira instance_uri if not explicitly configured in confluence_cfg
        instance_uri = str(confluence_cfg.get("instance_uri", "")).strip() or str(jira_cfg.get("instance_uri", "")).strip()
        if not instance_uri or "example.atlassian.net" in instance_uri:
            return {
                "phase": 2,
                "phase_name": "confluence_authorization",
                "owner": "human",
                "blockers": ["Atlassian Confluence instance URI not configured or placeholder in terraform.tfvars"],
                "next_action": "make confluence-checklist",
                "handoff_template": "confluence",
                "exit_code": 2
            }
        connector_modes = confluence_cfg.get("connector_modes")
        if isinstance(connector_modes, list) and ("DATA_INGESTION" in connector_modes or "FEDERATED" not in connector_modes):
            return {
                "phase": 2,
                "phase_name": "confluence_authorization",
                "owner": "human",
                "blockers": ["Confluence connector must use FEDERATED mode (connector_modes = [\"FEDERATED\"]) in terraform.tfvars"],
                "next_action": "make confluence-checklist",
                "handoff_template": "confluence",
                "exit_code": 2
            }
        confluence_auth_type = str(tfvars.get("confluence_auth_type", "OAUTH")).strip().upper()
        data_source = str(confluence_cfg.get("data_source", "confluence")).strip()
        if ".atlassian.net" in instance_uri.lower() and (confluence_auth_type in ("BASIC_AUTH", "API_TOKEN") or data_source == "confluence_server"):
            return {
                "phase": 2,
                "phase_name": "confluence_authorization",
                "owner": "human",
                "blockers": ["Atlassian Confluence Cloud (*.atlassian.net) requires OAuth 2.0 (confluence_auth_type = \"OAUTH\" and data_source = \"confluence\"), not BASIC_AUTH/API_TOKEN"],
                "next_action": "make confluence-checklist",
                "handoff_template": "confluence",
                "exit_code": 2
            }
```
  - `./Makefile` (Lines `66–73`):
```makefile
plan-connectors:
	@mkdir -p .plans
	terraform plan -input=false -out=.plans/connectors.tfplan
	python3 scripts/plan_guard.py .plans/connectors.tfplan

apply-connectors:
	python3 scripts/plan_guard.py .plans/connectors.tfplan
	terraform apply -input=false .plans/connectors.tfplan
```
  - `./main.tf` (Lines `463–466`):
```hcl
      params = {
        "impersonated_user_email_address" = var.workspace_admin_email
        "super_admin_service_account"     = "service-${google_project.projects[env_key].number}@gcp-sa-discoveryengine.iam.gserviceaccount.com"
      }
```
- **Problem Description & Operational Failure Mechanism:**
  Three credential and prerequisite validation gaps exist between Stage 0/2 (`scripts/configure.py` and `scripts/status.py`) and Stage 3 (`Makefile` and `main.tf`):
  1. **`.env.jira` Written by `configure.py` Is Never Sourced by `Makefile`**: When `jira_auth` is passed via `configure.py --apply-json`, `configure.py:567–576` writes `export TF_VAR_jira_auth='...'` to `.env.jira` and excludes `jira_auth` from `terraform.tfvars` (`skip_keys` at line `529`). Both `audit_inputs` (`configure.py:414`) and `enable_connectors` (`configure.py:892`) treat `os.path.exists(os.path.join(workdir, ".env.jira"))` as valid credentials. However, `Makefile:66–73` (`plan-connectors` and `apply-connectors`) executes `terraform plan` and `terraform apply` in fresh subshells without sourcing `.env.jira`, so `var.jira_auth` defaults to `{}` (`variables.tf:170`) and provisions Jira connectors with empty `client_id` / `client_secret` (`main.tf:171–172`).
  2. **Zero Confluence Credential Validation in `status.py` and `configure.py`**: Neither `scripts/status.py:503–540` (`enable_confluence_connector`) nor `scripts/configure.py:902–910` (`if "confluence" in planned:`) checks whether `TF_VAR_confluence_auth` (or fallback `TF_VAR_jira_auth` / `confluence_auth` / `jira_auth`) is set! Furthermore, `configure.py:902–910` only checks `effective_uri` and omits the `connector_modes = ["FEDERATED"]` and `*.atlassian.net` OAuth checks that `status.py:518–540` performs.
  3. **Unchecked `workspace_admin_email` for `people_directory`**: When `enable_people_directory_connector = true`, `main.tf:463–466` passes `"impersonated_user_email_address" = var.workspace_admin_email` into `params`. Yet `var.workspace_admin_email` defaults to `null` (`variables.tf:47`) and `"admin@example.com"` in `terraform.tfvars.example:8` (which is not in `PLACEHOLDER_STRINGS` at `status.py:31–38` or `configure.py:93–100`), and neither `configure.py:898–900` nor `status.py` validates that `workspace_admin_email` is non-null and non-placeholder.
- **Concrete Actionable Improvement:**
  1. Update `Makefile` (`plan-connectors` and `apply-connectors` at `Makefile:66–73`) to source `.env.jira` (and `.env.confluence` / `.env.slack` if present) before running `terraform plan` and `terraform apply`: `[ -f .env.jira ] && . ./.env.jira; terraform plan -input=false -out=.plans/connectors.tfplan`.
  2. In `scripts/configure.py:902–910` and `scripts/status.py:503–540`, verify that Confluence credentials exist in `TF_VAR_confluence_auth`, `TF_VAR_jira_auth`, `.env.confluence`, `.env.jira`, or `terraform.tfvars`, and enforce `FEDERATED` mode and OAuth on `*.atlassian.net` in `configure.py:902–910`.
  3. Add `"admin@example.com"` to `PLACEHOLDER_STRINGS` (`status.py:31–38`, `configure.py:93–100`) and validate `workspace_admin_email` whenever `people_directory` is planned or `enable_people_directory_connector` is `True`.

---

#### `DEPLOY-05` [High] — Stage 4 Infinite Loop & Unverified User Store License Binding Across `Makefile`, `allocate_licenses.py`, and `status.py`
- **ID:** `DEPLOY-05`
- **Category:** `Deployment Process`
- **Severity:** `High`
- **Stage(s) Impacted:** Stage 4 (`license_distribution`) -> Stage 5 (`verification`)
- **Exact File Path(s) & Line Numbers:**
  - `./Makefile` (Lines `75–79` — `licenses-dryrun`, `licenses`)
  - `./scripts/status.py` (Lines `657–684`)
  - `./scripts/allocate_licenses.py` (Lines `524–569`)
  - `./main.tf` (Lines `588–601` — `resource "google_discovery_engine_user_store" "default"`)
  - `./outputs.tf` (Lines `39–42` — `output "user_store_names"`)
  - `./AGENTS.md` (Line `49`)
- **Evidence Quote/Snippet:**
  - `./Makefile` (Lines `75–79`):
```makefile
licenses-dryrun:
	python3 scripts/allocate_licenses.py --distribute --dry-run

licenses: licenses-dryrun
	python3 scripts/allocate_licenses.py --distribute
```
  - `./scripts/status.py` (Lines `657–673`):
```python
    # Check if license_config_names is configured in tfvars (loop closed)
    lic_config_names = tfvars.get("license_config_names", {})
    licenses_distributed = (
        bool(lic_config_names) and
        all(env in lic_config_names for env in environments)
    )

    if not licenses_distributed:
        return {
            "phase": 4,
            "phase_name": PHASES[4],
            "owner": "agent",
            "blockers": [],
            "next_action": "make licenses",
            "handoff_template": None,
            "exit_code": 0
        }
```
  - `./scripts/allocate_licenses.py` (Lines `524–569`):
```python
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

            active_cfg = next((c for c in cfgs if c.get("state") == "ACTIVE" and not c.get("freeTrial")), None)
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
```
  - `./main.tf` (Lines `588–601`):
```hcl
resource "google_discovery_engine_user_store" "default" {
  for_each                           = local.environments
  project                            = google_project.projects[each.key].project_id
  location                           = var.location
  user_store_id                      = "default_user_store"
  default_license_config             = lookup(var.license_config_names, each.key, null)
  enable_license_auto_register       = lookup(var.license_config_names, each.key, null) != null
  enable_expired_license_auto_update = lookup(var.license_config_names, each.key, null) != null

  depends_on = [
    google_project_service.services,
    google_discovery_engine_acl_config.idp
  ]
}
```
- **Problem Description & Operational Failure Mechanism:**
  1. **Stage 4 Infinite Loop on `make licenses`**: In Stage 4, `scripts/status.py:657–673` checks whether `lic_config_names = tfvars.get("license_config_names", {})` contains all `environments` in `terraform.tfvars`; when empty, it returns `phase: 4` with `next_action: "make licenses"` (`AGENTS.md:49`). However, `Makefile:78–79` (`make licenses`) runs `python3 scripts/allocate_licenses.py --distribute`, which returns at `scripts/allocate_licenses.py:528` without writing `license_config_names` into `terraform.tfvars` and without invoking `--configure-auto-register` (`scripts/allocate_licenses.py:531–569`). When the agent or operator runs `make status` after `make licenses` (`AGENTS.md:10` Rule 1), `tfvars.get("license_config_names", {})` is still `{}` and `status.py` emits `next_action: "make licenses"` again in an infinite loop (while a second run of `make licenses` fails in `run_preflight_assertions` per `DEPLOY-06`).
  2. **Premature Advancement to Stage 5 Without Verifying `google_discovery_engine_user_store.default` State Attributes (`CHAL-03`)**: Even after `license_config_names` is populated in `terraform.tfvars` (e.g., via `python3 scripts/allocate_licenses.py --emit-tfvars` per `RUNBOOK.md:290–292`), `scripts/status.py:657–684` immediately advances to Stage 5 (`next_action: "make verify"`) based solely on `tfvars.get("license_config_names", {})` without checking `terraform.tfstate` to verify that `google_discovery_engine_user_store.default` (`main.tf:588–601`) has actually been updated in state with `default_license_config` bound and `enable_license_auto_register = true`!
  3. **Why Checking `outputs.user_store_names` Alone Is Invalid (`CHAL-03`)**: Because `resource "google_discovery_engine_user_store" "default"` (`main.tf:588–601`) uses `for_each = local.environments`, the UserStore resource is created in **Stage 1 (`foundation`)** for every environment with `default_license_config = null` and `enable_license_auto_register = false`. Consequently, `outputs.user_store_names` (`outputs.tf:39–42`) is already non-empty from Stage 1 onward. Checking `outputs.user_store_names` alone would falsely mark Stage 4 complete before any licenses are distributed or bound. Instead, `status.py` must inspect the `google_discovery_engine_user_store` resource instances in `state.get("resources", [])` and verify that `attributes.default_license_config` is non-null and `attributes.enable_license_auto_register` is `True` for every environment (and if `Makefile:66–69` `plan-connectors` is ever scoped with `-target` flags, it must include `-target=google_discovery_engine_user_store.default`).
- **Concrete Actionable Improvement:**
  1. Add a `--write-tfvars` flag to `scripts/allocate_licenses.py` (calling `configure.update_tfvars()` to persist `license_config_names` into `terraform.tfvars`) and update `Makefile:78–79` (`licenses`) to execute `--distribute --configure-auto-register --write-tfvars` followed by reconciling `google_discovery_engine_user_store.default` in Terraform state.
  2. Update `scripts/status.py:657–684` so that after `lic_config_names` is present in `terraform.tfvars`, `status.py` inspects the `google_discovery_engine_user_store` instances in `state["resources"]` to confirm `enable_license_auto_register == True` and `default_license_config == lic_config_names[env]`; if `license_config_names` is in `terraform.tfvars` but not yet applied to `google_discovery_engine_user_store.default` in `terraform.tfstate`, return `phase: 4` with `next_action: "make plan-connectors && make apply-connectors"`.

---

#### `DEPLOY-06` [High] — Stage 4 Preflight Capacity Check & `load_config` Block `--discover`, Idempotent Re-Runs, Seat Scaling, and `--configure-auto-register`
- **ID:** `DEPLOY-06`
- **Category:** `Deployment Process`
- **Severity:** `High`
- **Stage(s) Impacted:** Stage 4 (`license_distribution`)
- **Exact File Path(s) & Line Numbers:**
  - `./scripts/allocate_licenses.py` (Lines `168–184` — `run_preflight_assertions`, `361–364` — `load_config`, `432–481` — `main`, `500–506` — `--distribute` loop)
- **Evidence Quote/Snippet:**
  - `./scripts/allocate_licenses.py` (Lines `168–184`):
```python
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
```
  - `./scripts/allocate_licenses.py` (Lines `361–364`):
```python
    required_fields = ["billing_account", "subscription_id", "allocations"]
    missing = [f for f in required_fields if f not in data or data[f] is None or data[f] == ""]
    if missing:
        raise ValueError(f"Missing required field(s) in {config_file}: {', '.join(missing)}")
```
  - `./scripts/allocate_licenses.py` (Lines `452–481`):
```python
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
```
  - `./scripts/allocate_licenses.py` (Lines `500–506`):
```python
                    active_cfg = next((c for c in existing_cfgs if c.get("state") == "ACTIVE" and not c.get("freeTrial")), None)
                    current_seats = int(active_cfg.get("licenseCount", "0")) if active_cfg else 0
                    cfg_short = active_cfg.get("name", "").split("/")[-1] if active_cfg else None
                    if active_cfg and current_seats >= int(seats):
                        print(f"  • Already distributed ({current_seats} seat(s) active in {cfg_short}) — skipping duplicate distribution.")
                    else:
                        delta_seats = int(seats) - current_seats
```
- **Problem Description & Operational Failure Mechanism:**
  1. **Circular `--discover` Dependency (`allocate_licenses.py:361–364, 434–454`)**: `RUNBOOK.md:268, 274` and `AGENTS.md:96, 124` instruct running `python3 scripts/allocate_licenses.py --discover` to discover `subscription_id` and `license_config_id`. Although `if args.discover:` (line `452`) runs before `validate_required_params()` (line `457`), `load_config(args.config_file)` is called unconditionally at line `434` and enforces `required_fields = ["billing_account", "subscription_id", "allocations"]` at line `361`. When `var.subscription_id` is still `""` (`variables.tf:134`), `config/license_allocations.json` (`main.tf:746`) has `"subscription_id": ""`, causing `--discover` to crash at line `436` with `ValueError: Missing required field(s) in config/license_allocations.json: subscription_id`.
  2. **Gross vs. Net Seat Comparison in `run_preflight_assertions` (`allocate_licenses.py:168–184, 468`)**: While the `--distribute` loop (`lines 500–506`) is delta-aware (`delta_seats = int(seats) - current_seats`), `run_preflight_assertions` (called when `not args.skip_preflight and (args.distribute or args.configure_auto_register)` at line `468`) sums gross `total_requested_seats = sum(int(item.get("seat_count", 0)) for item in allocations)` (`line 171`) and requires `total_requested_seats <= available_seats` (`line 178`). Once seats are distributed (e.g., 5 of 5 seats distributed so `available_seats == 0`), any subsequent run of `make licenses`, `make licenses-dryrun`, `--configure-auto-register`, or incremental seat scaling fails at line `179` with `ValueError: Preflight assertion failed: Insufficient license seats in billing pool!`. Because `AGENTS.md:20` forbids `--skip-preflight`, Stage 4 is deadlocked.
- **Concrete Actionable Improvement:**
  1. Allow `load_config(args.config_file, require_subscription=not args.discover)` to succeed when `args.discover` is set (and fall back to reading `billing_account` and `billing_project` from `terraform.tfvars` if `config/license_allocations.json` does not exist yet).
  2. In `run_preflight_assertions` (`scripts/allocate_licenses.py:168–184`), query each project's active non-trial `licenseConfig` via `get_license_configs(p_id, location, token)`, compute `net_requested_seats = sum(max(0, int(item.get("seat_count", 0)) - current_seats_for(item)) for item in allocations)`, and assert `net_requested_seats <= available_seats` and `total_requested_seats <= total_capacity`.

---

#### `DEPLOY-07` [High] — Stage 5 `make verify WAIT=15m` Exits `0` Immediately Without Waiting on `"INITIALIZING"` Connectors, Exits `0` on Timeout, and Ignores `expected_seats`
- **ID:** `DEPLOY-07`
- **Category:** `Deployment Process`
- **Severity:** `High`
- **Stage(s) Impacted:** Stage 5 (`verification`)
- **Exact File Path(s) & Line Numbers:**
  - `./scripts/verify.py` (Lines `124–133` — `check_data_connectors`, `198–215` — `check_license_configs`, `229–248` — `verify_project`, `345–353` & `387` — `main`)
  - `./Makefile` (Lines `84–85` — `verify`)
- **Evidence Quote/Snippet:**
  - `./scripts/verify.py` (Lines `124–133`):
```python
        if errors:
            details_parts.append(f"Errors: {len(errors)}")

        status = state
        if errors or state in ("FAILED", "ERROR", "INITIALIZATION_FAILED") or "FAIL" in state:
            status = "ERROR"
        elif blocking_reasons or state in ("PAUSED", "INITIALIZING"):
            status = "WARN"

        results.append((f"Connector ({data_source})", status, ", ".join(details_parts)))
```
  - `./scripts/verify.py` (Lines `229–248`):
```python
def verify_project(project_id, location, token, expected_seats=None, silent=False):
    all_checks = []
    all_checks.extend(check_user_store(project_id, location, token))
    all_checks.extend(check_license_configs(project_id, location, token))
    all_checks.extend(check_data_connectors(project_id, location, token))
    all_checks.extend(check_search_engine(project_id, location, token))
    all_checks.extend(check_assistant(project_id, location, token))

    has_failures = False
    for comp, stat, det in all_checks:
        if not silent:
            print_row(comp, stat, det)
        if stat in ("ERROR", "FAIL"):
            has_failures = True

    if not silent:
        console_url = f"https://console.cloud.google.com/gen-app-builder/engines?project={project_id}"
        print(f"\n  • Gemini Enterprise Console : {console_url}\n")

    return not has_failures, all_checks
```
  - `./scripts/verify.py` (Lines `345–353`):
```python
        has_creating = any(
            c["status"] in ("CREATING", "INITIALIZING", "STATE_CREATING", "UPDATING")
            for r in json_results
            for c in r["checks"]
        )
        # If everything succeeded (and nothing is still creating when waiting) or no waiting requested, break
        elapsed = time.time() - start_time
        if (overall_success and not has_creating) or elapsed >= max_wait_seconds:
            break
```
- **Problem Description & Operational Failure Mechanism:**
  1. **`"INITIALIZING"` Connectors Bypass `--wait` Polling (`verify.py:130–131, 345–353`)**: In `check_data_connectors` (`scripts/verify.py:130–131`), when a connector's state is `"INITIALIZING"`, `elif blocking_reasons or state in ("PAUSED", "INITIALIZING"): status = "WARN"` overwrites `status` to `"WARN"`. In `main()` (`scripts/verify.py:345–349`), `has_creating` checks `c["status"] in ("CREATING", "INITIALIZING", "STATE_CREATING", "UPDATING")`. Because `c["status"]` was overwritten to `"WARN"` at line `131`, `has_creating` evaluates to `False`! Simultaneously, `verify_project` (`line 241`) only sets `has_failures = True` when `stat in ("ERROR", "FAIL")`, so `overall_success` is `True`. Consequently, `if (overall_success and not has_creating)` at line `352` is `True` on the very first poll iteration (`elapsed == 0`), causing `make verify` (`Makefile:84–85`: `python3 scripts/verify.py --wait $(WAIT)`) to exit immediately with code `0` without waiting!
  2. **Polling Timeout While Still `"CREATING"` Exits `0` (`verify.py:352, 387`)**: When a connector is in `"CREATING"` state and `elapsed >= max_wait_seconds` is reached (`line 352`), the `while True:` loop breaks while `overall_success` is still `True` (since `"CREATING"` is not in `("ERROR", "FAIL")` at line `241`), so `sys.exit(0 if overall_success else 1)` (`line 387`) exits `0` even on timeout.
  3. **Unused `expected_seats` Parameter (`verify.py:198–215, 229–232, 331`)**: `verify_project` receives `expected_seats=proj.get("seat_count")` from `main()` (`line 331`), but never reads `expected_seats` or passes it to `check_license_configs(project_id, location, token)` (`line 232`). Even if 0 seats are distributed (`"WARN"` at line `207`), `verify.py` exits `0`.
- **Concrete Actionable Improvement:**
  1. In `check_data_connectors` (`scripts/verify.py:130–131`), keep `status = state` when `state == "INITIALIZING"` and `not blocking_reasons` (only setting `status = "WARN"` when `blocking_reasons` is non-empty or `state == "PAUSED"`), so `has_creating` (`line 346`) detects `"INITIALIZING"` and polls until `ACTIVE`.
  2. After the `while True:` loop in `main()` (`scripts/verify.py:353`), if `has_creating` is still `True`, set `overall_success = False` so wait timeouts exit `1`.
  3. Pass `expected_seats` into `check_license_configs(project_id, location, token, expected_seats=expected_seats)` (`verify.py:198, 232`) and return `"ERROR"` when active distributed seats `< expected_seats` (`expected_seats > 0`).

---

#### `DEPLOY-08` [High] — Unhandled Stage 3 `default_assistant` `HTTP 409 ALREADY_EXISTS` Race Condition
- **ID:** `DEPLOY-08`
- **Category:** `Deployment Process`
- **Severity:** `High`
- **Stage(s) Impacted:** Stage 3 (`connectors_and_engines_apply`)
- **Exact File Path(s) & Line Numbers:**
  - `./main.tf` (Lines `676–703` — `resource "google_discovery_engine_search_engine" "engines"`, and Lines `717–737` — `resource "google_discovery_engine_assistant" "default"`)
  - `./AGENTS.md` (Line `123`)
  - `./RUNBOOK.md` (Line `249`)
- **Evidence Quote/Snippet:**
  - `./main.tf` (Lines `676–703`):
```hcl
resource "google_discovery_engine_search_engine" "engines" {
  for_each          = (var.enable_connectors || var.enable_jira_connector || var.enable_confluence_connector || var.enable_slack_connector || var.enable_people_directory_connector) ? local.environments : {}
  project           = google_project.projects[each.key].project_id
  location          = var.location
  collection_id     = "default_collection"
  engine_id         = "${var.customer_id}-${each.key}-search-engine"
  display_name      = "${var.customer_name} (${each.value.display_name}) Search App"
  industry_vertical = "GENERIC"
  app_type          = "APP_TYPE_INTRANET"

  data_store_ids = flatten([
    for conn_key, conn in local.environment_connectors : [
      for entity in google_discovery_engine_data_connector.connectors[conn_key].entities :
      basename(entity.data_store)
      if try(trimspace(entity.data_store), "") != ""
    ]
    if conn.env_key == each.key
  ])

  search_engine_config {
    search_tier    = "SEARCH_TIER_STANDARD"
    search_add_ons = ["SEARCH_ADD_ON_LLM"]
  }

  depends_on = [
    google_discovery_engine_data_connector.connectors
  ]
}
```
  - `./main.tf` (Lines `717–737`):
```hcl
resource "google_discovery_engine_assistant" "default" {
  for_each           = (var.enable_connectors || var.enable_jira_connector || var.enable_confluence_connector || var.enable_slack_connector || var.enable_people_directory_connector) ? local.environments : {}
  project            = google_project.projects[each.key].project_id
  location           = var.location
  collection_id      = google_discovery_engine_search_engine.engines[each.key].collection_id
  engine_id          = google_discovery_engine_search_engine.engines[each.key].engine_id
  assistant_id       = "default_assistant"
  display_name       = "${var.customer_name} Assistant"
  web_grounding_type = "WEB_GROUNDING_TYPE_GOOGLE_SEARCH"

  generation_config {
    default_language = "en"
    system_instruction {
      additional_system_instruction = var.assistant_instructions
    }
  }

  depends_on = [
    google_discovery_engine_search_engine.engines
  ]
}
```
  - `./AGENTS.md` (Line `123`):
```markdown
| `assistant: 409 ALREADY_EXISTS` | Engine auto-creates `default_assistant` | Import into state before `make apply-connectors` |
```
- **Problem Description & Operational Failure Mechanism:**
  When `google_discovery_engine_search_engine.engines` (`main.tf:676–703`) is created with `search_add_ons = ["SEARCH_ADD_ON_LLM"]` (`main.tf:697`), the Discovery Engine backend automatically creates the singleton child resource `assistants/default_assistant`. Immediately afterward in the same Stage 3 `make apply-connectors` run, Terraform attempts to `CREATE` (`POST`) `google_discovery_engine_assistant.default` (`main.tf:717–737`, `assistant_id = "default_assistant"`), which fails with HTTP `400` / `409 ALREADY_EXISTS` (`Only one assistant per engine is allowed`). This aborts `make apply-connectors` mid-run, leaving `assistant_names` absent from state outputs (`status.py:573, 622`) and forcing manual `terraform import` commands (`RUNBOOK.md:249`).
- **Concrete Actionable Improvement:**
  Automate Stage 3 assistant reconciliation in `Makefile` (`plan-connectors` / `apply-connectors`) or via a small helper script that first applies `google_discovery_engine_data_connector.connectors` and `google_discovery_engine_search_engine.engines`, checks whether `google_discovery_engine_assistant.default["<env>"]` is already in `terraform state list` (importing `projects/<PROJECT_ID>/locations/<LOCATION>/collections/default_collection/engines/<ENGINE_ID>/assistants/default_assistant` if it already exists in GCP), and then applies `google_discovery_engine_assistant.default` updates cleanly via `PATCH`.

---

#### `DEPLOY-09` [High] — Local-Only Terraform State (`terraform.tfstate`) Without Remote Backend Locking, Stale `.tfplan` Execution Risk, and Silent Corrupted State Fallback
- **ID:** `DEPLOY-09`
- **Category:** `Deployment Process`
- **Severity:** `High`
- **Stage(s) Impacted:** All Stages (`0`–`5`)
- **Exact File Path(s) & Line Numbers:**
  - `./versions.tf` (Lines `1–17`)
  - `./Makefile` (Lines `45–52`, `66–73`)
  - `./scripts/plan_guard.py` (Lines `48–134`)
  - `./scripts/status.py` (Lines `113–121`, `268–272`, `297`)
  - `./scripts/configure.py` (Lines `259–267`, `290–293`)
- **Evidence Quote/Snippet:**
  - `./versions.tf` (Lines `1–17`):
```hcl
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.41"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 7.41"
    }
    local = {
      source  = "hashicorp/local"
      version = ">= 2.0.0"
    }
  }
}
```
  - `./Makefile` (Lines `66–73`):
```makefile
plan-connectors:
	@mkdir -p .plans
	terraform plan -input=false -out=.plans/connectors.tfplan
	python3 scripts/plan_guard.py .plans/connectors.tfplan

apply-connectors:
	python3 scripts/plan_guard.py .plans/connectors.tfplan
	terraform apply -input=false .plans/connectors.tfplan
```
  - `./scripts/status.py` (Lines `113–121`):
```python
def parse_state(state_path):
    """Parse local terraform.tfstate if it exists."""
    if not os.path.exists(state_path):
        return None
    try:
        with open(state_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        return {"_error": str(e)}
```
  - `./scripts/status.py` (Lines `268–272`):
```python
    actual_state_path = state_path or os.path.join(workdir, "terraform.tfstate")
    state = parse_state(actual_state_path)

    if state and "_error" not in state:
        state_project_ids = set()
```
- **Problem Description & Operational Failure Mechanism:**
  1. **Local-Only State & Incompatible Remote Backend Detection**: `versions.tf:1–17` configures no `backend "gcs" {}` block, storing `terraform.tfstate` (including plaintext connector OAuth secrets) on the local filesystem without state locking. Worse, because `status.py:113–121` and `configure.py:259–267` only read a local `terraform.tfstate` file on disk (`if not os.path.exists(state_path): return None`), configuring a remote GCS backend causes `status.py` and `configure.py` to permanently report Stage 1 (`foundation_apply`) even after Stage 1 is applied!
  2. **Silent Corrupted State Fallback (`status.py:271, 297`)**: If `terraform.tfstate` is truncated or contains invalid JSON, `parse_state` returns `{"_error": str(e)}` (`status.py:121`). Instead of halting with a state error, `status.py:271` (`if state and "_error" not in state:`) and `status.py:297` (`state_outputs = state.get("outputs", {}) if state and "_error" not in state else {}`) silently bypass the state mismatch guard and fall back to Stage 1 (`make plan-foundation && make apply-foundation`).
  3. **Stale `.tfplan` Execution (`Makefile:50–52, 71–73`)**: `apply-foundation` and `apply-connectors` run `plan_guard.py` on `.plans/foundation.tfplan` or `.plans/connectors.tfplan`, but neither `Makefile` nor `plan_guard.py:48–134` checks whether `terraform.tfvars` or `*.tf` was modified after the `.tfplan` file was created.
- **Concrete Actionable Improvement:**
  1. In `scripts/status.py:113–121` and `scripts/configure.py:259–267`, fail closed (returning a blocker with `exit_code: 1`) if `state` contains `"_error"`, and fall back to `terraform state pull` when a remote backend is configured and no explicit `--state-file` fixture override is passed.
  2. In `scripts/plan_guard.py:99–134`, verify that `os.path.getmtime(plan_path) >= os.path.getmtime("terraform.tfvars")` (when `terraform.tfvars` exists and `plan_path` is a binary `.tfplan`) and reject stale plans.

---

#### `DEPLOY-10` [Medium] — Dead `--deep` Drift Check Flag in `scripts/status.py`
- **ID:** `DEPLOY-10`
- **Category:** `Deployment Process`
- **Severity:** `Medium`
- **Stage(s) Impacted:** Stages 1–5
- **Exact File Path(s) & Line Numbers:**
  - `./scripts/status.py` (Lines `183–186`, `932`, `961–968`)
- **Evidence Quote/Snippet:**
  - `./scripts/status.py` (Lines `183–186`):
```python
def determine_status(workdir, state_path=None, tfvars_path=None, skip_auth_check=False, skip_tools_check=False, deep=False):
    """
    Core phase detection and health assessment logic.
    """
```
  - `./scripts/status.py` (Line `932`):
```python
    parser.add_argument("--deep", action="store_true", help="Perform deep drift check via terraform plan.")
```
  - `./scripts/status.py` (Lines `961–968`):
```python
    status_data = determine_status(
        workdir=os.path.abspath(args.workdir),
        state_path=args.state_file,
        tfvars_path=args.tfvars_file,
        skip_auth_check=args.skip_auth_check,
        skip_tools_check=args.skip_tools_check,
        deep=args.deep
    )
```
- **Problem Description & Operational Failure Mechanism:**
  `scripts/status.py` defines the `--deep` CLI flag (`help="Perform deep drift check via terraform plan."`) at line `932` and passes `deep=args.deep` into `determine_status()` at line `967`. However, inside `determine_status()` (`lines 183–685`), the `deep` parameter is never read or referenced anywhere. Operators or CI jobs running `python3 scripts/status.py --deep` or `make status ARGS="--deep"` receive zero `terraform plan -detailed-exitcode` drift verification.
- **Concrete Actionable Improvement:**
  Implement `deep=True` in `determine_status()` (`scripts/status.py:183–685`): when `deep=True` and `phase >= 1`, execute `terraform plan -input=false -detailed-exitcode -no-color` in `workdir` (with foundation `-var` overrides when in Stage 1/2) and surface `"drift_detected": True | False` and any drifted resource addresses in `status_data`.

---

#### `DEPLOY-11` [Medium] — Missing `serviceusage.googleapis.com` and `cloudresourcemanager.googleapis.com` in `base_services` & Missing Quota Project Header in `get_project_metadata`
- **ID:** `DEPLOY-11`
- **Category:** `Deployment Process`
- **Severity:** `Medium`
- **Stage(s) Impacted:** Stage 1 (`foundation_apply`), Stage 2 (`make dwd-checklist`), Stage 4 (`make licenses-dryrun` / `make licenses`)
- **Exact File Path(s) & Line Numbers:**
  - `./main.tf` (Lines `42–53` — `local.base_services`, and Lines `740–744` — `resource "local_file" "license_allocations"`)
  - `./scripts/status.py` (Lines `733–754` — `print_dwd_checklist`)
  - `./scripts/allocate_licenses.py` (Lines `107–116` — `get_billing_account_license_config` and `get_project_metadata`, and Lines `138–141` — `run_preflight_assertions`)
- **Evidence Quote/Snippet:**
  - `./main.tf` (Lines `42–53`):
```hcl
  # Map of all services that need to be enabled per customer environment project
  base_services = [
    "discoveryengine.googleapis.com",
    "cloudidentity.googleapis.com",
    "admin.googleapis.com",
    "gmail.googleapis.com",
    "calendar-json.googleapis.com",
    "drive.googleapis.com",
    "chat.googleapis.com",
    "iamcredentials.googleapis.com",
    "iam.googleapis.com"
  ]
```
  - `./scripts/status.py` (Lines `733–754`):
```python
    for _env, info in data.items():
        pnum = info.get("project_number")
        pid = info.get("project_id")
        if tok and pnum:
            try:
                url = f"https://serviceusage.googleapis.com/v1beta1/projects/{pnum}/services/discoveryengine.googleapis.com:generateServiceIdentity"
                req = urllib.request.Request(
                    url,
                    data=b"{}",
                    method="POST",
                    headers={
                        "Authorization": f"Bearer {tok}",
                        "x-goog-user-project": quota_proj or pid or pnum,
                        "Content-Type": "application/json",
                    },
                )
                resp = json.loads(urllib.request.urlopen(req).read().decode())
                uid = resp.get("response", {}).get("uniqueId")
                if uid:
                    info["client_id"] = uid
            except Exception:
                pass
```
  - `./scripts/allocate_licenses.py` (Lines `107–116`):
```python
def get_billing_account_license_config(billing_account, license_config_id, token, central_project):
    """Fetch details of the Billing Account level license config."""
    url = f"https://discoveryengine.googleapis.com/v1alpha/billingAccounts/{billing_account}/billingAccountLicenseConfigs/{license_config_id}"
    return make_request(url, token=token, project_id=central_project)


def get_project_metadata(project_id, token):
    """Query Cloud Resource Manager API to retrieve project number and status."""
    url = f"https://cloudresourcemanager.googleapis.com/v1/projects/{project_id}"
    return make_request(url, token=token)
```
- **Problem Description & Operational Failure Mechanism:**
  1. **Unenabled `serviceusage.googleapis.com` and `cloudresourcemanager.googleapis.com` in `local.base_services` (`main.tf:42–53`)**: When `var.billing_project` is `null` (the default in `variables.tf:70` and `terraform.tfvars.example:12`), `print_dwd_checklist` (`scripts/status.py:745`) sets `"x-goog-user-project": quota_proj or pid or pnum` (targeting the newly created customer environment project `pid`). Because `local.base_services` (`main.tf:42–53`) only enables 9 APIs (`discoveryengine`, `cloudidentity`, `admin`, `gmail`, `calendar-json`, `drive`, `chat`, `iamcredentials`, `iam`) and omits `serviceusage.googleapis.com` and `cloudresourcemanager.googleapis.com`, the `POST https://serviceusage.googleapis.com/v1beta1/projects/{pnum}/services/discoveryengine.googleapis.com:generateServiceIdentity` request fails with HTTP `403 SERVICE_DISABLED`. Because `status.py:753–754` catches `except Exception: pass`, `make dwd-checklist` silently omits the 21-digit numeric `client_id` (`uniqueId`) required by Google Workspace Admin Console (`RUNBOOK.md:150, 153`).
  2. **Missing Quota Project Header in `get_project_metadata` (`allocate_licenses.py:113–116, 139`)**: Unlike `get_billing_account_license_config` (`line 110`), `get_project_metadata(project_id, token)` (`lines 113–116`) calls `make_request(url, token=token)` without `project_id=central_project`. When using user ADC credentials without a default quota project, `https://cloudresourcemanager.googleapis.com/v1/projects/{project_id}` fails in preflight (`line 139`) with HTTP `403`.
- **Concrete Actionable Improvement:**
  1. Add `"serviceusage.googleapis.com"` and `"cloudresourcemanager.googleapis.com"` to `local.base_services` in `main.tf:43–53`.
  2. Update `get_project_metadata(project_id, token, central_project=None)` in `scripts/allocate_licenses.py:113–116` to pass `project_id=central_project` when provided, and log a warning to `sys.stderr` at `scripts/status.py:753–754` instead of silently swallowing the exception when `uniqueId` lookup fails.

---

#### `DEPLOY-12` [Medium] — Seat Downscaling & Partial Retraction (`fullRetract: false`) Unsupported in `scripts/allocate_licenses.py`
- **ID:** `DEPLOY-12`
- **Category:** `Deployment Process`
- **Severity:** `Medium`
- **Stage(s) Impacted:** Stage 4 / Day-2 License Operations
- **Exact File Path(s) & Line Numbers:**
  - `./scripts/allocate_licenses.py` (Lines `503–506`, `590–599`)
  - `./RUNBOOK.md` (Line `304`)
  - `./AGENTS.md` (Line `125`)
- **Evidence Quote/Snippet:**
  - `./scripts/allocate_licenses.py` (Lines `503–506`):
```python
                    if active_cfg and current_seats >= int(seats):
                        print(f"  • Already distributed ({current_seats} seat(s) active in {cfg_short}) — skipping duplicate distribution.")
                    else:
                        delta_seats = int(seats) - current_seats
```
  - `./scripts/allocate_licenses.py` (Lines `590–599`):
```python
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
```
  - `./RUNBOOK.md` (Line `304`):
```markdown
  3. **Single-Project Auto-Routing:** If only 1 project exists in `licenseConfigDistributions` when the billing order quantity increases, Discovery Engine auto-routes the new seats into that project's `licenseConfig`. Call `:retractLicenseConfig` (`fullRetract: false, licenseCount: "<delta>"`) on that project to return the seats to the billing pool before distributing to a new project.
```
- **Problem Description & Operational Failure Mechanism:**
  `RUNBOOK.md:304` and `AGENTS.md:125` instruct operators and agents to perform a partial seat retraction (`fullRetract: false, licenseCount: "<delta>"`) when Discovery Engine auto-routes newly purchased seats into the first project or when rebalancing seats across environments. However:
  1. `allocate_licenses.py --distribute` (`lines 503–504`) treats `current_seats > int(seats)` as `"Already distributed — skipping duplicate distribution"`, ignoring any downward seat adjustment in `seat_allocations`.
  2. `allocate_licenses.py --retract` (`line 597`) hardcodes `body={"licenseConfig": full_cfg_name, "fullRetract": True}` and provides no CLI flag (e.g., `--retract-seats <N>`) for partial retraction.
- **Concrete Actionable Improvement:**
  1. Add `--retract-seats <N>` to `scripts/allocate_licenses.py` so `--retract --target-project <id> --retract-seats <N>` sends `{"licenseConfig": full_cfg_name, "fullRetract": False, "licenseCount": str(N)}`.
  2. In `--distribute` (`scripts/allocate_licenses.py:503`), when `current_seats > int(seats)`, either perform an automatic partial retraction of `current_seats - int(seats)` seats or emit an explicit `[WARN]` with the exact `--retract --target-project <id> --retract-seats <delta>` command.

---

#### `DEPLOY-13` [Medium] — Legacy `bootstrap.sh` Bypasses `Makefile`, `plan_guard.py`, Numeric `uniqueId` Resolution, and Staged Variable Guards
- **ID:** `DEPLOY-13`
- **Category:** `Deployment Process`
- **Severity:** `Medium`
- **Stage(s) Impacted:** Stages 0–1
- **Exact File Path(s) & Line Numbers:**
  - `./bootstrap.sh` (Lines `41–58`)
- **Evidence Quote/Snippet:**
  - `./bootstrap.sh` (Lines `41–58`):
```bash
terraform init
terraform apply -var="sa_email=${SA_EMAIL}" -var="billing_project=${BOOTSTRAP_PROJECT}"

echo ""
echo "=========================================================================="
echo " NEXT STEPS: Workspace Admin Domain-Wide Delegation (DWD)"
echo "=========================================================================="
echo "1. Run the following command to retrieve the DWD authorization checklist:"
echo "   terraform output dwd_checklist"
echo "2. Authorize each environment's Discovery Engine service agent in the Admin Console:"
echo "   https://admin.google.com/ac/owl/domainwidedelegation"
echo "3. After authorization, deploy Workspace connectors & Gemini Enterprise apps:"
echo "   terraform apply -var=\"enable_connectors=true\""
echo "4. Distribute seat licenses to projects:"
echo "   python3 scripts/allocate_licenses.py --distribute"
echo "5. Verify the deployment:"
echo "   python3 scripts/verify.py"
echo "=========================================================================="
```
- **Problem Description & Operational Failure Mechanism:**
  `bootstrap.sh` predates the `Makefile` / `plan_guard.py` / `status.py` / `configure.py` workflow and violates Rules 1, 2, and 3 of `AGENTS.md:9–15`:
  1. Line `42` runs `terraform apply -var="sa_email=${SA_EMAIL}" -var="billing_project=${BOOTSTRAP_PROJECT}"` directly without generating a saved `.tfplan`, without running `scripts/plan_guard.py`, and without passing `-var="enable_connectors=false"` or any other connector disable overrides.
  2. Line `49` instructs the operator to run `terraform output dwd_checklist` (which only outputs `service_agent_email` at `outputs.tf:54`) instead of `make dwd-checklist` (`status.py:713–756`, which resolves the 21-digit numeric OAuth2 `uniqueId`).
  3. Line `53` instructs the operator to run `terraform apply -var="enable_connectors=true"`, bypassing `make enable-connectors` (`configure.py:844–945`) and `make plan-connectors && make apply-connectors` (`Makefile:66–73`).
- **Concrete Actionable Improvement:**
  Refactor `bootstrap.sh:41–58` so that after provisioning the service account and IAM binding (`lines 12–30`), it saves `sa_email` and `billing_project` into `terraform.tfvars` via `python3 scripts/configure.py --set sa_email="${SA_EMAIL}" --set billing_project="${BOOTSTRAP_PROJECT}"`, runs `terraform init`, and delegates Stage 1–5 execution to `make status`, `make plan-foundation && make apply-foundation`, `make dwd-checklist`, `make enable-connectors`, `make plan-connectors && make apply-connectors`, `make licenses`, and `make verify`.

---

#### `DEPLOY-14` [Low] — GitHub Actions CI Workflow (`.github/workflows/terraform.yml`) Diverges from `Makefile` (`make test`), Omits Marketing Packager Check, and Runs Unsanitized Ambient Environment
- **ID:** `DEPLOY-14`
- **Category:** `Deployment Process`
- **Severity:** `Low`
- **Stage(s) Impacted:** CI/CD
- **Exact File Path(s) & Line Numbers:**
  - `./.github/workflows/terraform.yml` (Lines `22–40`)
  - `./Makefile` (Lines `96–100`)
- **Evidence Quote/Snippet:**
  - `./.github/workflows/terraform.yml` (Lines `22–40`):
```yaml
      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: "1.14.8"
          terraform_wrapper: false

      - name: Terraform Format Check
        run: terraform fmt -check -diff

      - name: Terraform Init
        run: terraform init -backend=false

      - name: Terraform Validate
        run: terraform validate

      - name: Run Test Harness
        id: test_harness
        run: |
          python3 -u scripts/test_red.py 2>&1 | tee test_run.log
```
  - `./Makefile` (Lines `96–100`):
```makefile
test:
	python3 scripts/package_marketing_assets.py --check
	python3 scripts/test_red.py
	terraform fmt -check
	terraform validate
```
- **Problem Description & Operational Failure Mechanism:**
  1. **Divergence Between `.github/workflows/terraform.yml` and `Makefile` (`test:`)**: `Makefile:96–100` runs `python3 scripts/package_marketing_assets.py --check`, `python3 scripts/test_red.py`, `terraform fmt -check`, and `terraform validate`. By contrast, `.github/workflows/terraform.yml:28–40` duplicates individual commands, omits the standalone `python3 scripts/package_marketing_assets.py --check` (`make check-marketing`) step, and runs `terraform init -backend=false` (`line 32`) without `-lockfile=readonly`.
  2. **Unsanitized `GH_TOKEN`/`GITHUB_TOKEN` in Test Harness Step (`terraform.yml:37–40`)**: `python3 -u scripts/test_red.py 2>&1 | tee test_run.log` runs without clearing `GH_TOKEN` / `GITHUB_TOKEN`, which causes `TestBranchAndIssueContracts.test_create_github_issues_script_registration_and_args` (`scripts/test_red.py:2336–2378`) to attempt live GitHub issue creation against `REPO="org-owner/gemini-prism"` (`scripts/create_github_issues.sh:7`) if a token is injected into the runner environment. (Also note that the newly added `scripts/deploy_marketing_assets.py` wired into `Makefile:93–94` as `deploy-marketing` unconditionally writes `dist/marketing/brand-kit-governance.zip` at `scripts/deploy_marketing_assets.py:738` even when invoked with `--dry-run`.)
- **Concrete Actionable Improvement:**
  Update `.github/workflows/terraform.yml:31–40` to pass `-lockfile=readonly` to `terraform init -backend=false`, add an explicit step running `python3 -B scripts/package_marketing_assets.py --check`, and run `GH_TOKEN="" GITHUB_TOKEN="" GH_CONFIG_DIR=/tmp/empty_gh python3 -B -u scripts/test_red.py 2>&1 | tee test_run.log` with explicit `set -euo pipefail`.

---

## Part 3: Existing Issues & Actionable Improvements — Documentation & Templates (`DOC-01` – `DOC-12`)

### Summary Table: Documentation & Template Issues

| ID | Category | Severity | File(s) & Line Numbers | Summary |
| :--- | :--- | :---: | :--- | :--- |
| **DOC-01** | `Documentation` | **Critical** | `terraform.tfvars.example:17–21, 81–94`<br/>`variables.tf:79–90, 268–302`<br/>`PRACTITIONERS_GUIDE.md:219–231, 281–284`<br/>`RUNBOOK.md:170–173, 181, 187, 226`<br/>`AGENTS.md:39, 80–85` | `terraform.tfvars.example` and `variables.tf` omit Slack connector variables (`enable_slack_connector`, `slack_auth_type`, `slack_auth`, `slack_config`) and `"slack"` in `planned_connectors`, even though Slack is documented in `PRACTITIONERS_GUIDE.md`, `RUNBOOK.md`, and `AGENTS.md` and referenced throughout `main.tf` and `outputs.tf` |
| **DOC-02** | `Documentation` | **Critical** | `AGENTS.md:80–85`<br/>`RUNBOOK.md:170–173, 195, 214`<br/>`PRACTITIONERS_GUIDE.md:227, 310, 364, 558`<br/>`scripts/status.py:396, 439, 555`<br/>`Makefile:1, 18–21, 45–64`<br/>`README.md:206–226` | Documentation (`AGENTS.md`, `RUNBOOK.md`, `PRACTITIONERS_GUIDE.md`) and `status.py` instruct operators/agents to run `make slack-checklist`, which does not exist in `Makefile`; `Makefile` (`plan-foundation`) also omits `-var="enable_slack_connector=false"`, and `README.md` omits `make slack-checklist` and `make licenses-list` |
| **DOC-03** | `Documentation` | **High** | `AGENTS.md:5–6, 25–26, 42`<br/>`.agent/workflows/deploy.md:1–11`<br/>`Makefile:33–34`<br/>`RUNBOOK.md:62` | `AGENTS.md` and `.agent/workflows/deploy.md` instruct agents to execute `make status --json`, which fails in GNU Make (`make: unrecognized option '--json'`, exit code `2`); `Makefile` requires `make status ARGS="--json"` |
| **DOC-04** | `Documentation` | **High** | `PRACTITIONERS_GUIDE.md:133–151, 188–200, 628`<br/>`RUNBOOK.md:156, 192`<br/>`main.tf:482–495`<br/>`variables.tf:178, 203–206`<br/>`AGENTS.md:15, 22` | `PRACTITIONERS_GUIDE.md` contains an outdated 9-scope DWD block (`lines 133–151`, omitting 3 Directory/Schema scopes required by `main.tf:482–495` and `line 628`) and an outdated Jira `DATA_INGESTION` table (`lines 188–200`, violating `AGENTS.md:15, 22` and `variables.tf:203–206`) |
| **DOC-05** | `Documentation` | **High** | `terraform.tfvars.example:8, 81–94`<br/>`variables.tf:44–48, 215–235`<br/>`main.tf:436–471`<br/>`outputs.tf:143–164`<br/>`scripts/status.py:907–916`<br/>`AGENTS.md:15, 22`<br/>`RUNBOOK.md:206`<br/>`PRACTITIONERS_GUIDE.md:239–266` | People Directory configuration conflicts across `terraform.tfvars.example` / `status.py` / `outputs.tf` (`google_people_directory`, `INCREMENTAL`, 5 entities) vs. `variables.tf` / `main.tf` (`native_cloud_identity`, `DATA_INGESTION`, `PERIODIC`, `["users"]`); `AGENTS.md` bans `DATA_INGESTION` without carving out `native_cloud_identity`; and `main.tf:464` requires `workspace_admin_email` documented as optional |
| **DOC-06** | `Documentation` | **High** | `scripts/configure.py:38–91, 102–180, 302–309, 357–446, 470–498, 519–530, 586–599, 871–944, 951–954, 1037–1041, 1094–1099` | `scripts/configure.py` CLI `--connectors` help string and `valid_set` (`{"workspace", "jira", "people_directory"}`) reject `confluence` and `slack`; `CONNECTOR_OPTIONS` omits `slack`; and `VARIABLE_METADATA` / `print_boxed_help` omit lookup guides for `confluence` and `slack` |
| **DOC-07** | `Documentation` | **Medium** | `docs/CONNECTORS_ROADMAP.md:11–19, 32–36`<br/>`README.md:35–38, 44–80, 179–181, 232–281`<br/>`main.tf:331–422` | `docs/CONNECTORS_ROADMAP.md` still lists Slack Enterprise as `📋 Accepted / Backlog` (`v1.4.0`, `Bot User OAuth (xoxb-)`) while Confluence and People Directory are `🟢 GA (Shipped)`; `README.md` still lists Slack (`P2`) and People Directory (`P4`) as unshipped roadmap items, omits them from the Mermaid architecture diagram, and omits `confluence`/`slack` in `planned_connectors` comment |
| **DOC-08** | `Documentation` | **Medium** | `README.md:127–136`<br/>`PRACTITIONERS_GUIDE.md:114–124`<br/>`scripts/status.py:738–750`<br/>`main.tf:43–53` | `README.md` omits `serviceusage.googleapis.com` from the bootstrap `gcloud services enable` command (unlike `PRACTITIONERS_GUIDE.md:122`), causing `make dwd-checklist` (`status.py:738–750`) to silently swallow an HTTP error and omit the 21-digit numeric DWD `client_id` (`uniqueId`) |
| **DOC-09** | `Documentation` | **Medium** | `bootstrap.sh:41–56`<br/>`outputs.tf:51–56`<br/>`AGENTS.md:8–24`<br/>`RUNBOOK.md:99–111` | `bootstrap.sh` runs unguarded `terraform apply` (bypassing `make plan-foundation` and `plan_guard.py`) and prints legacy `terraform output dwd_checklist` (where `outputs.tf:54` instructs using `service_agent_email` as Client ID) and `terraform apply -var="enable_connectors=true"` instead of `make dwd-checklist` and `make enable-connectors` |
| **DOC-10** | `Documentation` | **Medium** | `RUNBOOK.md:127–132`<br/>`main.tf:570–585`<br/>`outputs.tf:11–14` | `RUNBOOK.md` Stage 1 checklist claims Cloud Identity Admin Groups (`<customer_id>-<env>-admins@<domain>` and `<customer_id>-<env>-users@<domain>`) are provisioned, whereas `main.tf` only provisions `<customer_id>-<env>-users@<domain>` |
| **DOC-11** | `Documentation` | **Medium** | `PROJECT.md:47–50`<br/>`TEST_READY.md:24–28`<br/>`PRACTITIONERS_GUIDE.md:323, 473–477`<br/>`README.md:230–281`<br/>`AGENTS.md:52–109, 128–137` | Stale branch handoff files (`PROJECT.md` and `TEST_READY.md` citing `46` / `69` tests across `12` classes) remain at repository root; `PRACTITIONERS_GUIDE.md` cites outdated test (`46`) and template (`7`) counts (vs. `96` tests across `13` classes and `9` templates); and `PRACTITIONERS_GUIDE.md` is omitted from `README.md` and `AGENTS.md` |
| **DOC-12** | `Documentation` | **Low** | `Makefile:8–10`<br/>`scripts/verify.py:135–137`<br/>`.github/issues/01_confluence_connector.md:26–29, 46–50`<br/>`.github/issues/02_slack_connector.md:42–53, 74–78`<br/>`docs/` | `Makefile:9` banner and `scripts/verify.py:136` warning message omit Slack (`enable_slack_connector`); `.github/issues/01_confluence_connector.md` and `02_slack_connector.md` contain pre-implementation `INCREMENTAL` ingestion schemas and unchecked task boxes; and `docs/` has no `adr/` directory for Architecture Decision Records |

---

### Detailed Documentation & Template Findings

#### `DOC-01`: Missing Slack Connector Variables (`enable_slack_connector`, `slack_auth_type`, `slack_auth`, `slack_config`) and `"slack"` in `planned_connectors` Across `terraform.tfvars.example` and `variables.tf`
- **ID**: `DOC-01`
- **Category**: `Documentation`
- **Severity**: `Critical`
- **Exact File Path**:
  - `./terraform.tfvars.example` (Lines `17–21`, `81–94`)
  - `./variables.tf` (Lines `79–90`, `268–302`)
  - `./PRACTITIONERS_GUIDE.md` (Lines `219–231`, `281–284`)
  - `./RUNBOOK.md` (Lines `170–173`, `181`, `187`, `226`)
  - `./AGENTS.md` (Lines `39`, `80–85`, `120`)
- **Evidence Quote / Snippet**:
  - `./terraform.tfvars.example` (lines `17–21` and `81–94`):
    ```hcl
    # Discovery Engine & Workspace Connectors
    location             = "global"
    planned_connectors   = ["workspace"]
    enable_connectors    = false
    workspace_connectors = ["google_mail", "google_calendar", "google_drive", "google_chat"]
    ```
    ```hcl
    # Google People & Org Directory Connector (optional)
    enable_people_directory_connector = false

    people_directory_config = {
      data_source             = "google_people_directory"
      collection_id           = "people-directory-collection"
      display_name            = "Google People Directory"
      include_suspended_users = false
      org_units_include       = [] # e.g. ["/Employees", "/Contractors"]
      custom_schemas_include  = [] # e.g. ["Skills", "Certifications"]
      refresh_interval        = "86400s"
      sync_mode               = "INCREMENTAL"
      entities                = ["user_profile", "job_architecture", "reporting_hierarchy", "location_contact", "custom_attributes"]
    }
    ```
  - `./variables.tf` (lines `79–90`):
    ```hcl
    variable "planned_connectors" {
      type        = list(string)
      description = "List of enterprise connectors planned for deployment (workspace, jira, confluence, people_directory)"
      default     = ["workspace"]

      validation {
        condition = alltrue([
          for c in var.planned_connectors : contains(["workspace", "jira", "confluence", "people_directory"], c)
        ])
        error_message = "Each element of planned_connectors must be one of: 'workspace', 'jira', 'confluence', 'people_directory'."
      }
    }
    ```
  - `./PRACTITIONERS_GUIDE.md` (lines `219–231`):
    ```markdown
    #### 3.6 Plane 6: Slack Enterprise / Workspace Requirements (When `enable_slack_connector = true`)

    The repository supports deploying the **Slack Enterprise Data Connector** (`slack-collection`) alongside Google Workspace, Jira, and Confluence connectors or in a **Slack-only** deployment (`enable_connectors = false`, `enable_slack_connector = true`). Prism provisions the production **`v3` (`PUBLIC_GA`) Federated + Actions** connector backed by Slack's remote MCP endpoint (`https://mcp.slack.com`) via Google Cloud Business Application Platform (BAP).

    | Requirement Dimension | Option A: Google-Managed OAuth 2.0 (`slack_auth_type = "OAUTH"`, empty `slack_auth`) — **Default** | Option B: BYO Slack OAuth App (`slack_auth_type = "OAUTH"` + `client_id` & `client_secret`) |
    | :--- | :--- | :--- |
    | **Connector Architecture (`v3` `PUBLIC_GA`)** | `FEDERATED` + `ACTIONS` (`destination_configs` host `https://mcp.slack.com`, `auth_key = "OAuth"`). Zero Slack data copied into persistent GCP storage; queries execute live per user. | `FEDERATED` + `ACTIONS` (`destination_configs` host `https://mcp.slack.com`, `auth_key = "ByoOAuth"`). |
    | **Provisioned Entities** | `conversation`, `message`, `file` (configurable via `slack_config.entities`, with optional channel/privacy filters `channels_include`, `channels_exclude`, `include_private_channels`, `include_dms`) | `conversation`, `message`, `file` |
    | **Slack App Setup** | None required — uses Google's pre-registered Slack OAuth application. *(Ensure your Slack Workspace / Enterprise Grid allows member app installation or pre-approves the Google app.)* | Create a custom Slack App in [api.slack.com/apps](https://api.slack.com/apps) with Redirect URL `https://vertexaisearch.cloud.google.com/oauth-redirect` and scopes listed by `make slack-checklist`. |
    | **Required `terraform.tfvars` Settings** | `enable_slack_connector = true`, `slack_config.instance_uri = "https://<workspace>.slack.com"`, and optional `slack_config.team_id = "T..."` (`T...` for Workspace or `E...` for Enterprise Grid). | Same as Option A. |
    | **Runtime Secret Environment Variable (`TF_VAR_slack_auth`)** | **Not required** (leave `TF_VAR_slack_auth` unset). | `export TF_VAR_slack_auth='{"client_id":"...","client_secret":"..."}'` |
    | **End-User Authorization Flow** | Each user clicks **Sources → Connect** next to Slack once inside the Gemini Enterprise Web App (`vertexaisearch.cloud.google.com`) to authorize their individual Slack identity (`slack.com/oauth/v2/authorize`). | Same per-user **Sources → Connect** OAuth consent flow against your custom Slack App. |
    | **Static IP Allowlisting (Optional)** | Set `slack_config.static_ip_enabled = true`; allowlist the egress IPs emitted in `terraform output slack_checklist` (`static_ip_addresses`) inside Slack Enterprise Grid network settings. | Same as Option A. |
    ```
- **Problem Description**:
  `PRACTITIONERS_GUIDE.md` (§3.6, lines `219–231`, `281–284`), `RUNBOOK.md` (lines `170–173`, `181`, `187`, `226`), and `AGENTS.md` (lines `39`, `80–85`, `120`) document configuring `enable_slack_connector`, `slack_auth_type`, `slack_auth`, `slack_config`, and `"slack"` in `planned_connectors`, and `main.tf` (lines `331–422`, `477`, `677`, `707`, `718`) and `outputs.tf` (lines `166–209`) reference those variables directly. However, neither `terraform.tfvars.example` (which ends at line `94` after `people_directory_config`) nor `variables.tf` (which ends at line `302` after `confluence_config`) includes the Slack connector variable definitions, and `variables.tf:85–88` rejects `"slack"` in `planned_connectors`. As a result, `terraform validate` fails with 16 undeclared variable errors and `TestTerraformDefaultsContract.test_slack_v3_federated_defaults_contract` (`scripts/test_red.py:1714–1730`) fails at line `1722` (`AssertionError: 'variable "enable_slack_connector"' not found in variables.tf`).
- **Concrete Actionable Improvement**:
  1. Add `"slack"` to `planned_connectors` validation in `variables.tf:79–90` and to `terraform.tfvars.example:19`.
  2. Append the `enable_slack_connector`, `slack_auth_type`, `slack_auth`, and `slack_config` variable blocks to `variables.tf` (after line `302`), matching all attributes referenced in `main.tf:331–422` and the contract assertions in `scripts/test_red.py:1714–1730` (`entities = optional(list(string), ["conversation", "message", "file"])` and `incremental_refresh_interval = optional(string, "10800s")`).
  3. Append the `# Slack Enterprise Connector (optional)` block (`enable_slack_connector = false`, `slack_auth_type = "OAUTH"`, `slack_config = { ... }`) to `terraform.tfvars.example`.

---

#### `DOC-02`: `AGENTS.md`, `RUNBOOK.md`, `PRACTITIONERS_GUIDE.md`, and `scripts/status.py` Instruct Running Non-Existent `make slack-checklist` Target, and `Makefile` `plan-foundation` Omits `-var="enable_slack_connector=false"`
- **ID**: `DOC-02`
- **Category**: `Documentation`
- **Severity**: `Critical`
- **Exact File Path**:
  - `./AGENTS.md` (Lines `80–85`)
  - `./RUNBOOK.md` (Lines `170–173`, `195`, `214`)
  - `./PRACTITIONERS_GUIDE.md` (Lines `227`, `310`, `364`, `558`)
  - `./scripts/status.py` (Lines `396`, `439`, `555`)
  - `./Makefile` (Lines `1`, `18–21`, `45–64`)
  - `./README.md` (Lines `206–226`)
- **Evidence Quote / Snippet**:
  - `./AGENTS.md` (lines `80–85`):
    ````markdown
    ### `slack`
    ```text
    ACTION REQUIRED (Slack Admin): Configure Slack Enterprise authorization.
    Run `make slack-checklist` to view the Federated + MCP Actions setup, OAuth redirect URL, and target entities.
    Set slack_config.instance_uri (and optional team_id) in terraform.tfvars; optionally create a BYO Slack App in https://api.slack.com/apps and set TF_VAR_slack_auth.
    ```
    ````
  - `./RUNBOOK.md` (lines `170–174`):
    ```markdown
    7. If Slack Enterprise is planned (`"slack"` in `planned_connectors` or `enable_slack_connector = true`):
       - Run `make slack-checklist` to view the Slack workspace URI, `team_id`, OAuth callback URL (`https://vertexaisearch.cloud.google.com/oauth-redirect`), target federated entities (`conversation`, `message`, `file`), and scopes.
       - **Option A — Default Google-Managed OAuth (`slack_auth_type = "OAUTH"`, `v3` Federated + Actions):** No `TF_VAR_slack_auth` secret is required; set `slack_config.instance_uri` (e.g. `https://your-workspace.slack.com`) and optional `slack_config.team_id` (`T...` or `E...`) in `terraform.tfvars`. End users authorize Slack directly via **Sources → Connect** in the Gemini Enterprise Web App.
       - **Option B — Custom BYO Slack OAuth App (`slack_auth_type = "OAUTH"`):** Create a Slack App at [api.slack.com/apps](https://api.slack.com/apps) with redirect URL `https://vertexaisearch.cloud.google.com/oauth-redirect`, configure scopes from `make slack-checklist`, and export `export TF_VAR_slack_auth='{"client_id":"...","client_secret":"...","team_id":"T01234567"}'`.
    8. If Google People & Org Directory is planned (`"people_directory"` in `planned_connectors` or `enable_people_directory_connector = true`):
    ```
  - `./Makefile` (lines `1`, `18–21`, and `45–63`):
    ```makefile
    .PHONY: status configure check-inputs enable-connectors plan-foundation apply-foundation dwd-checklist jira-checklist confluence-checklist people-checklist plan-connectors apply-connectors licenses-dryrun licenses licenses-list verify check-marketing package-marketing deploy-marketing test help
    ```
    ```makefile
    	@echo "  dwd-checklist        - Print Google Workspace Domain-Wide Delegation authorization checklist"
    	@echo "  jira-checklist       - Print Atlassian Jira connector onboarding checklist"
    	@echo "  confluence-checklist - Print Atlassian Confluence connector onboarding checklist"
    	@echo "  people-checklist     - Print Google People Directory connector onboarding checklist"
    ```
    ```makefile
    plan-foundation:
    	@mkdir -p .plans
    	terraform plan -input=false -var="enable_connectors=false" -var="enable_jira_connector=false" -var="enable_confluence_connector=false" -var="enable_people_directory_connector=false" -out=.plans/foundation.tfplan
    	python3 scripts/plan_guard.py .plans/foundation.tfplan

    apply-foundation:
    	python3 scripts/plan_guard.py .plans/foundation.tfplan
    	terraform apply -input=false .plans/foundation.tfplan

    dwd-checklist:
    	@python3 scripts/status.py --dwd-checklist

    jira-checklist:
    	@python3 scripts/status.py --jira-checklist

    confluence-checklist:
    	@python3 scripts/status.py --confluence-checklist

    people-checklist:
    ```
- **Problem Description**:
  `AGENTS.md:83`, `RUNBOOK.md:171, 173, 195, 214`, `PRACTITIONERS_GUIDE.md:227, 310, 364, 558`, and `scripts/status.py:396, 439, 555` instruct users and agents to run `make slack-checklist`. Although `scripts/status.py:846–891, 930, 954–956` implements `--slack-checklist`, `Makefile` omits the `slack-checklist:` target, omits `slack-checklist` from `.PHONY` (`Makefile:1`) and `help` (`Makefile:18–21`), and omits `-var="enable_slack_connector=false"` from `plan-foundation` (`Makefile:47`). Running `make slack-checklist` fails with `make: *** No rule to make target 'slack-checklist'. Stop.` Furthermore, `README.md:206–226` (`Unified Command Surface (Makefile)`) omits both `make slack-checklist` and `make licenses-list`.
- **Concrete Actionable Improvement**:
  1. Add `slack-checklist` to `.PHONY` (`Makefile:1`), the `help` output (`Makefile:18–21`), and the target definitions (`Makefile:54–64`):
     ```makefile
     slack-checklist:
     	@python3 scripts/status.py --slack-checklist
     ```
  2. Add `-var="enable_slack_connector=false"` to `plan-foundation` (`Makefile:47`).
  3. Add `make slack-checklist` and `make licenses-list` to the `Makefile` table in `README.md:206–226`.

---

#### `DOC-03`: Invalid `make status --json` Command Syntax in `AGENTS.md` and `.agent/workflows/deploy.md` Causes GNU Make Failure
- **ID**: `DOC-03`
- **Category**: `Documentation`
- **Severity**: `High`
- **Exact File Path**:
  - `./AGENTS.md` (Lines `5–6`, `25–26`, `42`)
  - `./.agent/workflows/deploy.md` (Lines `1–11`)
  - `./Makefile` (Lines `33–34`)
  - `./RUNBOOK.md` (Line `62`)
- **Evidence Quote / Snippet**:
  - `./AGENTS.md` (lines `5–6`, `25–26`, and `42`):
    ```markdown
    ## Start Here
    Execute `make status --json`. Act on `next_action`. Reference the matching stage in [RUNBOOK.md](RUNBOOK.md).
    ```
    ```markdown
    ## Cross-Harness Combo-Box Protocol (Stage 0)
    When entering Stage 0 (`make status --json` reports `phase: 0`):
    ```
    ```markdown
    ## Phase Detection (`make status --json`)
    ```
  - `./.agent/workflows/deploy.md` (lines `1–11`):
    ```markdown
    ---
    description: Run staged Prism Gemini Enterprise deployment via status.py and RUNBOOK.md
    ---

    # Deploy Prism (Gemini Enterprise)

    1. Run `make status --json` to detect the live deployment phase and identify blockers.
    2. Consult [AGENTS.md](AGENTS.md) for rules of engagement and [RUNBOOK.md](RUNBOOK.md) for the active stage.
    3. If `owner` is `agent`: execute the recommended `next_action` (e.g. `make plan-foundation && make apply-foundation`).
    4. If `owner` is `human`: halt and present the specified `handoff_template` to the human operator.
    5. Repeat `make status --json` until all stages complete and `make verify` passes.
    ```
  - `./Makefile` (lines `33–34`):
    ```makefile
    status:
    	python3 scripts/status.py $(ARGS)
    ```
  - `./RUNBOOK.md` (line `62`):
    ```markdown
       - **Cross-Harness Combo-Box (Agents)**: Inspect the `interactive_questions` array via `make status ARGS="--json"` or `make check-inputs ARGS="--json"`. Present questions through native harness tools (`ask_question`, `AskUserQuestion`) and apply answers non-interactively:
    ```
- **Problem Description**:
  `AGENTS.md` (the top-level entry point for autonomous agents) and `.agent/workflows/deploy.md` instruct agents to execute `make status --json`. Because GNU `make` parses `--json` as a `make` CLI flag rather than forwarding it to the recipe, executing `make status --json` fails immediately with `make: unrecognized option '--json'` (exit code `2`). `Makefile:33–34` passes arguments via `$(ARGS)` (`make status ARGS="--json"`), as documented in `RUNBOOK.md:62` and `PRACTITIONERS_GUIDE.md:306`.
- **Concrete Actionable Improvement**:
  Replace all occurrences of `make status --json` in `AGENTS.md` (lines `6`, `26`, `42`) and `.agent/workflows/deploy.md` (lines `7`, `11`) with `make status ARGS="--json"` (or `python3 scripts/status.py --json`).

---

#### `DOC-04`: `PRACTITIONERS_GUIDE.md` Internal Contradictions — Outdated 9-Scope DWD List (vs. 12 Required Scopes) and Legacy `DATA_INGESTION` Jira Configuration (Violating Federated-Only Policy)
- **ID**: `DOC-04`
- **Category**: `Documentation`
- **Severity**: `High`
- **Exact File Path**:
  - `./PRACTITIONERS_GUIDE.md` (Lines `133–151`, `188–200`, `628`)
  - `./RUNBOOK.md` (Lines `156`, `192`)
  - `./main.tf` (Lines `482–495`)
  - `./variables.tf` (Lines `178`, `203–206`)
  - `./AGENTS.md` (Lines `15`, `22`, `115`)
- **Evidence Quote / Snippet**:
  - `./PRACTITIONERS_GUIDE.md` (lines `133–150` vs. line `628`):
    ````markdown
    | **Super Administrator** (Domain-Wide Delegation) | [admin.google.com/ac/owl/domainwidedelegation](https://admin.google.com/ac/owl/domainwidedelegation) | **Stage 2 Gate** | Authorizes each environment's Discovery Engine Service Agent (`service-<PROJECT_NUMBER>@gcp-sa-discoveryengine.iam.gserviceaccount.com`) using its **21-digit numeric `client_id` (`uniqueId`)** and the 9 read-only OAuth scopes output by `make dwd-checklist`. |
    | **Google Cloud Core Services API Control** | *Security > Access and data control > API controls > Google Cloud Core Services* | **Stage 2 Gate** | Confirm that the created customer GCP environment project IDs are permitted to access Google Workspace APIs if tenant-level API restrictions are enforced. |

    ##### Exact 9 OAuth 2.0 Scopes Required for Domain-Wide Delegation

    Copy and paste this exact comma-separated string (also emitted by `make dwd-checklist` under `oauth_scopes_csv`) into the Google Workspace Domain-Wide Delegation dialog for each environment's 21-digit Client ID:

    ```bash
    https://www.googleapis.com/auth/admin.directory.user.readonly,https://www.googleapis.com/auth/admin.directory.group.readonly,https://www.googleapis.com/auth/admin.directory.group.member.readonly,https://www.googleapis.com/auth/gmail.readonly,https://www.googleapis.com/auth/calendar.readonly,https://www.googleapis.com/auth/drive.readonly,https://www.googleapis.com/auth/chat.spaces.readonly,https://www.googleapis.com/auth/chat.messages.readonly,https://www.googleapis.com/auth/chat.memberships.readonly
    ```

    | Connector / Subsystem | Required OAuth 2.0 Scope | Access Level & Security Posture |
    | :--- | :--- | :--- |
    | **Google Workspace Directory & Identity ACLs (`GSUITE`)** | `https://www.googleapis.com/auth/admin.directory.user.readonly`<br/>`https://www.googleapis.com/auth/admin.directory.group.readonly`<br/>`https://www.googleapis.com/auth/admin.directory.group.member.readonly` | Read-only directory inspection to resolve user profiles and group memberships for search ACL enforcement. |
    | **Gmail Connector (`google_mail`)** | `https://www.googleapis.com/auth/gmail.readonly` | Read-only real-time federated query execution across user mail threads. |
    | **Calendar Connector (`google_calendar`)** | `https://www.googleapis.com/auth/calendar.readonly` | Read-only real-time federated query execution across user calendar events. |
    | **Drive Connector (`google_drive`)** | `https://www.googleapis.com/auth/drive.readonly` | Read-only real-time federated query execution across Google Drive files and shared drives. |
    | **Chat Connector (`google_chat`)** | `https://www.googleapis.com/auth/chat.spaces.readonly`<br/>`https://www.googleapis.com/auth/chat.messages.readonly`<br/>`https://www.googleapis.com/auth/chat.memberships.readonly` | Read-only real-time federated query execution across Google Chat spaces, messages, and space memberships. |
    ````
    ```markdown
    | `google_discovery_engine_data_connector: PERMISSION_DENIED` or `unauthorized_client` | Workspace Domain-Wide Delegation OAuth token propagation delay (typically 5–15 minutes) or missing scope. | Wait 5 minutes and retry `make apply-connectors`. If it persists past 15 minutes, run `make dwd-checklist` and verify the 21-digit `client_id` and all 12 scopes in [admin.google.com/ac/owl/domainwidedelegation](https://admin.google.com/ac/owl/domainwidedelegation). |
    ```
  - `./main.tf` (lines `482–495`):
    ```hcl
      dwd_scopes = [
        "https://www.googleapis.com/auth/admin.directory.user.readonly",
        "https://www.googleapis.com/auth/admin.directory.group.readonly",
        "https://www.googleapis.com/auth/admin.directory.group.member.readonly",
        "https://www.googleapis.com/auth/admin.directory.orgunit.readonly",
        "https://www.googleapis.com/auth/admin.directory.userschema.readonly",
        "https://www.googleapis.com/auth/directory.readonly",
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/calendar.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
        "https://www.googleapis.com/auth/chat.spaces.readonly",
        "https://www.googleapis.com/auth/chat.messages.readonly",
        "https://www.googleapis.com/auth/chat.memberships.readonly"
      ]
    ```
  - `./PRACTITIONERS_GUIDE.md` (lines `188–200`):
    ```markdown
    The repository supports deploying the **Atlassian Jira Data Connector** (`jira-collection`) either alongside Google Workspace connectors or in a **Jira-only** deployment (`enable_connectors = false`, `enable_jira_connector = true`).

    | Requirement Dimension | Option A: OAuth 2.0 3LO / 2LO (`jira_auth_type = "OAUTH"`) — **Recommended** | Option B: API Token / Basic Auth (`jira_auth_type = "BASIC_AUTH"` or `"API_TOKEN"`) |
    | :--- | :--- | :--- |
    | **Connector Version (`data_source_version`)** | `3` (Automatically selected by `main.tf` when `jira_auth_type` is `OAUTH`, `OAUTH2`, or `OAUTH_TWO_LEGGED`) | `1` (Automatically selected by `main.tf` when `jira_auth_type` is `BASIC_AUTH` or `API_TOKEN`) |
    | **Supported Modes (`connector_modes`)** | `["DATA_INGESTION"]` or `["DATA_INGESTION", "ACTIONS"]` (BAP Actions require OAuth 2.0) | `["DATA_INGESTION"]` only (`enable_actions` must be `false`) |
    | **Provisioned Entities** | `project`, `issue`, `attachment`, `comment`, `worklog` (configurable via `jira_config.entities`, with optional `project_keys_include` / `project_keys_exclude` filters) | `project`, `issue`, `attachment`, `comment`, `worklog` |
    | **Atlassian App / Token Setup** | Create an OAuth 2.0 (3LO) integration in [Atlassian Developer Console](https://developer.atlassian.com/console/myapps/) | Generate an API token at [id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens) |
    | **OAuth Callback / Redirect URLs** | **Ingestion Callback:** `https://vertexaisearch.cloud.google.com/console/oauth/jira_oauth.html`<br/>**Actions Callback:** `https://vertexaisearch.cloud.google.com/oauth-redirect` | Not applicable |
    | **Required Atlassian OAuth Scopes** | **Ingestion (7 Scopes):** `read:jira-work`, `read:jira-user`, `read:issue-details:jira`, `read:project:jira`, `read:jql:jira`, `read:board-scope:jira-software`, `offline_access`<br/>**BAP Actions (+4 Scopes when `enable_actions = true`):** `write:jira-work`, `write:issue:jira`, `write:comment:jira`, `write:attachment:jira` | Inherited from the Atlassian user account associated with `api_token` |
    | **Atlassian `cloudId` (`instance_id`)** | 36-character UUID automatically resolved by `make jira-checklist` (queries `https://<site>.atlassian.net/_edge/tenant_info`) | Optional |
    | **Runtime Secret Environment Variable (`TF_VAR_jira_auth`)** | `export TF_VAR_jira_auth='{"client_id":"...","client_secret":"...","refresh_token":"...","instance_id":"..."}'` | `export TF_VAR_jira_auth='{"user_account":"user@example.com","api_token":"..."}'` |
    | **Static IP Allowlisting (Optional)** | Set `jira_config.static_ip_enabled = true`; allowlist the egress IPs emitted in `terraform output jira_checklist` (`static_ip_addresses`) inside [admin.atlassian.com](https://admin.atlassian.com). | Same as Option A. |
    ```
- **Problem Description**:
  `PRACTITIONERS_GUIDE.md` has two severe internal and code-vs-doc contradictions:
  1. **9 vs. 12 DWD Scopes**: Section 3.3 (`PRACTITIONERS_GUIDE.md:133, 136–151`) instructs admins to paste 9 scopes, omitting `https://www.googleapis.com/auth/admin.directory.orgunit.readonly`, `https://www.googleapis.com/auth/admin.directory.userschema.readonly`, and `https://www.googleapis.com/auth/directory.readonly`. This contradicts `PRACTITIONERS_GUIDE.md:628` ("all 12 scopes"), `RUNBOOK.md:156, 192`, `main.tf:482–495`, and `scripts/status.py:720–733`.
  2. **Legacy `DATA_INGESTION` Jira Table**: Section 3.4 (`PRACTITIONERS_GUIDE.md:188–200`) documents `jira-collection` and `["DATA_INGESTION"]` or `["DATA_INGESTION", "ACTIONS"]`. This violates `AGENTS.md:15, 22` ("Provision all data connectors ... exclusively in `FEDERATED` mode" / "MUST NOT: Provision `DATA_INGESTION` connectors") and fails `variables.tf:203–206` validation (`error_message = "Jira connector must use FEDERATED mode (connector_modes = [\"FEDERATED\"])."`) and `scripts/status.py:478–489`.
- **Concrete Actionable Improvement**:
  1. Update `PRACTITIONERS_GUIDE.md:133–151` to `##### Exact 12 OAuth 2.0 Scopes Required for Domain-Wide Delegation` and include all 12 scopes from `main.tf:482–495`.
  2. Update `PRACTITIONERS_GUIDE.md:188–200` to `jira-federated-collection` and `["FEDERATED"]` or `["FEDERATED", "ACTIONS"]` (and note that `BASIC_AUTH` / `API_TOKEN` is only for self-managed Jira Data Center, never `*.atlassian.net`).

---

#### `DOC-05`: People Directory Schema, `DATA_INGESTION` Policy, and `workspace_admin_email` Contradictions Across `terraform.tfvars.example`, `variables.tf`, `main.tf`, `outputs.tf`, `status.py`, `AGENTS.md`, `RUNBOOK.md`, and `PRACTITIONERS_GUIDE.md`
- **ID**: `DOC-05`
- **Category**: `Documentation`
- **Severity**: `High`
- **Exact File Path**:
  - `./terraform.tfvars.example` (Lines `8`, `81–94`)
  - `./variables.tf` (Lines `44–48`, `215–227`)
  - `./main.tf` (Lines `442–466`)
  - `./outputs.tf` (Lines `143–164`)
  - `./scripts/status.py` (Lines `907–916`)
  - `./AGENTS.md` (Lines `15`, `22`)
  - `./RUNBOOK.md` (Line `206`)
  - `./PRACTITIONERS_GUIDE.md` (Lines `235–266`)
  - `./scripts/test_red.py` (Lines `1739–1752`)
- **Evidence Quote / Snippet**:
  - `./variables.tf` (lines `44–48` and `215–227`):
    ```hcl
    variable "workspace_admin_email" {
      type        = string
      description = "The email address of a Google Workspace Administrator (optional)"
      default     = null
    }
    ```
    ```hcl
    variable "people_directory_config" {
      type = object({
        data_source             = optional(string, "native_cloud_identity")
        collection_id           = optional(string, "people-directory-collection")
        display_name            = optional(string, "Google People Directory")
        include_suspended_users = optional(bool, false)
        org_units_include       = optional(list(string), []) # Target specific OUs (e.g. /Employees)
        custom_schemas_include  = optional(list(string), []) # Include custom employee attributes
        refresh_interval        = optional(string, "86400s") # Daily synchronization
        sync_mode               = optional(string, "PERIODIC")
        entities                = optional(list(string), ["users"])
        auto_run_disabled       = optional(bool, false)
      })
    ```
  - `./main.tf` (lines `442–466`):
    ```hcl
          env_key             = env_key
          connector           = "people_directory"
          data_source         = local.effective_people_directory_data_source
          data_source_version = null
          display_name        = coalesce(var.people_directory_config.display_name, "Google People Directory")
          collection_id       = coalesce(var.people_directory_config.collection_id, "people-directory-collection")
          project_id          = google_project.projects[env_key].project_id
          entities = [
            {
              entity_name = "users"
              params      = length(local.people_directory_entity_params) > 0 ? jsonencode(local.people_directory_entity_params) : null
            }
          ]
          connector_modes              = ["DATA_INGESTION"]
          sync_mode                    = "PERIODIC"
          refresh_interval             = coalesce(var.people_directory_config.refresh_interval, "86400s")
          incremental_refresh_interval = null
          static_ip_enabled            = false
          auto_run_disabled            = coalesce(var.people_directory_config.auto_run_disabled, false)
          incremental_sync_disabled    = false
          instance_uri                 = ""
          params = {
            "impersonated_user_email_address" = var.workspace_admin_email
            "super_admin_service_account"     = "service-${google_project.projects[env_key].number}@gcp-sa-discoveryengine.iam.gserviceaccount.com"
          }
    ```
  - `./scripts/status.py` (lines `907–916`):
    ```python
                    "data_source": people_cfg.get("data_source", "google_people_directory"),
                    "sync_mode": people_cfg.get("sync_mode", "INCREMENTAL"),
                    "refresh_interval": people_cfg.get("refresh_interval", "86400s"),
                    "entities": people_cfg.get("entities", ["user_profile", "job_architecture", "reporting_hierarchy", "location_contact", "custom_attributes"]),
                    "admin_console_url": "https://admin.google.com/ac/owl/domainwidedelegation",
                    "required_scopes": [
                        "https://www.googleapis.com/auth/admin.directory.user.readonly",
                        "https://www.googleapis.com/auth/admin.directory.orgunit.readonly",
                        "https://www.googleapis.com/auth/admin.directory.userschema.readonly"
                    ],
    ```
  - `./RUNBOOK.md` (line `206`):
    ```markdown
    | **Google People Directory** | `DATA_INGESTION` (Incremental) | [Google Directory API Guide](https://developers.google.com/admin-sdk/directory/v1/guides)<br/>[Cloud Identity Docs](https://cloud.google.com/identity/docs/) | [Workspace DWD Console](https://admin.google.com/ac/owl/domainwidedelegation) | Google Workspace Super Admin<br/>Service Agent DWD (0 additional credentials) |
    ```
- **Problem Description**:
  1. **Schema & Scope Mismatch**: `terraform.tfvars.example:84–94`, `scripts/status.py:907–916`, and `outputs.tf:149` specify `data_source = "google_people_directory"`, `sync_mode = "INCREMENTAL"`, and 5 entities (`["user_profile", "job_architecture", "reporting_hierarchy", "location_contact", "custom_attributes"]`), and `status.py:912–916` lists only 3 scopes (omitting `https://www.googleapis.com/auth/directory.readonly`, which is in `outputs.tf:155–160` and `main.tf:488`). However, `variables.tf:215–227` and `main.tf:442–466` use `data_source = "native_cloud_identity"`, `entities = ["users"]`, and `sync_mode = "PERIODIC"`. Note that `scripts/test_red.py:1744` currently asserts `self.assertIn("google_people_directory", content)` against `terraform.tfvars.example`.
  2. **`AGENTS.md` Blanket Ban on `DATA_INGESTION` & `RUNBOOK.md` Incremental Label**: `AGENTS.md:15, 22` states `MUST: Provision all data connectors (Workspace and third-party) exclusively in FEDERATED mode` and `MUST NOT: Provision DATA_INGESTION connectors`, without documenting the `native_cloud_identity` exception explained in `PRACTITIONERS_GUIDE.md:241`. Meanwhile, `RUNBOOK.md:206` parenthetically says `DATA_INGESTION (Incremental)` even though `main.tf:456` sets `sync_mode = "PERIODIC"`.
  3. **Undocumented Mandatory `workspace_admin_email`**: `main.tf:464` passes `"impersonated_user_email_address" = var.workspace_admin_email` to the `native_cloud_identity` connector, which fails in GCP if `workspace_admin_email` is `null` or `""`. Yet `variables.tf:46` (`"(optional)"`), `terraform.tfvars.example:8`, `RUNBOOK.md:206` (`"0 additional credentials"`), and `PRACTITIONERS_GUIDE.md:239, 263` (`"Zero new credentials"`, `[Optional]`) treat it as optional.
- **Concrete Actionable Improvement**:
  1. Align `terraform.tfvars.example:84–94`, `outputs.tf:149–152`, `scripts/status.py:907–916` (including adding `https://www.googleapis.com/auth/directory.readonly`), and `scripts/test_red.py:1739–1752` in lockstep to `data_source = "native_cloud_identity"`, `sync_mode = "PERIODIC"`, and `entities = ["users"]`.
  2. Update `AGENTS.md:15, 22` to carve out `native_cloud_identity` (`People Directory`) as the sole `DATA_INGESTION` (`PERIODIC`) exception because the Discovery Engine API only supports `DATA_INGESTION` for `native_cloud_identity`, and update `RUNBOOK.md:206` from `DATA_INGESTION (Incremental)` to `DATA_INGESTION (Periodic)`.
  3. Document in `variables.tf:44–48`, `terraform.tfvars.example:8`, `RUNBOOK.md:203–211`, and `PRACTITIONERS_GUIDE.md:239–266` that `workspace_admin_email` is required (`impersonated_user_email_address`) when `enable_people_directory_connector = true`.

---

#### `DOC-06`: `scripts/configure.py` CLI Help, `CONNECTOR_OPTIONS`, `VARIABLE_METADATA`, and `make check-inputs` Lookup Guides Omit `confluence` and `slack`
- **ID**: `DOC-06`
- **Category**: `Documentation`
- **Severity**: `High`
- **Exact File Path**:
  - `./scripts/configure.py` (Lines `38–91`, `102–180`, `357–446`, `586–599`, `951–954`, `1037–1041`, `1094–1099`)
- **Evidence Quote / Snippet**:
  - `./scripts/configure.py` (lines `951–954` and `1037–1041`):
    ```python
        parser.add_argument("--check", action="store_true", help="Audit variables against planned connectors.")
        parser.add_argument("--json", action="store_true", help="Output audit or operation result in JSON format.")
        parser.add_argument("--apply-json", help="JSON string containing configuration to apply non-interactively.")
        parser.add_argument("--connectors", help="Comma-separated list of planned connectors (workspace,jira,people_directory).")
    ```
    ```python
                valid_set = {"workspace", "jira", "people_directory"}
                for c in planned:
                    if c not in valid_set:
                        print(f"Error: Invalid connector '{c}'. Allowed: 'workspace', 'jira', 'people_directory'", file=sys.stderr)
                        sys.exit(1)
    ```
  - `./scripts/configure.py` (lines `586–599`):
    ```python
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
    ```
  - `./scripts/configure.py` (lines `1094–1099`):
    ```python
        print(f"[SUCCESS] Configuration saved to {tfvars_path}:")
        print(f"  • planned_connectors               = {json.dumps(chosen_connectors)}")
        print(f"  • enable_connectors                = false (Stage 0 safety)")
        print(f"  • enable_jira_connector            = false (Stage 0 safety)")
        print(f"  • enable_confluence_connector      = false (Stage 0 safety)")
        print(f"  • enable_people_directory_connector = false (Stage 0 safety)")
    ```
- **Problem Description**:
  `AGENTS.md:25–30, 56` and `RUNBOOK.md:45–59` direct operators and agents to run `make configure` and `make check-inputs` (`scripts/configure.py --check`) for interactive connector onboarding and step-by-step variable lookup guides. However:
  1. `scripts/configure.py:954` and `1037–1041` hardcode `valid_set = {"workspace", "jira", "people_directory"}`, rejecting both `confluence` and `slack` with `Error: Invalid connector 'confluence'. Allowed: 'workspace', 'jira', 'people_directory'`.
  2. `CONNECTOR_OPTIONS` (`scripts/configure.py:38–91`) includes `workspace`, `jira`, `confluence`, and `people_directory`, but omits `slack`, and Mode B wizard summary (`lines 1094–1099`) omits `enable_slack_connector = false (Stage 0 safety)`.
  3. `VARIABLE_METADATA` (`scripts/configure.py:102–180`), `audit_inputs` (`scripts/configure.py:357–446`), and `print_boxed_help` (`scripts/configure.py:586–615`) only define lookup guides for the 5 foundation variables plus Jira and People Directory, omitting `confluence_config.instance_uri`, `TF_VAR_confluence_auth`, `slack_config.instance_uri`, `TF_VAR_slack_auth`, and `workspace_admin_email` (when `people_directory` is selected).
- **Concrete Actionable Improvement**:
  1. Add `"slack"` to `CONNECTOR_OPTIONS` (`scripts/configure.py:38–91`) and derive `valid_set = {opt["value"] for opt in CONNECTOR_OPTIONS}` at line `1037` (and update `--connectors` help text at line `954` and wizard output at lines `1094–1099`).
  2. Add `VARIABLE_METADATA` entries, `audit_inputs` checks (`scripts/configure.py:102–180, 357–446`), and `print_boxed_help` sections (`scripts/configure.py:586–615`) for Confluence, Slack, and conditional `workspace_admin_email` when `"people_directory"` is selected.

---

#### `DOC-07`: `docs/CONNECTORS_ROADMAP.md` and `README.md` Out of Sync with Shipped Slack (`v3` Federated) and People Directory Connectors
- **ID**: `DOC-07`
- **Category**: `Documentation`
- **Severity**: `Medium`
- **Exact File Path**:
  - `./docs/CONNECTORS_ROADMAP.md` (Lines `11–19`, `32–36`)
  - `./README.md` (Lines `35–38`, `44–80`, `179–181`, `232–281`)
- **Evidence Quote / Snippet**:
  - `./docs/CONNECTORS_ROADMAP.md` (lines `11–18` and `32–36`):
    ```markdown
    | Priority | Connector | Target System | Ingestion Scope / Entities | Auth Architecture | Target Release | Status |
    | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
    | **Current** | **Google Workspace** | Google Workspace | Gmail, Calendar, Drive, Chat | Domain-Wide Delegation (DWD) | `v1.0.0` | 🟢 **GA (Shipped)** |
    | **Current** | **Atlassian Jira** | Jira Cloud / Data Center | Projects, Issues, Comments, Attachments, Worklogs | OAuth 2.0 (3LO) / API Token | `v1.1.0` | 🟢 **GA (Shipped)** |
    | **Current** | **People Directory** | Google Cloud Identity / Workspace | User Profiles, Org Chart, Manager Hierarchy, Offices | Discovery Engine DWD SA | `v1.2.0` | 🟢 **GA (Shipped)** |
    | **Current** | **Atlassian Confluence** | Confluence Cloud / DC | Spaces, Pages, Blogposts, Attachments, Comments (Federated Cloud v4 / DC v1) | OAuth 2.0 (3LO) / DC Basic Auth / Jira Fallback | `v1.3.0` | 🟢 **GA (Shipped)** |
    | **P2 (Med-High)** | **Slack Enterprise** | Slack Enterprise Grid | Channels, Messages, Threads, Canvases, Files | Bot User OAuth (`xoxb-`) | `v1.4.0` | 📋 **Accepted / Backlog** |
    | **P3 (Medium)** | **HubSpot CRM** | HubSpot Cloud | Contacts, Companies, Deals, Tickets, Engagements | Private App Token / OAuth | `v1.5.0` | 📋 **Accepted / Backlog** |
    ```
    ```markdown
    ### 2. [P2] Slack Enterprise Connector
    - **Repository Issue:** [.github/issues/02_slack_connector.md](../.github/issues/02_slack_connector.md)
    - **Objective:** Index conversational team chat, message threads, channel canvases, and shared files.
    - **Privacy Controls:** Strict channel inclusion/exclusion filters with user-account email mapping to Google Cloud Identity.
    - **Collection ID:** `slack-collection`
    ```
  - `./README.md` (lines `35–38` and `180–181`):
    ```markdown
    - **Unified Intranet Search App & Governed Assistant** (`google_discovery_engine_search_engine`, `google_discovery_engine_assistant`).
    - **Automated Seat Distribution & Verification** tooling via `Makefile`.
    - **Low-Code Marketing Asset Pack (`<= 3` Items):** Ready-to-import [Gemini Enterprise marketing catalog](catalog/marketing/README.md) pairing 2 Agent Designer blueprints (**Imagen** `1:1`/`16:9`/`9:16` visuals + **Veo** short-form video) with 1 shared `SKILL.md` brand governance package.
    - **Enterprise Connectors Roadmap:** Prioritized pipeline tracking [Slack (P2), HubSpot (P3), and People Directory (P4)](docs/CONNECTORS_ROADMAP.md).
    ```
    ```hcl
    # Planned enterprise connectors (workspace, jira, people_directory)
    planned_connectors    = ["workspace"]
    ```
- **Problem Description**:
  1. `docs/CONNECTORS_ROADMAP.md:17, 32–36` still marks **Slack Enterprise** as `📋 **Accepted / Backlog**` (`v1.4.0`, `Bot User OAuth (xoxb-)`, `Channels, Messages, Threads, Canvases, Files`), even though Slack v3 Federated + MCP Actions (`conversation`, `message`, `file`) is implemented in `main.tf:331–422`, `outputs.tf:166–209`, `scripts/status.py:846–891`, `AGENTS.md:39, 80–85`, `RUNBOOK.md:171, 226`, and `PRACTITIONERS_GUIDE.md:219–231`.
  2. `README.md:38` still describes Slack (`P2`) and People Directory (`P4`) as unshipped roadmap items (contradicting `docs/CONNECTORS_ROADMAP.md:15`, which already marks People Directory as `🟢 **GA (Shipped)**`), omits Slack and People Directory from the Mermaid architecture diagram (`README.md:44–80`), omits `"confluence"` and `"slack"` from the `planned_connectors` comment (`README.md:180`), and omits `.github/issues/05_interactive_connector_onboarding.md` and `PRACTITIONERS_GUIDE.md` from the File Structure tree (`README.md:232–281`).
- **Concrete Actionable Improvement**:
  1. Update `docs/CONNECTORS_ROADMAP.md:17, 32–36` to mark **Slack Enterprise** as `🟢 **GA (Shipped)**` with `v3` `FEDERATED` + `ACTIONS` (`slack-federated-collection`), `OAUTH` / `BOT_TOKEN` / `USER_TOKEN` / `API_TOKEN`, and entities `conversation`, `message`, `file`.
  2. Update `README.md:16–38, 44–80, 180–181, 232–281` to include Slack Enterprise and People Directory as shipped connectors (leaving HubSpot `P3` as planned), include all 5 options in `planned_connectors`, and add `PRACTITIONERS_GUIDE.md` and `05_interactive_connector_onboarding.md` to the File Structure tree.

---

#### `DOC-08`: `README.md` Bootstrap `gcloud services enable` Command Omits `serviceusage.googleapis.com` Required by `make dwd-checklist`
- **ID**: `DOC-08`
- **Category**: `Documentation`
- **Severity**: `Medium`
- **Exact File Path**:
  - `./README.md` (Lines `127–136`)
  - `./PRACTITIONERS_GUIDE.md` (Lines `114–124`)
  - `./scripts/status.py` (Lines `738–750`)
- **Evidence Quote / Snippet**:
  - `./README.md` (lines `127–136`):
    ````markdown
         ```bash
         gcloud services enable \
           cloudbilling.googleapis.com \
           cloudresourcemanager.googleapis.com \
           cloudidentity.googleapis.com \
           discoveryengine.googleapis.com \
           iam.googleapis.com \
           compute.googleapis.com \
           --project=<BILLING_PROJECT_ID>
         ```
    ````
  - `./PRACTITIONERS_GUIDE.md` (lines `114–124`):
    ````markdown
    ```bash
    gcloud services enable \
      cloudbilling.googleapis.com \
      cloudresourcemanager.googleapis.com \
      cloudidentity.googleapis.com \
      discoveryengine.googleapis.com \
      iam.googleapis.com \
      compute.googleapis.com \
      serviceusage.googleapis.com \
      --project=<BILLING_PROJECT_ID>
    ```
    ````
  - `./scripts/status.py` (lines `738–750`):
    ```python
                    url = f"https://serviceusage.googleapis.com/v1beta1/projects/{pnum}/services/discoveryengine.googleapis.com:generateServiceIdentity"
                    req = urllib.request.Request(
                        url,
                        data=b"{}",
                        method="POST",
                        headers={
                            "Authorization": f"Bearer {tok}",
                            "x-goog-user-project": quota_proj or pid or pnum,
                            "Content-Type": "application/json",
                        },
                    )
                    resp = json.loads(urllib.request.urlopen(req).read().decode())
                    uid = resp.get("response", {}).get("uniqueId")
    ```
- **Problem Description**:
  `PRACTITIONERS_GUIDE.md:122` includes `serviceusage.googleapis.com` in the bootstrap `gcloud services enable` command, whereas `README.md:127–136` omits it (and `main.tf:43–53` `base_services` also omits `serviceusage.googleapis.com`). When `make dwd-checklist` runs `scripts/status.py:738–754`, it calls `serviceusage.googleapis.com/v1beta1/projects/{pnum}/services/discoveryengine.googleapis.com:generateServiceIdentity` inside a `try ... except Exception: pass` block; if `serviceusage.googleapis.com` is not enabled on the quota project, the call fails silently and `client_id` (the mandatory 21-digit numeric DWD Client ID) is omitted from the checklist output.
- **Concrete Actionable Improvement**:
  Add `serviceusage.googleapis.com \` to the `gcloud services enable` block in `README.md:127–136` (matching `PRACTITIONERS_GUIDE.md:122`), and add `serviceusage.googleapis.com` and `cloudresourcemanager.googleapis.com` to `local.base_services` in `main.tf:43–53`.

---

#### `DOC-09`: `bootstrap.sh` Executes Unguarded `terraform apply` and Prints Legacy `dwd_checklist` Instructions Bypassing `Makefile` and `plan_guard.py`
- **ID**: `DOC-09`
- **Category**: `Documentation`
- **Severity**: `Medium`
- **Exact File Path**:
  - `./bootstrap.sh` (Lines `41–56`)
  - `./outputs.tf` (Lines `51–56`)
  - `./AGENTS.md` (Lines `8–19`, `58–63`)
  - `./RUNBOOK.md` (Lines `99–111`, `135–166`)
- **Evidence Quote / Snippet**:
  - `./bootstrap.sh` (lines `41–56`):
    ```bash
    terraform init
    terraform apply -var="sa_email=${SA_EMAIL}" -var="billing_project=${BOOTSTRAP_PROJECT}"

    echo ""
    echo "=========================================================================="
    echo " NEXT STEPS: Workspace Admin Domain-Wide Delegation (DWD)"
    echo "=========================================================================="
    echo "1. Run the following command to retrieve the DWD authorization checklist:"
    echo "   terraform output dwd_checklist"
    echo "2. Authorize each environment's Discovery Engine service agent in the Admin Console:"
    echo "   https://admin.google.com/ac/owl/domainwidedelegation"
    echo "3. After authorization, deploy Workspace connectors & Gemini Enterprise apps:"
    echo "   terraform apply -var=\"enable_connectors=true\""
    echo "4. Distribute seat licenses to projects:"
    echo "   python3 scripts/allocate_licenses.py --distribute"
    echo "5. Verify the deployment:"
    ```
  - `./outputs.tf` (lines `51–56`):
    ```hcl
          admin_console_url   = "https://admin.google.com/ac/owl/domainwidedelegation"
          oauth_scopes        = local.dwd_scopes
          oauth_scopes_csv    = join(",", local.dwd_scopes)
          action_instructions = "Add DWD API Client in Google Workspace Admin Console using service_agent_email as Client ID with oauth_scopes_csv."
        }
      }
    ```
- **Problem Description**:
  `README.md:148–153` and `PRACTITIONERS_GUIDE.md:107` offer `./bootstrap.sh` as an automated bootstrap alternative. However, `bootstrap.sh:42` executes an unguarded `terraform apply` without `-var="enable_connectors=false"` (or the third-party connector disable flags) and without running `scripts/plan_guard.py`. Then, `bootstrap.sh:48–55` instructs the operator to run `terraform output dwd_checklist` (where `outputs.tf:54` misleadingly tells the admin to add the API client `using service_agent_email as Client ID` instead of the 21-digit numeric `uniqueId` required by Google Workspace Admin Console and documented in `AGENTS.md:61` and `RUNBOOK.md:149`) and raw `terraform apply -var="enable_connectors=true"` instead of `make dwd-checklist` and `make enable-connectors`.
- **Concrete Actionable Improvement**:
  1. Update `bootstrap.sh:41–58` to invoke `make plan-foundation` and `make apply-foundation` (passing `TF_VAR_sa_email` and `TF_VAR_billing_project`), and update its post-Stage-1 instructions to `make dwd-checklist`, `make enable-connectors && make plan-connectors && make apply-connectors`, `make licenses`, and `make verify`.
  2. Update `outputs.tf:54` so `dwd_checklist.action_instructions` instructs using the **21-digit numeric Client ID (`uniqueId`) from `make dwd-checklist`** rather than `service_agent_email`.

---

#### `DOC-10`: `RUNBOOK.md` Stage 1 Checklist Claims Cloud Identity Admin Group (`<customer_id>-<env>-admins@<domain>`) Is Created When `main.tf` Only Creates the Users Group
- **ID**: `DOC-10`
- **Category**: `Documentation`
- **Severity**: `Medium`
- **Exact File Path**:
  - `./RUNBOOK.md` (Lines `127–132`)
  - `./main.tf` (Lines `570–585`)
  - `./outputs.tf` (Lines `11–14`)
- **Evidence Quote / Snippet**:
  - `./RUNBOOK.md` (lines `127–132`):
    ```markdown
    **Checklist:**
    - [ ] `make plan-foundation` generated `.plans/foundation.tfplan` with 0 deletes/replaces
    - [ ] Foundation resources successfully applied across all environments
    - [ ] Discovery Engine service agent identities created (`service-<PROJECT_NUMBER>@gcp-sa-discoveryengine.iam.gserviceaccount.com`)
    - [ ] Cloud Identity Admin & User Groups created (`<customer_id>-<env>-admins@<domain>` and `<customer_id>-<env>-users@<domain>`)
    - [ ] Location IdP configured to `GSUITE`
    ```
  - `./main.tf` (lines `570–585`):
    ```hcl
    # 3. Provision Cloud Identity User Groups
    resource "google_cloud_identity_group" "users" {
      for_each     = local.environments
      display_name = "${var.customer_name} (${each.value.display_name}) Users"
      parent       = "customers/${var.workspace_customer_id}"

      group_key {
        id = "${var.customer_id}-${each.key}-users@${var.company_domain}"
      }

      labels = {
        "cloudidentity.googleapis.com/groups.discussion_forum" = ""
      }

      depends_on = [google_project_service.services]
    }
    ```
- **Problem Description**:
  `RUNBOOK.md:131` instructs operators and agents verifying Stage 1 (`foundation_apply`) to check that both `<customer_id>-<env>-admins@<domain>` and `<customer_id>-<env>-users@<domain>` Cloud Identity groups were created. However, `main.tf:570–585` only defines `resource "google_cloud_identity_group" "users"` (`<customer_id>-<env>-users@<domain>`) and `outputs.tf:11–14` only outputs `workspace_user_groups`. No `-admins` group resource exists in the codebase.
- **Concrete Actionable Improvement**:
  Update `RUNBOOK.md:131` to read:
  `- [ ] Cloud Identity User Groups created (<customer_id>-<env>-users@<domain>)`

---

#### `DOC-11`: Stale Root Handoff Artifacts (`PROJECT.md`, `TEST_READY.md`), Outdated Test/Template Counts in `PRACTITIONERS_GUIDE.md`, and Missing `PRACTITIONERS_GUIDE.md` Links in `README.md` & `AGENTS.md`
- **ID**: `DOC-11`
- **Category**: `Documentation`
- **Severity**: `Medium`
- **Exact File Path**:
  - `./PROJECT.md` (Lines `47–50`)
  - `./TEST_READY.md` (Lines `24–28`)
  - `./PRACTITIONERS_GUIDE.md` (Lines `323`, `473–477`)
  - `./AGENTS.md` (Lines `52–109`, `128–137`)
  - `./README.md` (Lines `230–281`)
- **Evidence Quote / Snippet**:
  - `./PROJECT.md` (lines `47–50`):
    ```markdown
    | 20 | Agent Protocol & Template Update | Update `AGENTS.md` with Stage 0 combo-box protocol and hand-off templates, strictly maintaining `<= 150` lines | M3 | R5 |
    | 21 | Readme & Practitioner Guide Docs | Update `README.md` and `PRACTITIONERS_GUIDE.md` with new targets, flags, and workflow | M3 | R5 |
    | 22 | E2E Test Suite (Tiers 1-4) | Comprehensive unit and integration test coverage in `scripts/test_red.py` | M_E2E | Verification |
    | 23 | Final Integrated Verification | Pass `make test` (46 existing + all new unit tests, `terraform fmt -check`, `terraform validate`, 0 leaks) | M_FINAL | AC 54-65 |
    ```
  - `./TEST_READY.md` (lines `24–28`):
    ```markdown
    ### Current Status
    - **Total Tests:** 69 (46 baseline + 23 new test cases)
    - **Total Classes:** 12 `unittest.TestCase` classes
    - **Execution Time:** ~1.0s
    - **Pass Rate:** 100% (69 passed, 0 failed, 0 errors, 0 skipped)
    ```
  - `./PRACTITIONERS_GUIDE.md` (lines `323` and `473–477`):
    ```markdown
    | `AGENTS.md` & `.agent/workflows/deploy.md` | Agent Protocol | Rules of engagement, exit-code loop, and copy-paste human escalation templates (`dwd`, `jira`, `slack`, `permissions`, `subscription`, `state_mismatch`, `identity`) for AI agents. |
    ```
    ```markdown
    `make test` executes `python3 scripts/test_red.py`, `terraform fmt -check`, and `terraform validate`. The 46 unit and contract tests in `test_red.py` enforce:
    - **Negative & Adversarial API Handling:** Missing/malformed JSON configs, project number mismatches, insufficient billing pool capacity, and `--dry-run` zero-mutation guarantees in `allocate_licenses.py`.
    - **Plan Guard Enforcement:** Rejection of `["delete"]`, `["delete", "create"]`, and `["create", "delete"]` plans, and safe handling of `create`/`update`/`no-op`/`local_file`.
    - **State Machine & Connector Determinism:** All phase transitions (`Stage 0` through `Stage 5`), Workspace, Jira-only, Slack-only, and multi-connector gating, `v3` Slack Federated + MCP Actions defaults, and foreign state mismatch detection in `status.py`.
    - **Documentation & Agent Contracts:** Every `## Stage` section in `RUNBOOK.md` must contain all 5 mandatory headings (`**Owner:**`, `**Preconditions (machine-checkable):**`, `**Do:**`, `**Done when:**`, `**If it fails:**`); `AGENTS.md` must remain `<= 150` lines and include all 7 hand-off templates (`dwd`, `jira`, `slack`, `permissions`, `subscription`, `state_mismatch`, `identity`); all relative links across `README.md`, `RUNBOOK.md`, `AGENTS.md`, `GEMINI.md`, `PRACTITIONERS_GUIDE.md`, and `docs/CONNECTORS_ROADMAP.md` must resolve; and `TestDataScrubbing` scans `git ls-files` to guarantee zero leaked customer identifiers or real billing/subscription IDs.
    ```
  - `./AGENTS.md` (lines `128–137`):
    ```markdown
    ## Repository Map
    - `assets/`: Vector SVGs (`prism-banner.svg`, `prism-logo.svg`, `prism-icon.svg`) and high-res brand artwork.
    - `Makefile`: Unified command surface (`make status`, `make plan-*`, `make apply-*`).
    - `RUNBOOK.md`: Complete human and agent deployment instructions.
    - `main.tf`, `variables.tf`, `outputs.tf`: Core Terraform configuration.
    - `scripts/configure.py`: Interactive connector onboarding wizard and variable audit engine.
    - `scripts/status.py`: Live phase detection engine.
    - `scripts/plan_guard.py`: Destructive change guard for `.tfplan`.
    - `scripts/allocate_licenses.py`: Seat distribution and verification tool.
    - `scripts/verify.py`: Post-deployment validation script.
    ```
- **Problem Description**:
  1. `PROJECT.md` and `TEST_READY.md` are point-in-time branch handoff artifacts from the earlier `feature/interactive-connector-onboarding` branch (claiming `46` or `69` tests across `12` classes and `100%` pass rate), conflicting with the current repository state (`96` tests across `13` `unittest.TestCase` classes in `scripts/test_red.py`, plus `catalog/marketing/`, `scripts/package_marketing_assets.py`, and `scripts/deploy_marketing_assets.py`).
  2. `PRACTITIONERS_GUIDE.md:323, 473, 477` still claims `make test` runs `The 46 unit and contract tests` (omitting `package_marketing_assets.py --check`) and lists only 7 hand-off templates (`dwd`, `jira`, `slack`, `permissions`, `subscription`, `state_mismatch`, `identity`), omitting `inputs` and `confluence` (which are in `AGENTS.md:52–109`, bringing the total to 9 templates).
  3. Neither `README.md:230–281` (`File Structure`) nor `AGENTS.md:128–137` (`Repository Map`) references `PRACTITIONERS_GUIDE.md`, `catalog/marketing/`, `scripts/package_marketing_assets.py`, or `scripts/deploy_marketing_assets.py`.
- **Concrete Actionable Improvement**:
  1. Archive or remove `PROJECT.md` and `TEST_READY.md` (or replace `PROJECT.md` with a canonical architecture & module layout reference).
  2. Update `PRACTITIONERS_GUIDE.md:323, 473–477` to reflect the 96 unit/contract tests, `package_marketing_assets.py --check`, and all 9 hand-off templates (`inputs`, `dwd`, `jira`, `confluence`, `slack`, `permissions`, `subscription`, `state_mismatch`, `identity`).
  3. Add `PRACTITIONERS_GUIDE.md`, `catalog/marketing/`, `scripts/package_marketing_assets.py`, and `scripts/deploy_marketing_assets.py` to `README.md` (`File Structure`) and `AGENTS.md` (`Repository Map`).

---

#### `DOC-12`: Minor Documentation & Issue Template Drift (`Makefile` Banner, `verify.py` Warning Hint, `.github/issues/01_confluence_connector.md` & `02_slack_connector.md`, and Missing `docs/adr/`)
- **ID**: `DOC-12`
- **Category**: `Documentation`
- **Severity**: `Low`
- **Exact File Path**:
  - `./Makefile` (Lines `8–10`)
  - `./scripts/verify.py` (Lines `135–136`)
  - `./.github/issues/01_confluence_connector.md` (Lines `26–29`, `46–50`)
  - `./.github/issues/02_slack_connector.md` (Lines `42–53`, `74–78`)
- **Evidence Quote / Snippet**:
  - `./Makefile` (lines `8–10`):
    ```makefile
    	@echo "  ═══╬─╱  ╲──✦   P R I S M   │ Gemini Enterprise Provisioning Engine"
    	@echo "  ═══╝╱____╲     v1.0        │ Workspace · Jira · Confluence · Identity · Licensing"
    	@echo ""
    ```
  - `./scripts/verify.py` (lines `135–136`):
    ```python
        if not found_connectors:
            results.append(("Data Connectors", "WARN", "No active data connectors found (enable_connectors, enable_jira_connector, enable_confluence_connector, or enable_people_directory_connector may be false)"))
    ```
  - `./.github/issues/02_slack_connector.md` (lines `42–53` and `74–78`):
    ```hcl
    variable "slack_config" {
      description = "Configuration parameters for Slack ingestion"
      type = object({
        team_id                      = optional(string, "")
        channels_include             = optional(list(string), []) # Whitelist channel IDs
        channels_exclude             = optional(list(string), []) # Blacklist channel IDs
        include_private_channels     = optional(bool, false)
        entities                     = optional(list(string), ["channel", "message", "thread", "canvas", "file"])
        refresh_interval             = optional(string, "43200s") # 12-hour full crawl
        incremental_refresh_interval = optional(string, "1800s")  # 30-min incremental sync
        sync_mode                    = optional(string, "INCREMENTAL")
      })
    ```
    ```markdown
    ### Acceptance Criteria
    - [ ] Variables defined in `variables.tf` and exported in `outputs.tf`.
    - [ ] Ingestion schema properly formats conversational threads and parent-child message relationships.
    - [ ] Privacy controls: Whitelist validation and automatic exclusion of direct messages (DMs/MPDMs) unless explicitly opted in.
    - [ ] Terraform plan successfully verifies connector metadata and Secret Manager bindings.
    ```
- **Problem Description**:
  1. `Makefile:9` (`Workspace · Jira · Confluence · Identity · Licensing`) and `scripts/verify.py:136` omit Slack (`enable_slack_connector`).
  2. `.github/issues/01_confluence_connector.md:26–29, 46–50` and `.github/issues/02_slack_connector.md:42–53, 74–78` still show pre-implementation `INCREMENTAL` ingestion schemas (`["spaces", "pages", ...]`, `["channel", "message", "thread", "canvas", "file"]`) and unchecked acceptance criteria checkboxes `[ ]` (unlike `.github/issues/04_people_directory_connector.md:62–66` and `05_interactive_connector_onboarding.md:72–78`, which have `[x]`).
  3. `docs/` contains only `CONNECTORS_ROADMAP.md` and lacks an `adr/` directory for Architecture Decision Records (such as Federated-First vs. `native_cloud_identity` `DATA_INGESTION`, Two-Stage Apply for DWD, and Billing Pool Seat Distribution).
- **Concrete Actionable Improvement**:
  1. Update `Makefile:9` and `scripts/verify.py:136` to include Slack (`enable_slack_connector`).
  2. Update `.github/issues/01_confluence_connector.md` and `.github/issues/02_slack_connector.md` to reflect the shipped `v3`/`v4` `FEDERATED` + `ACTIONS` schemas and mark completed items `[x]`.
  3. Add `docs/adr/` with concise Architecture Decision Records for key platform invariants.


---

## Part 4: Production Readiness & Engineering Planning Roadmap (`RM-01` – `RM-12`)

### Roadmap Overview & Phasing Summary

| ID | Phase | Priority | Effort | Title | Findings Addressed |
| :--- | :--- | :---: | :---: | :--- | :--- |
| **RM-01** | **Phase 0: Immediate Unblockers** | `P0` | `S` (0.5d) | Restore `variables.tf`, `terraform.tfvars.example`, `Makefile`, and `configure.py` Slack & Confluence Parity | `CODE-01`, `CODE-02`, `DEPLOY-01`, `DEPLOY-02`, `DEPLOY-03`, `DOC-01`, `DOC-02`, `DOC-06` |
| **RM-02** | **Phase 0: Immediate Unblockers** | `P0` | `S` (0.5d) | Reconcile All Documentation, Runbooks, Handoff Artifacts & `bootstrap.sh` with Ground-Truth Implementation | `DOC-01`–`DOC-12`, `DEPLOY-13` |
| **RM-03** | **Phase 0: Immediate Unblockers** | `P0` | `M` (1d) | Eliminate Secret Leakage in Terraform Plans & Unify `.env.*` Credential Pipeline Across `configure.py`, `status.py`, and `Makefile` | `CODE-03`, `CODE-11`, `DEPLOY-04` |
| **RM-04** | **Phase 0: Immediate Unblockers** | `P0` | `M` (1d) | Harden State Corruption Guard, Plan-to-`tfvars` Digest Binding, and Unit Test Hermeticity | `CODE-09`, `CODE-10`, `CODE-13`, `DEPLOY-09`, `DEPLOY-14` |
| **RM-05** | **Phase 1: Core Automation & Stage Gates** | `P1` | `M` (1.5d) | Close Stage 3 & Stage 4 Automation Loops (`default_assistant` Import & License Distribution -> `user_store` State Verification) | `CODE-04`, `CODE-05`, `DEPLOY-05`, `DEPLOY-06`, `DEPLOY-08`, `DEPLOY-12` |
| **RM-06** | **Phase 1: Core Automation & Stage Gates** | `P1` | `M` (1d) | Upgrade `scripts/verify.py` to Enforce `terraform.tfvars` Contracts, `INITIALIZING` Wait Polling & OAuth Token Refresh | `CODE-08`, `DEPLOY-07` |
| **RM-07** | **Phase 1: Core Automation & Stage Gates** | `P1` | `M` (1.5d) | Extract Shared `scripts/hcl_parser.py`, Implement `status.py --deep`, and Harden Stage 2/3 Readiness Checks | `CODE-06`, `CODE-07`, `CODE-10`, `DEPLOY-10`, `DEPLOY-11`, `DOC-05`, `DOC-08` |
| **RM-08** | **Phase 1: Core Automation & Stage Gates** | `P1` | `M` (1d) | Add Strict `variables.tf` Validations, Remote GCS Backend Template & CI Workflow Parity | `CODE-12`, `DEPLOY-09`, `DEPLOY-14` |
| **RM-09** | **Phase 2: Architecture & Test Modularization** | `P2` | `L` (3d) | Modularize Monolithic `main.tf` (760 Lines) into Composable Terraform Sub-Modules (`foundation`, `connectors`, `engines`, `licensing`) | `CODE-01`, `CODE-03`, `CODE-06`, `CODE-12`, `DEPLOY-08` |
| **RM-10** | **Phase 2: Architecture & Test Modularization** | `P2` | `M` (2d) | Split Monolithic `scripts/test_red.py` (2,651 Lines) into Domain Test Suites & Harden `deploy_marketing_assets.py` Hermetic Tests | `CODE-09`, `CODE-13`, `CODE-14`, `DOC-11` |
| **RM-11** | **Phase 3: Ecosystem & Catalog Expansion** | `P2` | `L` (3d) | Implement HubSpot CRM Federated Connector (`P3`) & Declarative Connector Registry Pattern | `DOC-07`, `DOC-12` |
| **RM-12** | **Phase 3: Ecosystem & Catalog Expansion** | `P2` | `M` (2d) | Expand Low-Code Agent & Skill Catalog Across Enterprise Domains & Integrate with Stage 5 Verification | `CODE-14`, `DOC-11` |

---

### Phase 0: Immediate Unblockers (Restore Validation, Green Test Suite & Secret Safety)

#### `RM-01`: Restore `variables.tf`, `terraform.tfvars.example`, `Makefile`, and `configure.py` Slack & Confluence Parity
- **Priority**: `P0` | **Effort**: `S` (0.5 day) | **Dependencies**: None
- **Findings Addressed**: `CODE-01`, `CODE-02`, `DEPLOY-01`, `DEPLOY-02`, `DEPLOY-03`, `DOC-01`, `DOC-02`, `DOC-06` (resolves `CHAL-01`, `CHAL-02`, `CHAL-04`)
- **Affected Files & Exact Symbols**:
  - `variables.tf` (`variable "planned_connectors"` at lines `79–90`; append `variable "enable_slack_connector"`, `variable "slack_auth_type"`, `variable "slack_auth"`, `variable "slack_config"` after line `302`)
  - `terraform.tfvars.example` (`planned_connectors` at line `19`; Slack block and `people_directory_config` at lines `81–94`)
  - `outputs.tf` (`people_directory_connector_readiness` at lines `143–164`)
  - `Makefile` (`.PHONY` at line `1`, `help` at lines `18–21`, `plan-foundation` at lines `45–48`, `slack-checklist` after line `63`)
  - `scripts/configure.py` (`CONNECTOR_OPTIONS` at lines `38–91`, `VARIABLE_METADATA` at lines `102–180`, `determine_stage` at lines `302–309`, `audit_inputs` at lines `357–446`, `update_tfvars` at lines `449–580`, `enable_connectors` at lines `871–944`, `--connectors` help at line `954`, `valid_set` in `main` at lines `1037–1041`, Mode B summary at lines `1094–1099`)
  - `scripts/status.py` (`get_people_checklist` at lines `894–921`)
  - `scripts/test_red.py` (`TestTerraformDefaultsContract.test_people_directory_defaults_contract` at lines `1739–1752`)
- **Implementation Specification**:
  1. **`variables.tf` Contract-Compliant Slack Declarations**:
     - Update `variable "planned_connectors"` (`variables.tf:79–90`) so `contains(["workspace", "jira", "confluence", "slack", "people_directory"], c)` is enforced.
     - Append the complete Slack variable definitions after `variables.tf:302` matching every attribute referenced in `main.tf:331–422` and every contract assertion in `scripts/test_red.py:1714–1730`:
       ```hcl
       variable "enable_slack_connector" {
         type        = bool
         description = "Whether to provision the Slack Enterprise data connector"
         default     = false
       }

       variable "slack_auth_type" {
         type        = string
         description = "Authentication type for Slack connector: OAUTH, OAUTH2, BOT_TOKEN, USER_TOKEN, or API_TOKEN"
         default     = "OAUTH"

         validation {
           condition     = contains(["OAUTH", "OAUTH2", "BOT_TOKEN", "USER_TOKEN", "API_TOKEN"], var.slack_auth_type)
           error_message = "slack_auth_type must be one of: OAUTH, OAUTH2, BOT_TOKEN, USER_TOKEN, API_TOKEN."
         }
       }

       variable "slack_auth" {
         type = object({
           bot_token     = optional(string, "")
           user_token    = optional(string, "")
           api_token     = optional(string, "")
           client_id     = optional(string, "")
           client_secret = optional(string, "")
           refresh_token = optional(string, "")
           team_id       = optional(string, "")
         })
         description = "Sensitive authentication credentials for Slack connector (supply via TF_VAR_slack_auth)"
         default     = {}
         sensitive   = true
       }

       variable "slack_config" {
         type = object({
           collection_id                = optional(string, "slack-federated-collection")
           instance_uri                 = optional(string, "")
           team_id                      = optional(string, "")
           data_source                  = optional(string, "slack")
           data_source_version          = optional(number, 3)
           connector_modes              = optional(list(string), ["FEDERATED"])
           sync_mode                    = optional(string, "PERIODIC")
           refresh_interval             = optional(string, "86400s")
           incremental_refresh_interval = optional(string, "10800s")
           static_ip_enabled            = optional(bool, false)
           auto_run_disabled            = optional(bool, false)
           incremental_sync_disabled    = optional(bool, false)
           enable_actions               = optional(bool, false)
           enabled_actions              = optional(list(string), [])
           channels_include             = optional(list(string), [])
           channels_exclude             = optional(list(string), [])
           include_private_channels     = optional(bool, true)
           include_dms                  = optional(bool, false)
           entities = optional(list(string), [
             "conversation",
             "message",
             "file"
           ])
           extra_params = optional(map(any), {})
         })
         description = "Configuration parameters for the Slack Enterprise data connector"
         default     = {}

         validation {
           condition = (
             contains(coalesce(var.slack_config.connector_modes, ["FEDERATED"]), "FEDERATED") &&
             !contains(coalesce(var.slack_config.connector_modes, ["FEDERATED"]), "DATA_INGESTION")
           )
           error_message = "Slack connector must use FEDERATED mode (connector_modes = [\"FEDERATED\"])."
         }
       }
       ```
  2. **`scripts/configure.py` Onboarding & Validation Fixes**:
     - Append the `"slack"` entry (`{"value": "slack", "label": "Slack Enterprise (Federated Search & MCP Actions)", ...}`) to `CONNECTOR_OPTIONS` (`scripts/configure.py:38–91`).
     - Replace the hardcoded `valid_set = {"workspace", "jira", "people_directory"}` at `scripts/configure.py:1037` with `valid_set = {opt["value"] for opt in CONNECTOR_OPTIONS}`.
     - Add `"enable_slack_connector"` to the Stage 0 safety guard in `determine_stage` (`configure.py:302–309`), `update_tfvars` (`configure.py:471–498, 519–530`), and `enable_connectors` (`configure.py:871–944`, alongside `enable_people_directory_connector`).
     - Add `VARIABLE_METADATA` and `audit_inputs` checks for `confluence_config.instance_uri`, `TF_VAR_confluence_auth`, `slack_config.instance_uri`, `TF_VAR_slack_auth`, and `workspace_admin_email` (when `"people_directory"` is in `planned_connectors`).
  3. **`Makefile` & `terraform.tfvars.example` Alignment**:
     - Add `slack-checklist` to `Makefile` (`.PHONY`, `help`, and target rules) and `-var="enable_slack_connector=false"` to `plan-foundation` (`Makefile:47`).
     - Add the default Slack block to `terraform.tfvars.example` and align `people_directory_config` across `terraform.tfvars.example:84–94`, `outputs.tf:149–152`, `scripts/status.py:907–916`, and `scripts/test_red.py:1739–1752` in lockstep (`data_source = "native_cloud_identity"`, `sync_mode = "PERIODIC"`, `entities = ["users"]`).
- **Verification Criteria**:
  - `terraform validate` exits `0`.
  - `PYTHONDONTWRITEBYTECODE=1 GH_TOKEN= GITHUB_TOKEN= GH_CONFIG_DIR=/tmp/empty_gh python3 -B scripts/test_red.py` passes all `96` tests (`OK`).

---

#### `RM-02`: Reconcile All Documentation, Runbooks, Handoff Artifacts & `bootstrap.sh` with Ground-Truth Implementation
- **Priority**: `P0` | **Effort**: `S` (0.5 day) | **Dependencies**: `RM-01`
- **Findings Addressed**: `DOC-01` through `DOC-12`, `DEPLOY-13`
- **Affected Files**:
  - `AGENTS.md` (lines `6`, `15`, `22`, `26`, `42`, `128–137`)
  - `.agent/workflows/deploy.md` (lines `7`, `11`)
  - `PRACTITIONERS_GUIDE.md` (lines `133–151`, `188–200`, `239–266`, `323`, `473–477`)
  - `RUNBOOK.md` (lines `131`, `203–211`)
  - `README.md` (lines `35–38`, `44–80`, `127–136`, `180`, `206–226`, `230–281`)
  - `docs/CONNECTORS_ROADMAP.md` (lines `17`, `32–36`)
  - `bootstrap.sh` (lines `41–56`) & `outputs.tf` (line `54`)
  - `PROJECT.md`, `TEST_READY.md`, `.github/issues/01_confluence_connector.md`, `.github/issues/02_slack_connector.md`
  - `scripts/test_red.py` (`TestDocumentationContracts` at lines `2166–2295`)
- **Implementation Specification**:
  1. Fix `make status --json` -> `make status ARGS="--json"` in `AGENTS.md:6, 26, 42` and `.agent/workflows/deploy.md:7, 11` (`DOC-03`).
  2. Update `PRACTITIONERS_GUIDE.md:133–151` to list all 12 DWD scopes from `main.tf:482–495`, and update `PRACTITIONERS_GUIDE.md:188–200` to show `jira-federated-collection` and `connector_modes = ["FEDERATED"]` (`DOC-04`).
  3. Update `AGENTS.md:15, 22` to document `native_cloud_identity` (`People Directory`) as the sole `DATA_INGESTION` (`PERIODIC`) exception, update `RUNBOOK.md:206` from `DATA_INGESTION (Incremental)` to `DATA_INGESTION (Periodic)`, and document `workspace_admin_email` as mandatory when `enable_people_directory_connector = true` (`DOC-05`).
  4. Update `docs/CONNECTORS_ROADMAP.md:17, 32–36` to mark **Slack Enterprise** as `🟢 GA (Shipped)`, and update `README.md` (`lines 35–38, 44–80, 127–136, 180, 206–226, 230–281`) to include `serviceusage.googleapis.com`, Slack/People Directory in the Mermaid diagram and feature bullets, `make slack-checklist` and `make licenses-list` in the Makefile table, and `PRACTITIONERS_GUIDE.md` in the File Structure (`DOC-07`, `DOC-08`, `DOC-11`).
  5. Update `bootstrap.sh:41–56` to delegate to `make plan-foundation && make apply-foundation` and `make dwd-checklist`, update `outputs.tf:54` to reference the 21-digit numeric Client ID (`uniqueId`), remove the nonexistent `<customer_id>-<env>-admins@<domain>` group from `RUNBOOK.md:131`, archive/remove stale `PROJECT.md` and `TEST_READY.md`, and update `.github/issues/01_confluence_connector.md` and `02_slack_connector.md` (`DOC-09`, `DOC-10`, `DOC-11`, `DOC-12`).
  6. Add automated contract tests in `TestDocumentationContracts` (`scripts/test_red.py`) asserting that:
     - Every `make <target>` referenced in `AGENTS.md`, `RUNBOOK.md`, `PRACTITIONERS_GUIDE.md`, `README.md`, and `scripts/status.py` exists in `Makefile`.
     - Neither `AGENTS.md` nor `.agent/workflows/deploy.md` contains `make status --json`.
     - `PRACTITIONERS_GUIDE.md` contains all 12 scopes from `main.tf` `local.dwd_scopes` and zero occurrences of `["DATA_INGESTION"]` inside Jira/Confluence/Slack tables.
- **Verification Criteria**:
  - `TestDocumentationContracts` in `scripts/test_red.py` passes with 100% doc-to-code parity.

---

#### `RM-03`: Eliminate Secret Leakage in Terraform Plans & Unify `.env.*` Credential Pipeline Across `configure.py`, `status.py`, and `Makefile`
- **Priority**: `P0` | **Effort**: `M` (1 day) | **Dependencies**: `RM-01`
- **Findings Addressed**: `CODE-03`, `CODE-11`, `DEPLOY-04`
- **Affected Files & Exact Symbols**:
  - `main.tf` (`local.effective_confluence_client_secret`, `local.effective_confluence_api_token` at lines `208–226`; `local.confluence_environment_connectors` `params` and `action_params` at lines `306–324`; `local.effective_slack_token` and `local.slack_environment_connectors` `params` and `action_params` at lines `344–348, 405–419`)
  - `scripts/configure.py` (`audit_inputs` at lines `412–433`, `update_tfvars` `.env.jira` writer at lines `567–576`, `enable_connectors` at lines `890–911`)
  - `scripts/status.py` (Stage 2 Jira/Confluence/Slack credential checks at lines `491–569`)
  - `Makefile` (`plan-connectors`, `apply-connectors` at lines `65–73`)
- **Implementation Specification**:
  1. **Remove `nonsensitive()` on Secrets in `main.tf`**:
     - In `main.tf:208–226`, compute non-sensitive boolean presence flags (`has_confluence_client_secret = nonsensitive(trimspace(try(var.confluence_auth.client_secret, "")) != "")`, etc.) and keep `local.effective_confluence_client_secret` and `local.effective_confluence_api_token` sensitive.
     - Remove `nonsensitive(...)` wrappers around `local.effective_confluence_api_token` and `local.effective_confluence_client_secret` in `local.confluence_environment_connectors` (`main.tf:308, 315, 323`) and around `var.slack_auth.client_secret` in `local.slack_environment_connectors` (`main.tf:412, 417`), matching `local.jira_environment_connectors` (`main.tf:165–181`).
  2. **Atomic `0o600` `.env.*` Creation & Shell Quoting in `scripts/configure.py`**:
     - Replace lines `567–576` of `scripts/configure.py` with a helper that writes `.env.jira`, `.env.confluence`, and `.env.slack` using `os.open(env_file_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)` and `shlex.quote(json.dumps(secret_payload))` so credentials containing `'`, `$`, or `\` cannot corrupt the shell file or be read by other local users before `os.chmod`.
  3. **Auto-Source `.env.*` in `Makefile` & Validate Confluence Credentials in `status.py` / `configure.py`**:
     - Update `plan-connectors` and `apply-connectors` in `Makefile:65–73` to source `.env.jira`, `.env.confluence`, and `.env.slack` if present (`for f in .env.jira .env.confluence .env.slack; do [ -f "$$f" ] && . "./$$f"; done`).
     - Add Confluence credential validation (`TF_VAR_confluence_auth` or fallback `TF_VAR_jira_auth` / `.env.confluence` / `.env.jira`) in `scripts/status.py:503–539` and `scripts/configure.py:902–910`.
- **Verification Criteria**:
  - `terraform plan` output with `enable_confluence_connector = true` and `enable_slack_connector = true` masks all `client_secret`, `api_token`, `bot_token`, and `user_token` values as `(sensitive value)`.
  - Unit tests in `scripts/test_red.py` verify `.env.*` `0o600` creation, `shlex.quote` round-tripping of special characters, and Stage 2 Confluence credential gating.

---

#### `RM-04`: Harden State Corruption Guard, Plan-to-`tfvars` Digest Binding, and Unit Test Hermeticity
- **Priority**: `P0` | **Effort**: `M` (1 day) | **Dependencies**: `RM-01`
- **Findings Addressed**: `CODE-09`, `CODE-10`, `CODE-13`, `DEPLOY-09`, `DEPLOY-14`
- **Affected Files & Exact Symbols**:
  - `scripts/status.py` (`parse_state` at lines `113–121`, `determine_status` at lines `268–272`)
  - `scripts/plan_guard.py` (`guard_plan` at lines `99–134`, `main` at lines `136–147`)
  - `Makefile` (`plan-foundation`, `apply-foundation`, `plan-connectors`, `apply-connectors` at lines `45–52, 65–73`)
  - `scripts/create_github_issues.sh` (`main` arg handling and auth checks at lines `24–96`)
  - `scripts/test_red.py` (`test_status_legacy_workspace_state_triggers_mismatch` at lines `406–429`, `test_git_branch_contract` at lines `2299–2311`, `test_create_github_issues_script_registration_and_args` at lines `2336–2378`)
- **Implementation Specification**:
  1. **Fail Closed on Corrupted `terraform.tfstate` in `scripts/status.py`**:
     - In `determine_status` (`scripts/status.py:268–272`), immediately check `if state and "_error" in state:` before running the foreign-project mismatch guard or Stage 1 check, returning Phase `0` (`handoff_template: "state_mismatch"`, `exit_code: 1`) with the JSON parse error from `parse_state` (`status.py:113–121`).
  2. **Bind `.plans/*.tfplan` to `terraform.tfvars` SHA-256 Digest**:
     - When `make plan-foundation` (`Makefile:45–48`) or `make plan-connectors` (`Makefile:65–68`) succeeds, record the SHA-256 hash of `terraform.tfvars` in `.plans/foundation.tfplan.sha256` / `.plans/connectors.tfplan.sha256`, and verify in `scripts/plan_guard.py:99–134` (`guard_plan`) during `make apply-*` that `terraform.tfvars` has not been modified since the plan was generated.
  3. **Make `scripts/test_red.py` 100% Hermetic**:
     - Add `--dry-run` to `scripts/create_github_issues.sh:24–96` and pass `--dry-run` (with scrubbed `GH_TOKEN=""`, `GITHUB_TOKEN=""`, `PATH` without live `gh`) in `TestBranchAndIssueContracts.test_create_github_issues_script_registration_and_args` (`scripts/test_red.py:2345–2376`).
     - Construct a synthetic legacy `legacy-*` state fixture in `self.temp_dir` inside `test_status_legacy_workspace_state_triggers_mismatch` (`scripts/test_red.py:406–429`) instead of reading `os.path.join(REPO_ROOT, "terraform.tfstate")`.
     - Relax `test_git_branch_contract` (`scripts/test_red.py:2299–2311`) to accept standard branch prefixes (`main`, `master`, `feature/*`, `fix/*`, `release/*`, or detached HEAD in CI).
- **Verification Criteria**:
  - Corrupted `terraform.tfstate` returns `exit_code == 1` (`phase == 0`).
  - Modifying `terraform.tfvars` after `make plan-foundation` causes `make apply-foundation` (`plan_guard.py`) to reject the stale plan with `exit_code == 1`.
  - `python3 -B scripts/test_red.py` passes identically regardless of ambient `GH_TOKEN`, `gh auth status`, git branch name, or presence/absence of `terraform.tfstate`.

---

### Phase 1: Core Automation & Stage Gates (Stage 3–5 Reliability)

#### `RM-05`: Close Stage 3 & Stage 4 Automation Loops (`default_assistant` Import & License Distribution -> `user_store` State Verification)
- **Priority**: `P1` | **Effort**: `M` (1.5 days) | **Dependencies**: `RM-01`, `RM-04`
- **Findings Addressed**: `CODE-04`, `CODE-05`, `DEPLOY-05`, `DEPLOY-06`, `DEPLOY-08`, `DEPLOY-12` (resolves `CHAL-03`)
- **Affected Files & Exact Symbols**:
  - `scripts/allocate_licenses.py` (`run_preflight_assertions` at lines `168–188`, `emit_tfvars` at lines `268–302`, `load_config` at lines `348–369`, `discover_billing_subscriptions` at lines `388–409`, `main` at lines `412–605`)
  - `Makefile` (`plan-connectors`, `apply-connectors`, `licenses`, `licenses-dryrun` at lines `65–79`)
  - `scripts/status.py` (Stage 4 license distribution & user store check at lines `630–684`)
  - `main.tf` (`google_discovery_engine_user_store.default` at lines `588–601`, `google_discovery_engine_search_engine.engines` at lines `676–703`, `google_discovery_engine_assistant.default` at lines `717–737`, `local_file.license_allocations` at lines `740–760`)
- **Implementation Specification**:
  1. **Unblock `allocate_licenses.py --discover` (`CODE-04`)**:
     - Update `load_config(config_file, require_subscription_id=True)` (`scripts/allocate_licenses.py:348–369`) and `main()` (`lines 432–455`) so `--discover` passes `require_subscription_id=False` and falls back to parsing `billing_account` and `project_ids` from `terraform.tfvars` / `terraform.tfstate` if `config/license_allocations.json` does not exist yet or has `"subscription_id": ""`.
  2. **Delta-Aware Preflight Seat Assertion & Partial Retraction (`CODE-05`, `DEPLOY-06`, `DEPLOY-12`)**:
     - Update `run_preflight_assertions` (`scripts/allocate_licenses.py:168–188`) to query each target project's existing active non-trial `licenseConfig` (`current_seats`) and compute `total_delta_seats = sum(max(0, int(item.get("seat_count", 0)) - current_seats) for item in allocations)`. Only raise `ValueError("Insufficient license seats...")` when `total_delta_seats > available_seats`. Skip `available_seats` assertion when only `--configure-auto-register` is invoked.
     - Add `--retract-seats <N>` (`fullRetract: False`, `retractLicenseCount: str(N)`) and automatic downsizing in `--distribute` when `current_seats > int(seats)` (`allocate_licenses.py:503–505, 571–605`).
  3. **Close the Stage 4 License Distribution -> `user_store` Terraform State Loop (`DEPLOY-05`, `CHAL-03`)**:
     - Remove the early `return` after `if args.distribute:` (`scripts/allocate_licenses.py:528`) so `--distribute` and `--configure-auto-register` can execute in a single invocation, and add `--write-tfvars` to `allocate_licenses.py` (updating `license_config_names = { ... }` in `terraform.tfvars`).
     - Update `make licenses` (`Makefile:77–78`) to run `python3 scripts/allocate_licenses.py --distribute --configure-auto-register --write-tfvars $(ARGS)`.
     - Because `resource "google_discovery_engine_user_store" "default"` (`main.tf:588–601`) uses `for_each = local.environments`, it is created in Stage 1 (`foundation_apply`) with `enable_license_auto_register = false` and `default_license_config = null`, meaning `outputs.user_store_names` (`outputs.tf:23–28`) is already non-empty from Stage 1. Therefore, update `scripts/status.py:657–684` to inspect the `google_discovery_engine_user_store.default` resource instances in `terraform.tfstate`:
       - If `tfvars.get("license_config_names")` is missing for any environment with `seat_allocations[env] > 0`, return Phase `4` (`next_action: "make licenses"`).
       - If `tfvars.get("license_config_names")` is populated in `terraform.tfvars`, check `state.get("resources", [])` for `type == "google_discovery_engine_user_store"` (`name == "default"`): if any allocated environment instance has `attributes.get("enable_license_auto_register") != True` or `attributes.get("default_license_config") != license_config_names[env]`, keep Phase `4` active with `next_action: "make plan-connectors && make apply-connectors"` so Terraform reconciles `google_discovery_engine_user_store.default` before advancing to Stage 5 (`make verify`).
  4. **Auto-Import GCP-Auto-Created `default_assistant` in Stage 3 (`DEPLOY-08`)**:
     - When `google_discovery_engine_search_engine.engines` (`main.tf:676–703`) is created with `search_add_ons = ["SEARCH_ADD_ON_LLM"]`, GCP can auto-instantiate `default_assistant`, causing `google_discovery_engine_assistant.default` (`main.tf:717–737`) to fail with HTTP `409 ALREADY_EXISTS`. Add an idempotent preflight helper invoked before `apply-connectors` that checks whether `google_discovery_engine_assistant.default["<env>"]` is absent from `terraform.tfstate` while `GET https://discoveryengine.googleapis.com/v1alpha/projects/{p}/locations/{loc}/collections/default_collection/engines/{eng}/assistants/default_assistant` returns `200`, and automatically imports it via `terraform import`.
- **Verification Criteria**:
  - `allocate_licenses.py --discover` succeeds when `subscription_id` is `""`.
  - Re-running `make licenses` when all seats are already distributed succeeds with `total_delta_seats == 0`.
  - `make status` transitions cleanly: `make licenses` -> `make plan-connectors && make apply-connectors` (reconciling `google_discovery_engine_user_store.default` in `terraform.tfstate`) -> Stage 5 (`make verify`).

---

#### `RM-06`: Upgrade `scripts/verify.py` to Enforce `terraform.tfvars` Contracts, `INITIALIZING` Wait Polling & OAuth Token Refresh
- **Priority**: `P1` | **Effort**: `M` (1 day) | **Dependencies**: `RM-01`, `RM-05`
- **Findings Addressed**: `CODE-08`, `DEPLOY-07`
- **Affected Files & Exact Symbols**:
  - `scripts/verify.py` (`make_request` at lines `59–80`, `check_data_connectors` at lines `82–138`, `check_engines_and_assistants` at lines `140–179`, `check_user_store` at lines `182–195`, `check_license_configs` at lines `198–215`, `verify_project` at lines `229–248`, `main` at lines `297–391`)
  - `scripts/allocate_licenses.py` (`make_request` at line `51`)
- **Implementation Specification**:
  1. **Poll `INITIALIZING` Connectors & Refresh Access Tokens During `--wait`**:
     - In `check_data_connectors` (`scripts/verify.py:128–133`), treat both `"CREATING"` and `"INITIALIZING"` as `"CREATING"` (or check `any(r["status"] in ("CREATING", "INITIALIZING") ...)` in `main` at line `345`) so `make verify WAIT=15m` continues polling until BAP connectors transition to `"ACTIVE"` or `"FAILED"`.
     - Inside the `while True:` polling loop (`scripts/verify.py:318–354`), refresh `token = get_access_token()` before each polling iteration so `--wait` durations exceeding token TTL do not fail with HTTP `401`.
  2. **Enforce `terraform.tfvars` Expected Resources & `expected_seats`**:
     - In `verify_project` (`scripts/verify.py:229–248`), pass `expected_seats` and the expected connector `dataSource` set derived from `terraform.tfvars` (`enable_connectors`, `workspace_connectors`, `enable_jira_connector`, `enable_confluence_connector`, `enable_slack_connector`, `enable_people_directory_connector`) into `check_data_connectors`, `check_engines_and_assistants`, `check_user_store`, and `check_license_configs`.
     - Emit `"FAIL"` (not `"WARN"`) when an enabled connector, search engine, `default_assistant`, or `licenseConfig` is missing, or when `allocated_seats < expected_seats` (`check_license_configs` at `verify.py:198–215`) or `enableLicenseAutoRegister` is `False` when `expected_seats > 0` (`check_user_store` at `verify.py:182–195`).
  3. **Add Explicit Socket Timeout to `make_request`**:
     - Add `timeout=30` to `urllib.request.urlopen(req, timeout=timeout)` in `scripts/verify.py:72` and `scripts/allocate_licenses.py:51`.
- **Verification Criteria**:
  - `verify.py` continues polling when a connector reports `state: "INITIALIZING"`, refreshes tokens per cycle, and exits `1` (`verified: false`) when expected connectors, engines, or `expected_seats` are missing.

---

#### `RM-07`: Extract Shared `scripts/hcl_parser.py`, Implement `status.py --deep`, and Harden Stage 2/3 Readiness Checks
- **Priority**: `P1` | **Effort**: `M` (1.5 days) | **Dependencies**: `RM-01`, `RM-04`
- **Findings Addressed**: `CODE-06`, `CODE-07`, `CODE-10`, `DEPLOY-10`, `DEPLOY-11`, `DOC-05`, `DOC-08`
- **Affected Files & Exact Symbols**:
  - New shared module: `scripts/hcl_parser.py`
  - `scripts/status.py` (`parse_tfvars` at lines `41–110`, `determine_status` at lines `183, 575–628, 932, 967`, `get_dwd_checklist` at lines `735–755`, `get_people_checklist` at lines `894–921`)
  - `scripts/configure.py` (`parse_tfvars` at lines `197–257`)
  - `scripts/allocate_licenses.py` (`get_project_metadata` at lines `106–117`)
  - `main.tf` (`local.base_services` at lines `43–53`)
- **Implementation Specification**:
  1. **Unified Character-Wise `scripts/hcl_parser.py` (`CODE-07`)**:
     - Replace the duplicated regex `parse_tfvars` functions in `scripts/status.py:41–110` and `scripts/configure.py:197–257` with a single stdlib character-wise lexer/parser in `scripts/hcl_parser.py` that:
       - Strips `#` and `//` comments only outside double-quoted strings (preserving `#` inside URLs, tokens, or channel filters).
       - Tracks brace depth `{ ... }` and bracket depth `[ ... ]` so nested maps (`extra_params = { ... }`) and empty top-level maps (`confluence_config = {}`) parse accurately.
  2. **Implement `status.py --deep` (`CODE-10`, `DEPLOY-10`) & Stage 3 Workspace Connector State Check**:
     - In `determine_status` (`scripts/status.py:183, 684`), when `deep=True`, execute `terraform plan -detailed-exitcode -lock=false -no-color`: if exit code is `2` (drift detected), include `"drift_detected": True` and set `next_action` to re-plan/apply the drifted stage.
     - In `scripts/status.py:575–628`, include `tfvars.get("workspace_connectors", ["google_mail", "google_calendar", "google_drive", "google_chat"])` in `expected_connectors` when `enable_connectors` is `True`.
  3. **Harden Service Usage & Cloud Resource Manager Quota Headers (`DEPLOY-11`, `DOC-08`)**:
     - Add `"serviceusage.googleapis.com"` and `"cloudresourcemanager.googleapis.com"` to `local.base_services` (`main.tf:43–53`).
     - Pass `project_id=central_project` (`x-goog-user-project`) in `get_project_metadata` (`scripts/allocate_licenses.py:113–116`) and surface a descriptive warning in `get_dwd_checklist` (`scripts/status.py:738–754`) instead of `except Exception: pass` when `uniqueId` resolution fails.
- **Verification Criteria**:
  - `hcl_parser.parse_tfvars` accurately parses strings containing `#`, nested `extra_params` maps, and empty `{}` blocks.
  - `python3 scripts/status.py --deep` detects live infrastructure drift via `terraform plan -detailed-exitcode`.

---

#### `RM-08`: Add Strict `variables.tf` Validations, Remote GCS Backend Template & CI Workflow Parity
- **Priority**: `P1` | **Effort**: `M` (1 day) | **Dependencies**: `RM-01`, `RM-04`
- **Findings Addressed**: `CODE-12`, `DEPLOY-09`, `DEPLOY-14`
- **Affected Files & Exact Symbols**:
  - `variables.tf` (`customer_id`, `company_domain`, `workspace_customer_id`, `billing_account`, `project_id_prefix`, `workspace_admin_email` at lines `1–48`, new `licensing_project` variable)
  - `main.tf` (`google_project.projects` at lines `505–513`, `local_file.license_allocations` at lines `740–760`)
  - `backend.tf.example` (new opt-in GCS remote state backend template)
  - `.github/workflows/terraform.yml` (lines `22–40`)
- **Implementation Specification**:
  1. **Input Variable Validation Blocks in `variables.tf`**:
     - `customer_id`: `can(regex("^[a-z][a-z0-9-]{1,20}$", var.customer_id))` (ensuring `<project_id_prefix><customer_id>-<env>` complies with GCP's 6–30 char project ID limit).
     - `workspace_customer_id`: `can(regex("^C[0-9a-zA-Z]{7,10}$", var.workspace_customer_id))`.
     - `billing_account`: `can(regex("^[0-9A-F]{6}-[0-9A-F]{6}-[0-9A-F]{6}$", upper(var.billing_account)))`.
     - `company_domain`: `can(regex("^[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$", var.company_domain))`.
  2. **Explicit `licensing_project` & Restrictive `local_file` Permissions (`main.tf:740–760`)**:
     - Add `variable "licensing_project" { default = "" }` and set `licensing_project = coalesce(nullif(var.licensing_project, ""), var.billing_project, try(google_project.projects["prod"].project_id, values(google_project.projects)[0].project_id))` in `main.tf:743`.
     - Set `file_permission = "0600"` and `directory_permission = "0700"` on `resource "local_file" "license_allocations"` (`main.tf:740–760`).
  3. **Remote GCS Backend Template & CI Workflow Alignment**:
     - Provide `backend.tf.example` with a `backend "gcs" { bucket = "..." prefix = "prism/state" }` template and document state locking in `RUNBOOK.md`.
     - Update `.github/workflows/terraform.yml:37–40` to run `python3 scripts/package_marketing_assets.py --check` and execute `scripts/test_red.py` with `PYTHONDONTWRITEBYTECODE=1 GH_TOKEN= GITHUB_TOKEN=`.
- **Verification Criteria**:
  - Invalid `customer_id`, `workspace_customer_id`, or `billing_account` formats are caught at `terraform validate` / `terraform plan` time before any GCP API call.

---

### Phase 2: Architecture & Test Modularization (Maintainability & Scale)

#### `RM-09`: Modularize Monolithic `main.tf` (760 Lines) into Composable Terraform Sub-Modules
- **Priority**: `P2` | **Effort**: `L` (3 days) | **Dependencies**: `RM-01`, `RM-03`, `RM-08`
- **Findings Addressed**: `CODE-01`, `CODE-03`, `CODE-06`, `CODE-12`, `DEPLOY-08`
- **Affected Files**:
  - `main.tf` (lines `1–760`), `variables.tf` (lines `1–302`), `outputs.tf` (lines `1–210`)
  - New sub-modules: `modules/foundation/`, `modules/connectors/`, `modules/engines/`, `modules/licensing/`
- **Implementation Specification**:
  1. Decompose the 760-line root `main.tf` into four focused Terraform modules while preserving root input/output compatibility:
     - `modules/foundation`: `google_project.projects`, `google_project_service.services`, `google_project_service_identity.discoveryengine_sa`, `google_cloud_identity_group.users`, and `google_discovery_engine_user_store.default` (`main.tf:505–601`).
     - `modules/connectors`: Normalized connector locals and `google_discovery_engine_data_connector.connectors` (`main.tf:64–478, 604–673`).
     - `modules/engines`: `google_discovery_engine_search_engine.engines` and `google_discovery_engine_assistant.default` (`main.tf:676–737`).
     - `modules/licensing`: `local_file.license_allocations` (`main.tf:740–760`).
  2. Emit `moved { from = ... to = module.... }` blocks at the root so existing customer `terraform.tfstate` files migrate with zero resource replacements (`0` deletions/replacements verified by `scripts/plan_guard.py`).
- **Verification Criteria**:
  - `terraform plan` against an existing state fixture with `moved` blocks passes `scripts/plan_guard.py` with `0` deletions and `0` replacements.

---

#### `RM-10`: Split Monolithic `scripts/test_red.py` (2,651 Lines) into Domain Test Suites & Harden `deploy_marketing_assets.py` Hermetic Tests
- **Priority**: `P2` | **Effort**: `M` (2 days) | **Dependencies**: `RM-01`, `RM-04`
- **Findings Addressed**: `CODE-09`, `CODE-13`, `CODE-14`, `DOC-11` (resolves `CHAL-05`, `CHAL-07`)
- **Affected Files & Exact Symbols**:
  - `scripts/test_red.py` (lines `1–2651`, 13 `unittest.TestCase` classes, 96 test methods)
  - `scripts/deploy_marketing_assets.py` (`discover_environment` at lines `94–198`, `deploy_shared_skill` at lines `274–374`, `deploy_workflow_agent` at lines `609–690`, `deploy_pack` at lines `693–771`)
  - New test package: `tests/test_status.py`, `tests/test_configure.py`, `tests/test_plan_guard.py`, `tests/test_allocate_licenses.py`, `tests/test_verify.py`, `tests/test_terraform_contracts.py`, `tests/test_docs_parity.py`, `tests/test_marketing_assets.py`
- **Implementation Specification**:
  1. **Modularize `scripts/test_red.py`**:
     - Split the 13 `unittest.TestCase` classes (`TestAllocateLicensesNegative`, `TestPlanGuard`, `TestStatusPhaseDetection`, `TestVerifyConnectors`, `TestDocumentationContracts`, `TestTerraformDefaultsContract`, `TestVerifyWaitParsing`, `TestConfigureCLI`, `TestConfigureInteractive`, `TestStatusConfigIntegration`, `TestBranchAndIssueContracts`, `TestDataScrubbing`, `TestMarketingCatalogAndPackager`) into dedicated modules under `tests/` and keep `scripts/test_red.py` as a lightweight test discovery runner (`unittest.defaultTestLoader.discover("tests")`) so `make test` remains backward-compatible.
  2. **Harden `scripts/deploy_marketing_assets.py` & Expand Unit Test Coverage (`CODE-14`, `CHAL-05`, `CHAL-07`)**:
     - **Zero Filesystem Side Effects in `--dry-run`**: In `deploy_pack` (`scripts/deploy_marketing_assets.py:704–726`), when `dry_run=True`, call `packager.validate_catalog(catalog_dir=catalog_dir)` (or build into a `tempfile.TemporaryDirectory`) instead of writing `dist/marketing/brand-kit-governance.zip` and `marketing_pack_manifest.json` to `DEFAULT_OUTPUT_DIR` (`deploy_marketing_assets.py:705`).
     - **Broader Data Store & Connector Discovery**: In `discover_environment` (`scripts/deploy_marketing_assets.py:135–152`), allow configurable connector prefixes (including `jira`, `people-directory`) rather than hardcoding `preferred_prefixes = ("google-drive", "confluence", "slack")` and rigid suffixes (`_google_drive`, `_page`, `_space`, `_message`, `_file`).
     - **Comprehensive Unit Tests**: Add unit tests in `tests/test_marketing_assets.py` covering `deploy_shared_skill` (`CREATE` vs. `UPDATE` + Scotty raw ZIP upload at `deploy_marketing_assets.py:274–374`), `deploy_workflow_agent` (`CREATE` vs. `UPDATE` at `deploy_marketing_assets.py:609–690`), `_publish_and_enable_agent` (`PRIVATE -> DISABLED -> ENABLED` transitions at `deploy_marketing_assets.py:213–271`), and `discover_environment` (`engine_id` lookup, missing engine error, and widget model auto-detection at `deploy_marketing_assets.py:94–198`).
- **Verification Criteria**:
  - `python3 -m unittest discover -s tests -v` and `python3 -B scripts/test_red.py` execute in `< 1.5s` with zero network calls and zero writes outside `tempfile.TemporaryDirectory`.

---

### Phase 3: Ecosystem & Catalog Expansion

#### `RM-11`: Implement HubSpot CRM Federated Connector (`P3`) & Declarative Connector Registry Pattern
- **Priority**: `P2` | **Effort**: `L` (3 days) | **Dependencies**: `RM-07`, `RM-09`
- **Findings Addressed**: `DOC-07`, `DOC-12`
- **Affected Files**:
  - `docs/CONNECTORS_ROADMAP.md` (lines `18, 38–42`), `.github/issues/03_hubspot_connector.md`
  - `modules/connectors/`, `variables.tf`, `outputs.tf`, `scripts/configure.py`, `scripts/status.py`, `Makefile`
- **Implementation Specification**:
  1. Refactor connector metadata across `scripts/configure.py` and `scripts/status.py` into a single declarative `scripts/connector_registry.py` descriptor table (defining `key`, `enable_var`, `config_var`, `auth_env_var`, `checklist_flag`, `default_collection_id`, `connector_modes`, and `entities`).
  2. Implement the **P3 — HubSpot CRM** connector (`enable_hubspot_connector`, `hubspot_auth_type`, `hubspot_auth`, `hubspot_config`, `make hubspot-checklist`) in `FEDERATED` mode (`hubspot-federated-collection`, entities: `contacts`, `companies`, `deals`, `tickets`, `engagements`, `owners`) per `.github/issues/03_hubspot_connector.md` and `docs/CONNECTORS_ROADMAP.md:38–42`.
- **Verification Criteria**:
  - Adding a new connector to `connector_registry.py` automatically registers its CLI flags, `make <connector>-checklist`, Stage 0/2 guards, and contract tests.

---

#### `RM-12`: Expand Low-Code Agent & Skill Catalog Across Enterprise Domains & Integrate with Stage 5 Verification
- **Priority**: `P2` | **Effort**: `M` (2 days) | **Dependencies**: `RM-06`, `RM-10`
- **Findings Addressed**: `CODE-14`, `DOC-11` (resolves `CHAL-05`, `CHAL-07`)
- **Affected Files**:
  - `catalog/marketing/`, `scripts/package_marketing_assets.py` (lines `1–615`), `scripts/deploy_marketing_assets.py` (lines `1–869`), `scripts/verify.py` (lines `140–179`), `Makefile` (lines `28–30, 90–94`)
- **Implementation Specification**:
  1. Generalize `scripts/package_marketing_assets.py` (`--catalog-dir catalog/<pack>`) and `scripts/deploy_marketing_assets.py` (`--catalog-dir catalog/<pack>`) to support domain-specific asset packs (`catalog/marketing`, `catalog/engineering`, `catalog/revops`) while enforcing the `<= 3` items-per-pack budget cap (`MAX_CATALOG_ITEMS = 3` at `package_marketing_assets.py:31`) and deterministic ZIP packaging (`DETERMINISTIC_ZIP_DATE` at `package_marketing_assets.py:33`).
  2. Integrate optional catalog verification (`--verify-catalog catalog/marketing`) into `scripts/verify.py` (`check_engines_and_assistants` at `verify.py:140–179`) so Stage 5 (`make verify`) can assert that deployed `skillAgentDefinition` and `workflowAgentDefinition` resources under `default_assistant` are in `state == "ENABLED"` with `sharingConfig.scope == "ALL_USERS"`.
- **Verification Criteria**:
  - `make package-marketing` and `make verify` validate both core infrastructure and deployed low-code assistant agents/skills end-to-end.

---

## Part 5: Cross-Reference & Rubric Traceability Matrix

### 5.1 Requirement Coverage Matrix (`R1` – `R4`)

| Requirement ID | Requirement Description | Report Section(s) | Coverage Summary |
| :--- | :--- | :--- | :--- |
| **R1** | Deep review of existing issues across **Code** (`*.tf`, `scripts/*.py`, `scripts/*.sh`, `catalog/`), **Deployment Process** (`Makefile`, Stages 0–5, `bootstrap.sh`, `.github/workflows/terraform.yml`), and **Documentation** (`README.md`, `RUNBOOK.md`, `PRACTITIONERS_GUIDE.md`, `AGENTS.md`, `GEMINI.md`, `docs/CONNECTORS_ROADMAP.md`, `.github/issues/*.md`, `PROJECT.md`, `TEST_READY.md`) | **Executive Summary**, **Part 1** (`CODE-01`–`CODE-14`), **Part 2** (`DEPLOY-01`–`DEPLOY-14`), **Part 3** (`DOC-01`–`DOC-12`) | **40 distinct, non-duplicative findings** (`14` Code, `14` Deployment Process, `12` Documentation) covering every Terraform file, Python script (including `package_marketing_assets.py` and `deploy_marketing_assets.py`), shell script, CI workflow, and documentation/template file |
| **R2** | Concrete, actionable improvements for every identified issue with exact file paths, line numbers, and verbatim repository evidence | **Part 1** (`CODE-01`–`CODE-14`), **Part 2** (`DEPLOY-01`–`DEPLOY-14`), **Part 3** (`DOC-01`–`DOC-12`) | Every finding provides exact file paths, 1-indexed line numbers, character-for-character verbatim repository snippets verified programmatically, failure mode analysis, and drop-in code/config/documentation fixes |
| **R3** | Prioritized engineering planning roadmap (`P0` / `P1` / `P2`) with effort sizing (`S` / `M` / `L`), dependencies, affected files/symbols, and verification criteria | **Part 4** (`RM-01`–`RM-12`), **Part 5** (`§5.2`, `§5.3`) | **12-item phased roadmap** across **Phase 0** (`RM-01`–`RM-04`, `P0`), **Phase 1** (`RM-05`–`RM-08`, `P1`), **Phase 2** (`RM-09`–`RM-10`, `P2`), and **Phase 3** (`RM-11`–`RM-12`, `P2`) with 100% bidirectional traceability to all 40 findings |
| **R4** | Strict read-only codebase constraint (do not modify, create, or delete any repository file outside `.agents/teamwork/`) | **Executive Summary**, **Part 5** (`§5.1`) | Verified via `git status --porcelain` and `git diff --stat` (`12 files changed, 1029 insertions(+), 174 deletions(-)` unchanged before and after audit; all Python checks run with `PYTHONDONTWRITEBYTECODE=1 python3 -B`) |

---

### 5.2 Master Finding & Roadmap Traceability Matrix (`CODE-01`..`14`, `DEPLOY-01`..`14`, `DOC-01`..`12`)

| Finding ID | Category | Severity | Primary Verified File(s) & Exact Line Numbers | Mapped Roadmap Item(s) |
| :--- | :--- | :---: | :--- | :--- |
| **CODE-01** | `Code` | **Critical** | `main.tf:331–422, 477, 677, 707, 718`; `outputs.tf:166–209`; `variables.tf:79–90, 268–302`; `terraform.tfvars.example:81–94` | `RM-01`, `RM-09` |
| **CODE-02** | `Code` | **Critical** | `scripts/configure.py:38–91, 102–180, 302–309, 357–446, 471–498, 519–530, 871–944, 1037–1041` | `RM-01` |
| **CODE-03** | `Code` | **High** | `main.tf:208–226, 306–324, 410–417`; `variables.tf:160–172, 254–266` | `RM-03`, `RM-09` |
| **CODE-04** | `Code` | **High** | `scripts/allocate_licenses.py:348–369, 432–455`; `main.tf:740–760` | `RM-05` |
| **CODE-05** | `Code` | **High** | `scripts/allocate_licenses.py:168–188, 468–482, 500–528`; `Makefile:74–79`; `scripts/status.py:657–684` | `RM-05` |
| **CODE-06** | `Code` | **High** | `main.tf:436–471`; `variables.tf:44–48, 215–235`; `outputs.tf:143–164`; `terraform.tfvars.example:8, 81–94`; `scripts/status.py:894–921` | `RM-01`, `RM-07`, `RM-09` |
| **CODE-07** | `Code` | **High** | `scripts/status.py:41–110`; `scripts/configure.py:197–257` | `RM-07` |
| **CODE-08** | `Code` | **High** | `scripts/verify.py:59–80, 82–138, 140–215, 229–248, 305–365`; `scripts/allocate_licenses.py:51` | `RM-06` |
| **CODE-09** | `Code` | **High** | `scripts/test_red.py:2336–2378`; `scripts/create_github_issues.sh:40–95` | `RM-04`, `RM-10` |
| **CODE-10** | `Code` | **Medium** | `scripts/status.py:113–121, 131–165, 183, 268–298, 575–628, 932, 967` | `RM-04`, `RM-07` |
| **CODE-11** | `Code` | **Medium** | `scripts/configure.py:412–416, 567–576, 890–894`; `Makefile:65–73` | `RM-03` |
| **CODE-12** | `Code` | **Medium** | `main.tf:14, 505–513, 740–760`; `variables.tf:1–16, 28–42, 62–65`; `versions.tf:1–17`; `bootstrap.sh:41–56` | `RM-08`, `RM-09` |
| **CODE-13** | `Code` | **Low** | `scripts/test_red.py:406–429, 2299–2311`; `.github/workflows/terraform.yml:37–40` | `RM-04`, `RM-10` |
| **CODE-14** | `Code` | **Medium** | `scripts/deploy_marketing_assets.py:94–198, 213–374, 609–771`; `scripts/package_marketing_assets.py:1–615`; `Makefile:30, 90–94`; `scripts/test_red.py:2461–2648` | `RM-10`, `RM-12` |
| **DEPLOY-01** | `Deployment Process` | **Critical** | `main.tf:331–422, 477, 677, 707, 718`; `variables.tf:79–90, 268–302`; `terraform.tfvars.example:81–94` | `RM-01` |
| **DEPLOY-02** | `Deployment Process` | **Critical** | `Makefile:1, 18–21, 45–48, 54–63`; `scripts/status.py:396, 439, 555, 566, 930` | `RM-01` |
| **DEPLOY-03** | `Deployment Process` | **High** | `scripts/configure.py:38–91, 270–327, 471–475, 489, 871–927, 1032–1041` | `RM-01` |
| **DEPLOY-04** | `Deployment Process` | **High** | `scripts/configure.py:412–433, 567–576, 890–911`; `scripts/status.py:503–539`; `Makefile:65–72`; `main.tf:463–466` | `RM-03` |
| **DEPLOY-05** | `Deployment Process` | **High** | `Makefile:74–79`; `scripts/allocate_licenses.py:484–569`; `scripts/status.py:657–684`; `main.tf:588–601` | `RM-05` |
| **DEPLOY-06** | `Deployment Process` | **High** | `scripts/allocate_licenses.py:168–188, 468–520` | `RM-05` |
| **DEPLOY-07** | `Deployment Process` | **High** | `scripts/verify.py:128–133, 229–248, 345–354, 387` | `RM-06` |
| **DEPLOY-08** | `Deployment Process` | **High** | `main.tf:676–703, 717–737`; `RUNBOOK.md:249`; `AGENTS.md:123` | `RM-05`, `RM-09` |
| **DEPLOY-09** | `Deployment Process` | **High** | `versions.tf:1–17`; `Makefile:45–52, 65–73`; `scripts/plan_guard.py:48–134`; `scripts/status.py:268–295` | `RM-04`, `RM-08` |
| **DEPLOY-10** | `Deployment Process` | **Medium** | `scripts/status.py:183, 932, 967` | `RM-07` |
| **DEPLOY-11** | `Deployment Process` | **Medium** | `scripts/status.py:735–755`; `scripts/allocate_licenses.py:106–117, 139`; `main.tf:43–53, 743` | `RM-07` |
| **DEPLOY-12** | `Deployment Process` | **Medium** | `scripts/allocate_licenses.py:503–505, 571–605`; `RUNBOOK.md:304`; `AGENTS.md:125` | `RM-05` |
| **DEPLOY-13** | `Deployment Process` | **Medium** | `bootstrap.sh:41–56` | `RM-02` |
| **DEPLOY-14** | `Deployment Process` | **Low** | `.github/workflows/terraform.yml:22–40`; `Makefile:96–100`; `versions.tf:1–17` | `RM-04`, `RM-08` |
| **DOC-01** | `Documentation` | **Critical** | `terraform.tfvars.example:17–21, 81–94`; `variables.tf:79–90, 268–302`; `PRACTITIONERS_GUIDE.md:219–231, 281–284`; `RUNBOOK.md:170–173, 181, 187, 226`; `AGENTS.md:39, 80–85` | `RM-01`, `RM-02` |
| **DOC-02** | `Documentation` | **Critical** | `AGENTS.md:80–85`; `RUNBOOK.md:170–174, 195, 214`; `PRACTITIONERS_GUIDE.md:227, 310, 364, 558`; `scripts/status.py:396, 439, 555`; `Makefile:1, 18–21, 45–63`; `README.md:206–226` | `RM-01`, `RM-02` |
| **DOC-03** | `Documentation` | **High** | `AGENTS.md:5–6, 25–26, 42`; `.agent/workflows/deploy.md:1–11`; `Makefile:33–34`; `RUNBOOK.md:62` | `RM-02` |
| **DOC-04** | `Documentation` | **High** | `PRACTITIONERS_GUIDE.md:133–150, 188–200, 628`; `RUNBOOK.md:156, 192`; `main.tf:482–495`; `variables.tf:178, 203–206`; `AGENTS.md:15, 22` | `RM-02` |
| **DOC-05** | `Documentation` | **High** | `terraform.tfvars.example:8, 81–94`; `variables.tf:44–48, 215–227`; `main.tf:442–466`; `outputs.tf:143–164`; `scripts/status.py:907–916`; `AGENTS.md:15, 22`; `RUNBOOK.md:206`; `PRACTITIONERS_GUIDE.md:239–266`; `scripts/test_red.py:1739–1752` | `RM-01`, `RM-02`, `RM-07` |
| **DOC-06** | `Documentation` | **High** | `scripts/configure.py:38–91, 102–180, 302–309, 357–446, 470–498, 519–530, 586–599, 871–944, 951–954, 1037–1041, 1094–1099` | `RM-01`, `RM-02` |
| **DOC-07** | `Documentation` | **Medium** | `docs/CONNECTORS_ROADMAP.md:11–18, 32–36`; `README.md:35–38, 44–80, 180–181, 232–281`; `main.tf:331–422` | `RM-02`, `RM-11` |
| **DOC-08** | `Documentation` | **Medium** | `README.md:127–136`; `PRACTITIONERS_GUIDE.md:114–124`; `scripts/status.py:738–750`; `main.tf:43–53` | `RM-02`, `RM-07` |
| **DOC-09** | `Documentation` | **Medium** | `bootstrap.sh:41–56`; `outputs.tf:51–56`; `AGENTS.md:8–24`; `RUNBOOK.md:99–111` | `RM-02` |
| **DOC-10** | `Documentation` | **Medium** | `RUNBOOK.md:127–132`; `main.tf:570–585`; `outputs.tf:11–14` | `RM-02` |
| **DOC-11** | `Documentation` | **Medium** | `PROJECT.md:47–50`; `TEST_READY.md:24–28`; `PRACTITIONERS_GUIDE.md:323, 473–477`; `README.md:230–281`; `AGENTS.md:52–109, 128–137` | `RM-02`, `RM-10`, `RM-12` |
| **DOC-12** | `Documentation` | **Low** | `Makefile:8–10`; `scripts/verify.py:135–136`; `.github/issues/01_confluence_connector.md:26–29, 46–50`; `.github/issues/02_slack_connector.md:42–53, 74–78`; `docs/` | `RM-02`, `RM-11` |

---

### 5.3 Adversarial Challenge & Forensic Audit Resolution Matrix (`A1`–`A4`, `B1`–`B19`, `C1`–`C8` & `CHAL-01`–`CHAL-08`)

| Audit / Challenge ID | Source Report | Defect Identified in Iteration 1 Draft | Resolution Verified in Iteration 2 |
| :--- | :--- | :--- | :--- |
| **A1** | `auditor_r1_1` (`Exec Summary`) | Fabricated `package_marketing_assets.py --check` output string | Replaced with exact empirical CLI output: `Status : PASS` and `Budget Usage : 3 / 3 max items (2 low-code agents, 1 shared skills)` (`Executive Summary`) |
| **A2** | `auditor_r1_1` (`Exec Summary`, `CODE-01`) | Fabricated `test_slack_v3_federated_defaults_contract` failure message at line `1722` | Replaced with exact traceback at `scripts/test_red.py:1723` (`AssertionError: None is not true`) (`Executive Summary`, `CODE-01`) |
| **A3** | `auditor_r1_1` (`CODE-02`) | Fabricated `test_configure_stage_0_safety_guard_forces_enable_false` failure message at line `1999` | Replaced with exact traceback at `scripts/test_red.py:2000` (`AssertionError: 1 != 0`) (`Executive Summary`, `CODE-02`) |
| **A4** | `auditor_r1_1` (`CODE-02`) | Fabricated `test_configure_enable_connectors_stage_2_success` failure message at line `2052` | Replaced with exact traceback at `scripts/test_red.py:2053` (`AssertionError: False is not true`) (`Executive Summary`, `CODE-02`) |
| **B1–B3** | `auditor_r1_1` (`Exec Summary`, `CODE-01`) | Misstated provider constraints (`versions.tf`), fabricated Slack HCL locals/resources, and misnamed `outputs.tf` checklist outputs | Replaced with verbatim quotes from `versions.tf:1–17`, `main.tf:331–422, 604–673`, and `outputs.tf:166–209` (`Executive Summary`, `CODE-01`) |
| **B4–B8** | `auditor_r1_1` (`CODE-02`–`CODE-06`) | Misnamed Python/HCL identifiers and reconstructed snippets in `configure.py`, `main.tf`, and `allocate_licenses.py` | Replaced with 100% verbatim quotes from `scripts/configure.py`, `main.tf:213–226, 306–324, 436–466`, and `scripts/allocate_licenses.py:171–184, 361–364, 432–455` (`CODE-02`–`CODE-06`) |
| **B9–B12** | `auditor_r1_1` (`CODE-07`–`CODE-12`) | Reconstructed parser, verifier, `.env.jira`, and `google_project.projects` snippets | Replaced with 100% verbatim quotes from `scripts/status.py:54–65`, `scripts/configure.py:210–218, 567–576`, `scripts/verify.py:71–74, 127–133, 198–243, 305–353`, and `main.tf:505–513, 740–748` (`CODE-07`–`CODE-12`) |
| **B13–B19** | `auditor_r1_1` (`DEPLOY-02`–`DEPLOY-14`) | Reconstructed snippets or used ellipses in `Makefile`, `status.py`, `main.tf`, `bootstrap.sh`, and `.github/workflows/terraform.yml` | Replaced all 46 Part 2 fenced blocks with contiguous character-for-character repository slices (`DEPLOY-01`–`DEPLOY-14`) |
| **C1** | `auditor_r1_1` (`DOC-01`) | Quoted a 14-line `people_directory_config` block that did not match `terraform.tfvars.example:81–94` | Replaced with the exact 14-line verbatim block from `terraform.tfvars.example:81–94` (`DOC-01`) |
| **C2** | `auditor_r1_1` (`DOC-02`) | Quoted fabricated `AGENTS.md:49, 80–85` and `RUNBOOK.md:195–201` blocks and left conversational reasoning notes in prose | Replaced with verbatim quotes from `AGENTS.md:80–85`, `RUNBOOK.md:170–174`, and `Makefile:1, 18–21, 45–63` with zero internal monologue (`DOC-02`) |
| **C3** | `auditor_r1_1` (`DOC-03`) | Fabricated `AGENTS.md:6` and `.agent/workflows/deploy.md:1–11` snippets | Replaced with exact character-for-character quotes from `AGENTS.md:5–6, 25–26, 42` and `.agent/workflows/deploy.md:1–11` (`DOC-03`) |
| **C4** | `auditor_r1_1` (`DOC-04`) | Fabricated `PRACTITIONERS_GUIDE.md:133–151` heading and `188–200` Jira HCL block | Replaced with exact character-for-character quotes from `PRACTITIONERS_GUIDE.md:133–150, 188–200, 628` and `main.tf:482–495` (`DOC-04`) |
| **C5** | `auditor_r1_1` (`DOC-06`) | Claimed `docs/CONNECTORS_ROADMAP.md` marked Confluence (`P1`) and People Directory (`P4`) as unshipped | Replaced with exact verbatim table from `docs/CONNECTORS_ROADMAP.md:11–18, 32–36` showing Confluence and People Directory are `🟢 GA (Shipped)` while only Slack (`P2`) and HubSpot (`P3`) are `📋 Accepted / Backlog`, plus `README.md:35–38, 180–181` (`DOC-07`) |
| **C6** | `auditor_r1_1` (`DOC-08`) | Fabricated `RUNBOOK.md:131` checkbox text | Replaced with exact verbatim lines `127–132` of `RUNBOOK.md` and lines `570–585` of `main.tf` (`DOC-10`) |
| **C7** | `auditor_r1_1` (`DOC-09`) | Fabricated `README.md:127–136` `gcloud services enable` block | Replaced with exact verbatim lines `127–136` of `README.md`, lines `114–124` of `PRACTITIONERS_GUIDE.md`, and lines `738–750` of `scripts/status.py` (`DOC-08`) |
| **C8** | `auditor_r1_1` (`DOC-10`) | Fabricated `PROJECT.md:50` and `TEST_READY.md:25–26` quotes | Replaced with exact verbatim quotes from `PROJECT.md:47–50` (`46 existing + all new unit tests`) and `TEST_READY.md:24–28` (`69 (46 baseline + 23 new test cases)` across `12 unittest.TestCase classes`) (`DOC-11`) |
| **CHAL-01** | `challenger_r1_2` / `reviewer_r1_2` | Proposed `slack_config` in `CODE-01`/`RM-01` used wrong default entity names, omitted `incremental_refresh_interval = optional(string, "10800s")`, and omitted attributes accessed by `main.tf:340–420` | `RM-01` specifies the complete `slack_config`, `slack_auth`, and `slack_auth_type` schemas matching `main.tf:331–422` and `scripts/test_red.py:1714–1730` (`entities = ["conversation", "message", "file"]`, `incremental_refresh_interval = optional(string, "10800s")`) |
| **CHAL-02** | `challenger_r1_2` / `reviewer_r1_2` | Proposed `configure.py` fix referenced nonexistent dictionary keys, variable names, and helper functions | `DOC-06` and `RM-01` use `{opt["value"] for opt in CONNECTOR_OPTIONS}`, `enable_people_directory_connector`, and `update_tfvars` (`scripts/configure.py:449–580`) |
| **CHAL-03** | `challenger_r1_2` / `reviewer_r1_2` | Proposed Stage 4 `RM-05` fix checked whether `outputs.user_store_names` was non-empty, which is always true after Stage 1 (`for_each = local.environments`) | `RM-05` inspects `google_discovery_engine_user_store.default` instances in `terraform.tfstate` to verify `enable_license_auto_register == True` and `default_license_config == license_config_names[env]` |
| **CHAL-04** | `challenger_r1_2` / `reviewer_r1_2` | `CODE-06`/`DOC-05`/`RM-01` changing `google_people_directory` -> `native_cloud_identity` in `terraform.tfvars.example` would break `test_people_directory_defaults_contract` (`test_red.py:1744`) unless updated in lockstep | `DOC-05` and `RM-01` explicitly specify updating `terraform.tfvars.example:84–94`, `outputs.tf:149–152`, `scripts/status.py:907–916`, and `scripts/test_red.py:1739–1752` in lockstep |
| **CHAL-05** | `challenger_r1_2` / `reviewer_r1_2` | Omitted audit of `scripts/deploy_marketing_assets.py` (869 lines) and `Makefile:93–94` (`deploy-marketing`) | Covered in `CODE-14`, `RM-10`, `RM-12`, and `§5.2` (including `--dry-run` ZIP side-effect at `deploy_marketing_assets.py:705`, data store discovery at `135–152`, and unit test coverage) |
| **CHAL-06** | `challenger_r1_2` / `reviewer_r1_2` | Fabricated code snippets and wrong function names in Python scripts | Every snippet in `remediation_part3_4_5.md` is copied character-for-character from repository files and verified by Python check; all function names match ground truth (`parse_state`, `audit_inputs`, `check_data_connectors`, `check_license_configs`) |
| **CHAL-07** | `challenger_r1_2` | Inaccurate test count (`94` vs `96` tests in `scripts/test_red.py`) | `DOC-11` and `RM-10` accurately cite `96` test methods across `13` `unittest.TestCase` classes in `scripts/test_red.py` (2,651 lines) |
| **CHAL-08** | `challenger_r1_2` / `reviewer_r1_2` | Leaked conversational reasoning text in `DOC-02` | Completely eliminated; verified 0 occurrences in `remediation_part3_4_5.md` |
