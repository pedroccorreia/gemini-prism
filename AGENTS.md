# Agent Protocol — Prism (Gemini Enterprise Provisioning)

Autonomous agent protocol for Prism: provisioning Gemini Enterprise across customer environments.

## Start Here
Execute `make status --json`. Act on `next_action`. Reference the matching stage in [RUNBOOK.md](RUNBOOK.md).

## Rules of Engagement
- **MUST**:
  1. Run `make status` before and after every action.
  2. Use `make plan-<stage>` and `make apply-<stage>` (always applies guarded saved plans).
  3. Use `make enable-connectors` to validate prerequisites and activate connectors in Stage 2.
  4. Run `make plan-connectors && make apply-connectors` after changing `seat_allocations` in `terraform.tfvars` (to refresh `config/license_allocations.json`), then run `make licenses-dryrun` before `make licenses`.
  5. Stop at human gates (`status.py` exit code 2) and post the designated hand-off template.
  6. Provision all data connectors (Workspace and third-party) in `FEDERATED` mode (`connector_modes = ["FEDERATED"]`, or `["FEDERATED", "ACTIONS"]` when MCP/BAP actions are enabled).
  7. When `enable_workspace_actions = true`, configure 3LO Web Application OAuth credentials via `TF_VAR_workspace_oauth` (`client_id` and `client_secret`) with redirect URIs `https://vertexaisearch.cloud.google.com/console/oauth/default_oauth.html` and `https://vertexaisearch.cloud.google.com/oauth-redirect`, enable BAP write actions (`create_calendar_event`, `update_calendar_event`, etc.), rotate `collection_id` to distinct collection IDs (`*-actions-collection`) with `create_before_destroy = true`, and run `python3 scripts/configure.py --sync-workspace-actions` (chained in `make apply-connectors`) to persist `actionConfig.isActionConfigured = true`.
  8. Preserve supplemental non-Terraform data stores attached to the unified Search Engine via `extra_data_store_ids` in `terraform.tfvars` so `make apply-connectors` never detaches customer BigQuery/GCS or demo stores.
- **MUST NOT**:
  1. Run `terraform destroy` or apply any plan with deletions/replacements.
  2. Modify `.tf` files to bypass guards or remove `deletion_policy = "PREVENT"`.
  3. Flip `enable_connectors = true` without explicit human confirmation.
  4. Use `--skip-preflight` or switch GCP identities/credentials.
  5. Commit `terraform.tfvars`, `terraform.tfstate`, or `config/license_allocations.json`.
  6. Provision `DATA_INGESTION` connectors or use `jira_server` / `confluence_server` / `BASIC_AUTH` against Atlassian Cloud (`*.atlassian.net`).
  7. Use `admin.directory.customschema.readonly` in DWD scopes; the valid Admin SDK scope for custom user schemas is `https://www.googleapis.com/auth/admin.directory.userschema.readonly`.
  8. Enable Google internal allowlists, `GOOGLE_INTERNAL` fields, or `custom_mcp` workarounds against `*mcp.googleapis.com`.

## Cross-Harness Combo-Box Protocol (Stage 0)
When entering Stage 0 (`make status --json` reports `phase: 0`):
1. Parse the `interactive_questions` array (`planned_connectors` multi-select, `geap_governance_mode` `"none"` vs `"foundation"`, and `enable_workspace_actions` `"false"` vs `"true"`) and Help Center URLs.
2. Query the human operator using your harness native combo-box tool (`ask_question`, `AskUserQuestion`) to select connectors, GEAP Agent Governance Foundation, and whether to enable Google Workspace Actions.
3. Apply user selections non-interactively: `python3 scripts/configure.py --apply-json '<json>'` (or `--governance-mode <none|foundation> --workspace-actions <true|false>`).
4. Audit remaining variables via `make check-inputs` (and inspect GEAP Day-2 handoff metadata via `make geap-checklist` once provisioned).

## Human Gates
| Stage | Gate Reason | Signal for Resuming | Template |
| :--- | :--- | :--- | :--- |
| **Stage 0** | Missing inputs or invalid credentials | Valid `terraform.tfvars` / active ADC | `inputs` / `identity` |
| **Stage 2** | Domain-Wide Delegation & Workspace Admin access | `enable_connectors = true` | `dwd` |
| **Stage 2** | Atlassian Jira authorization / URI missing | Valid Jira URI & credentials configured | `jira` |
| **Stage 2** | Atlassian Confluence authorization / URI missing | Valid Confluence URI & credentials configured | `confluence` |
| **Stage 2** | Slack Enterprise authorization / URI missing | Valid Slack URI / `team_id` & credentials configured | `slack` |
| **Stage 4** | Missing billing subscription IDs | Subscription IDs set in tfvars | `subscription` |

## Phase Detection (`make status --json`)
| Phase | Name | Owner | Condition | Next Action |
| :---: | :--- | :---: | :--- | :--- |
| 0 | `preflight_inputs` | Human | Missing tfvars/credentials/state mismatch | `make configure` or `make check-inputs` |
| 1 | `foundation_apply` | Agent | `project_ids` absent from state | `make plan-foundation && make apply-foundation` |
| 2 | `dwd_authorization` | Human | `enable_connectors == false` | `make dwd-checklist (then make enable-connectors)` |
| 3 | `connectors_and_engines_apply` | Agent | `search_engine_names` absent | `make plan-connectors && make apply-connectors` |
| 4 | `license_distribution` | Agent | `license_config_names` absent | `make licenses` |
| 5 | `verification` | Agent | All components present | `make verify` |

## Hand-off Templates
### `inputs`
```text
ACTION REQUIRED: Customer configuration variables missing or placeholder in terraform.tfvars.
Run `make configure` for the interactive wizard or `make check-inputs` to view step-by-step lookup guides.
```

### `dwd`
```text
ACTION REQUIRED (Workspace Super Admin): Authorize Domain-Wide Delegation in https://admin.google.com/ac/owl/domainwidedelegation.
Add API Client using the 21-digit numeric Client ID (uniqueId) and service agent email from `make dwd-checklist` with OAuth scopes CSV.
In https://admin.google.com, allow GCP projects under Security > Access and data control > API controls > Google Cloud Core Services, and verify Workspace data access under Generative AI > Gemini Enterprise. Set enable_connectors = true when done.
```

### `workspace_actions`
```text
ACTION REQUIRED: Configure Google Workspace OAuth 2.0 Web Application client for Actions.
Run `make workspace-actions-checklist` to view the authorized redirect URIs.
Create an OAuth client ID (Web application) in https://console.cloud.google.com/apis/credentials and export TF_VAR_workspace_oauth='{"client_id":"...","client_secret":"..."}'.
```

### `jira`
```text
ACTION REQUIRED (Atlassian Admin): Configure Atlassian Jira authorization.
Run `make jira-checklist` to view the OAuth 2.0 (3LO) callback URL, required scopes, and instance URI.
Configure Atlassian Developer Console app or API token, set TF_VAR_jira_auth, and update jira_config.instance_uri in terraform.tfvars.
```

### `confluence`
```text
ACTION REQUIRED (Atlassian Admin): Configure Atlassian Confluence authorization.
Run `make confluence-checklist` to view the OAuth 2.0 (3LO) callback URL, required scopes, and instance URI.
Configure Atlassian Developer Console app or API token, set TF_VAR_confluence_auth (or reuse TF_VAR_jira_auth), and update confluence_config.instance_uri in terraform.tfvars.
```

### `slack`
```text
ACTION REQUIRED (Slack Admin): Configure Slack Enterprise authorization.
Run `make slack-checklist` to view the Federated + MCP Actions setup, OAuth redirect URL, and target entities.
Set slack_config.instance_uri (and optional team_id) in terraform.tfvars; optionally create a BYO Slack App in https://api.slack.com/apps and set TF_VAR_slack_auth.
```

### `permissions`
```text
ACTION REQUIRED (IAM & Workspace Admin): The executing principal lacks required permissions.
Grant GCP roles (roles/resourcemanager.projectCreator, roles/billing.user) AND Workspace Groups Admin in https://admin.google.com/ac/roles.
```

### `subscription`
```text
ACTION REQUIRED (Billing Admin): Gemini Enterprise subscription IDs are missing.
Purchase subscription on Billing Account (or run `python3 scripts/allocate_licenses.py --discover`) and set license_config_id and subscription_id in terraform.tfvars.
```

### `state_mismatch`
```text
CRITICAL (Human Intervention): Local state contains projects from another deployment.
Do not apply. Backup or isolate current state before proceeding (see RUNBOOK.md §State Safety).
```

### `identity`
```text
ACTION REQUIRED: Active GCP credentials not found.
Run `gcloud auth application-default login` and `gcloud auth login` with a customer domain identity that holds Workspace Groups Admin.
```

## Troubleshooting
| Error Signature | Cause | Remediation |
| :--- | :--- | :--- |
| `plan_guard: DESTRUCTIVE CHANGES` | Resources would be deleted/replaced | Inspect diff; verify customer IDs; never bypass |
| `DWD: Invalid scope customschema` | Wrong Admin SDK schema scope name | Use `https://www.googleapis.com/auth/admin.directory.userschema.readonly` |
| `google_cloud_identity_group: 403` | Missing Groups Admin permission | Post `permissions` template (requires Workspace Groups Admin) |
| `connectors: PERMISSION_DENIED` | DWD token propagation latency | Wait 5 minutes and retry `make apply-connectors` |
| `Workspace Actions: ActionState CREATING / ActionConfigured False` | Missing 3LO OAuth credentials (`TF_VAR_workspace_oauth`) or Terraform omitted `OUTPUT_ONLY` field `actionConfig.isActionConfigured` | Configure `TF_VAR_workspace_oauth` (`client_id` + `client_secret`) in `.env.workspace` and run `python3 scripts/configure.py --sync-workspace-actions` (chained in `make apply-connectors`) |
| `jira: 401/403/UNAUTHORIZED` | Invalid Jira credentials or scopes | Post `jira` template; verify `TF_VAR_jira_auth` |
| `confluence: 401/403/UNAUTHORIZED` | Invalid Confluence credentials or scopes | Post `confluence` template; verify `TF_VAR_confluence_auth` / `TF_VAR_jira_auth` |
| `slack: 401/403/invalid_auth` | Invalid Slack OAuth credentials or scopes | Post `slack` template; verify `slack_config` & `TF_VAR_slack_auth` |
| `DataStore ... is being deleted` | Async GCP deletion after collection removal (up to 2h) | Use a distinct `collection_id` in connector config |
| `Error 400: DataStore ... currently exists in list at index N of Engine` | Deleting an existing connector before detaching its data store from `google_discovery_engine_search_engine` | Keep `lifecycle { create_before_destroy = true }` on `google_discovery_engine_data_connector.connectors` so the Engine updates before old collections are destroyed |
| `DeleteCollection: 500 / spanner: value not found` | Deleting a `FEDERATED` connector while `state == "CREATING"` | Wait ~5m for BAP connection to reach `ACTIVE` or `FAILED` before deleting |
| `assistant: 409 ALREADY_EXISTS` | Engine auto-creates `default_assistant` | Import into state before `make apply-connectors` |
| `missing license_config_id` | Console only displays Subscription ID | Run `python3 scripts/allocate_licenses.py --discover` |
| `distributeLicenseConfig: Insufficient` | Billing pool out of seats or auto-routed to 1st project | Increase order `quantity` (takes ~5m to activate) or partial-retract (`fullRetract: false`) auto-routed seats |
| `Procurement Order: 400 on modify` | Order in `ORDER_STATE_PENDING_CANCELLATION` or wrong param | Revert cancellation first, then update `quantity` with `offer` URI |

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
