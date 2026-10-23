# Prism — Gemini Enterprise Provisioning Runbook

This runbook defines the authoritative, staged procedure for **Prism**: provisioning Gemini Enterprise (Vertex AI Search) with Google Workspace, Atlassian Jira, and Atlassian Confluence connectors across customer environments.

It serves both **human operators** and **autonomous AI agents** ([AGENTS.md](AGENTS.md)). Every stage contains machine-checkable preconditions, execution targets via `make`, success criteria, failure handling, and checklist items.

---

## Deployment Lifecycle & State Machine

```mermaid
stateDiagram-v2
  [*] --> S0: Clone Repository
  S0: Stage 0 — Preflight & Inputs (Agent, Human supplies values)
  S1: Stage 1 — Foundation Apply (Agent)
  G2: Stage 2 — DWD Authorization (HUMAN GATE)
  S3: Stage 3 — Connectors, Engine & Assistant (Agent)
  G4: Stage 4 — Subscription IDs Present? (HUMAN GATE if missing)
  S4: Stage 4 — License Distribution & User Store Binding (Agent)
  S5: Stage 5 — Verification & Handoff (Agent, then Human UAT)

  S0 --> S1: make status exit 0
  S1 --> G2: project_ids output present in state
  G2 --> S3: enable_connectors = true in terraform.tfvars
  S3 --> G4: search_engine_names present in state
  G4 --> S4: license_config_id and subscription_id set
  S4 --> S5: license configs ACTIVE across projects
  S5 --> [*]: make verify exit 0
```

---

## State Safety & Disaster Prevention

> [!CAUTION]
> **State Mismatch Protection:** If a local `terraform.tfstate` exists containing `google_project` resources whose `project_id` does not match the customer identifier `${project_id_prefix}${customer_id}-<env>`, running `terraform apply` will destroy those existing projects.
> `scripts/status.py` and `scripts/plan_guard.py` automatically detect state mismatches and refuse plan/apply actions. Never bypass this check by editing `.tf` files or force-applying.

---

## Stage 0 — Preflight & Inputs

**Owner:** Agent (Human supplies customer values)

**Preconditions (machine-checkable):**
- Tools check: `terraform version` (>= 1.5.0), `gcloud --version`, `python3 --version` (>= 3.9).
- Identity check: `gcloud auth application-default print-access-token` returns a valid token for a **customer Workspace domain user** who holds:
  - GCP IAM roles: `roles/resourcemanager.projectCreator` and `roles/billing.user`.
  - Google Workspace Admin role: **Groups Admin** (or Super Admin) in [Workspace Admin Console > Admin roles](https://admin.google.com/ac/roles) (required to create `google_cloud_identity_group`).

**Do:**
1. Check live status and blockers:
   ```bash
   make status
   ```
2. Configure input variables and select planned enterprise connectors:
   - **Interactive Terminal Wizard (Humans)**: Run the zero-dependency onboarding wizard:
     ```bash
     make configure
     ```
     Provides an interactive combo-box with arrow keys (`[↑/↓]`), spacebar selection (`[Space]`), Enter confirmation, and inline boxed help (`?`) with direct documentation links.
   - **Cross-Harness Combo-Box (Agents)**: Inspect the `interactive_questions` array via `make status ARGS="--json"` or `make check-inputs ARGS="--json"`. Present questions through native harness tools (`ask_question`, `AskUserQuestion`) and apply answers non-interactively:
     ```bash
     python3 scripts/configure.py --apply-json '{"planned_connectors": ["workspace", "jira"], "customer_id": "acme"}'
     ```
   - **Manual Configuration**: Alternatively, copy template `cp terraform.tfvars.example terraform.tfvars` and edit customer values.
3. Audit configured vs. missing variables:
   ```bash
   make check-inputs
   ```
   Audits `terraform.tfvars` against `planned_connectors`, surfacing missing/placeholder variables, step-by-step lookup guides, Admin Console URLs, CLI lookup commands, required IAM roles, and official Help Center links.
4. Stage 0 Deployment Safety Guard:
   Verify that `planned_connectors` records customer intent (e.g. `["workspace", "jira"]`), while `enable_connectors = false`, `enable_jira_connector = false`, and `enable_people_directory_connector = false` remain `false` during Stage 0 to protect Stage 1 Foundation and Stage 2 Human Gates.
5. Run Terraform initialization and validation:
   ```bash
   terraform init
   terraform validate
   ```

**Done when:**
- `make check-inputs` returns exit code 0 (`Audit Status: ALL CONFIGURED`).
- `make status` returns exit code 0 and indicates readiness for Stage 1 (`foundation_apply`).

**If it fails:**
- Missing CLI tools: Install required packages (`terraform`, `gcloud`, `python3`).
- Missing or placeholder variables: Run `make configure` or `make check-inputs` to view resolution guides and console URLs.
- Authentication failure: Escalate using the **identity** template; run `gcloud auth application-default login` and `gcloud auth login`.
- State mismatch detected: Escalate using the **state_mismatch** template. Reconcile or back up foreign state before proceeding.

**Checklist:**
- [ ] Required tools verified in PATH
- [ ] Active GCP account authenticated with Workspace **Groups Admin** rights
- [ ] `planned_connectors` selected and `terraform.tfvars` populated with non-placeholder values
- [ ] `make check-inputs` audits clean with 0 missing variables
- [ ] Initial `terraform init` and `terraform validate` pass

---

## Stage 1 — Foundation Infrastructure Apply

**Owner:** Agent

**Preconditions (machine-checkable):**
- `make status` returns exit code 0 (`phase: 1, phase_name: "foundation_apply"`).
- `enable_connectors` is `false` in `terraform.tfvars`.

**Do:**
1. Generate and guard the foundation plan:
   ```bash
   make plan-foundation
   ```
2. Apply the guarded plan:
   ```bash
   make apply-foundation
   ```

**Done when:**
- `terraform output -json project_ids` contains all configured environments.
- `config/license_allocations.json` is automatically generated by Terraform.
- Re-plan produces zero diff (`make status` exits with code 2, signalling Stage 2 gate).

**If it fails:**
- `plan_guard` stops on deletions: Check why existing resources would be modified. Do not set `ALLOW_DESTROY=1` unless destruction is intended.
- `google_cloud_identity_group` 403 Forbidden: Provisioner principal lacks Groups Admin role in Google Workspace Admin Console. Escalate using **permissions** template.
- Project creation quota / billing link failure: Escalate to GCP organization billing admin.

**Checklist:**
- [ ] `make plan-foundation` generated `.plans/foundation.tfplan` with 0 deletes/replaces
- [ ] Foundation resources successfully applied across all environments
- [ ] Discovery Engine service agent identities created (`service-<PROJECT_NUMBER>@gcp-sa-discoveryengine.iam.gserviceaccount.com`)
- [ ] Cloud Identity User Groups created (`<customer_id>-<env>-users@<domain>`)
- [ ] Location IdP configured to `GSUITE`

---

## Stage 2 — Workspace & Atlassian Jira Authorization Gate

**Owner:** Human (Workspace Super Admin & Atlassian Admin Gate)

**Preconditions (machine-checkable):**
- `make status` returns exit code 2 (`phase: 2, phase_name: "dwd_authorization"` or `"jira_authorization"`).
- Foundation projects and Discovery Engine service agents exist.

**Do:**
1. Retrieve the authorization parameters (including the **21-digit numeric `client_id`**):
   ```bash
   make dwd-checklist
   ```
   > **Where does the 21-digit numeric Client ID come from?**
   > `service-<PROJECT_NUMBER>@gcp-sa-discoveryengine.iam.gserviceaccount.com` is a Google-managed Service Agent and does not appear in the standard Cloud Console *Service Accounts* list. `make dwd-checklist` automatically resolves its 21-digit numeric OAuth2 `uniqueId` via the Service Usage API (`POST https://serviceusage.googleapis.com/v1beta1/projects/<PROJECT_NUMBER>/services/discoveryengine.googleapis.com:generateServiceIdentity`).
2. Open the [Google Workspace Admin Console - Domain-Wide Delegation](https://admin.google.com/ac/owl/domainwidedelegation).
3. Click **Add new** API client for each environment project:
   - **Client ID**: The 21-digit numeric `client_id` (`uniqueId`) or `service_agent_email` from `make dwd-checklist`.
   - **OAuth Scopes**: Copy and paste the comma-separated scope string from `dwd-checklist`:
     ```
     https://www.googleapis.com/auth/admin.directory.user.readonly,https://www.googleapis.com/auth/admin.directory.group.readonly,https://www.googleapis.com/auth/admin.directory.group.member.readonly,https://www.googleapis.com/auth/admin.directory.orgunit.readonly,https://www.googleapis.com/auth/admin.directory.userschema.readonly,https://www.googleapis.com/auth/directory.readonly,https://www.googleapis.com/auth/gmail.readonly,https://www.googleapis.com/auth/calendar.readonly,https://www.googleapis.com/auth/drive.readonly,https://www.googleapis.com/auth/chat.spaces.readonly,https://www.googleapis.com/auth/chat.messages.readonly
     ```
   - Click **Authorize**.
4. In Workspace Admin Console under **Security > Access and data control > API controls > Google Cloud Core Services**, allow access for the environment GCP project IDs if prompted.
5. If Atlassian Jira is planned (`"jira"` in `planned_connectors`):
   - Run `make jira-checklist` to view the Jira instance URI, resolved `cloudId` (`instance_id`), required OAuth scopes, and redirect URLs.
   - Ensure `connector_modes = ["FEDERATED"]` is configured in `jira_config`.
   - For Jira Cloud (`*.atlassian.net`, OAuth 2.0 3LO, v3): Register an OAuth 2.0 (3LO) app in [Atlassian Developer Console](https://developer.atlassian.com/console/myapps/) with callback URL `https://vertexaisearch.cloud.google.com/console/oauth/jira_oauth.html` (and `https://vertexaisearch.cloud.google.com/oauth-redirect` if Actions are enabled), configure the scopes from `jira-checklist`, and supply `client_id`, `client_secret`, and `instance_id` via `export TF_VAR_jira_auth='{"client_id":"...","client_secret":"...","instance_id":"..."}'` or `terraform.tfvars`.
   - Update `jira_config.instance_uri` and `jira_config.instance_id` in `terraform.tfvars`.
6. If Atlassian Confluence is planned (`"confluence"` in `planned_connectors` or `enable_confluence_connector = true`):
   - Run `make confluence-checklist` to view the Confluence instance URI, resolved `cloudId` (`instance_id`), required OAuth scopes, and redirect URLs.
   - Ensure `connector_modes = ["FEDERATED"]` is configured in `confluence_config`.
   - For Confluence Cloud (`*.atlassian.net`, OAuth 2.0 3LO, v4): Register/configure an OAuth 2.0 (3LO) app in [Atlassian Developer Console](https://developer.atlassian.com/console/myapps/) with callback URL `https://vertexaisearch.cloud.google.com/console/oauth/confluence_oauth.html` (and `https://vertexaisearch.cloud.google.com/oauth-redirect` if Actions are enabled), configure the scopes from `confluence-checklist`, and supply `client_id`, `client_secret`, and `instance_id` via `export TF_VAR_confluence_auth='{"client_id":"...","client_secret":"...","instance_id":"..."}'` or `terraform.tfvars`. (If Confluence shares the same Atlassian tenant and 3LO app as Jira, `TF_VAR_confluence_auth` and instance URI automatically fall back to `jira_auth` and `jira_config`.)
   - Update `confluence_config.instance_uri` and `confluence_config.instance_id` in `terraform.tfvars` (or omit to inherit from Jira).
7. If Google People & Org Directory is planned (`"people_directory"` in `planned_connectors` or `enable_people_directory_connector = true`):
   - Run `make people-checklist` to view directory configuration, target entities, and sync parameters.
   - People Directory reuses the DWD authorization above; ensure all Directory scopes (`user.readonly`, `orgunit.readonly`, `userschema.readonly`, `directory.readonly`) are authorized.
8. If HubSpot is planned (`"hubspot"` in `planned_connectors` or `enable_hubspot_connector = true`):
   - Run `make hubspot-checklist` to view connector configuration and target CRM entities (`contact`, `company`, `deal`, `ticket`).
   - Create a Private App in HubSpot (`https://app.hubspot.com`), grant read scopes, and supply the service key Bearer token via `export TF_VAR_hubspot_auth='{"api_token":"pat-..."}'`.
   - Ensure `connector_modes = ["FEDERATED"]` is configured in `hubspot_config`.
9. Enable planned connectors via Stage 2 Enablement Helper:
   ```bash
   make enable-connectors
   ```
   *(Or manually update `terraform.tfvars` with `enable_connectors = true`, `enable_jira_connector = true`, `enable_confluence_connector = true`, `enable_people_directory_connector = true`, and/or `enable_hubspot_connector = true`.)*
   ```
   The enablement helper verifies that all prerequisites and credentials for `planned_connectors` are configured and valid (Workspace domain and customer ID, Jira instance URI and OAuth/token credentials, People Directory scopes, HubSpot credentials), then automatically flips the corresponding `enable_* = true` flags in `terraform.tfvars`. Alternatively, set flags manually in `terraform.tfvars`.

**Done when:**
- Planned connectors are validated and matching `enable_* = true` flags are enabled in `terraform.tfvars` via `make enable-connectors` (or manually set).
- If `enable_jira_connector = true`, `jira_config.instance_uri` is non-empty and non-placeholder.
- If `enable_confluence_connector = true`, `confluence_config.instance_uri` (or inherited `jira_config.instance_uri`) is non-empty and non-placeholder.
- `make status` returns exit code 0 (`phase: 3, phase_name: "connectors_and_engines_apply"`).

**If it fails:**
- DWD authorization rejected by Admin Console: Verify executing human is a Workspace Super Admin and use the 21-digit numeric `client_id` from `make dwd-checklist`.
- Incomplete scopes: Ensure all 11 required scopes are pasted without trailing spaces.
- Jira OAuth/Token rejection: Verify Atlassian 3LO app redirect URI and scopes match `make jira-checklist`, and credentials in `TF_VAR_jira_auth` have access to the target Jira Cloud instance.
- Confluence OAuth/Token rejection: Verify Atlassian 3LO app redirect URI and scopes match `make confluence-checklist`, and credentials in `TF_VAR_confluence_auth` (or fallback `TF_VAR_jira_auth`) have access to the target Confluence Cloud instance.
- HubSpot token rejection: Verify HubSpot Private App Service Key has required scopes and is exported via `TF_VAR_hubspot_auth`.
- Enablement helper reports missing prerequisites: Run `make check-inputs` to identify unresolved variables and consult the Help Center reference table below.

### Connector Help Center Reference Table

| Connector | Mode | Official Help Center & Guides | Admin Consoles | Required IAM Roles & Credentials |
| :--- | :--- | :--- | :--- | :--- |
| **Google Workspace** (Gmail, Calendar, Drive, Chat) | `FEDERATED` | [Workspace Connectors Guide](https://docs.cloud.google.com/gemini/enterprise/docs/connectors/introduction-to-connectors-and-data-stores)<br/>[Gmail Guide](https://docs.cloud.google.com/gemini/enterprise/docs/connectors/gmail)<br/>[Drive Guide](https://docs.cloud.google.com/gemini/enterprise/docs/connectors/drive) | [Workspace DWD Console](https://admin.google.com/ac/owl/domainwidedelegation)<br/>[Core Services](https://admin.google.com/ac/owl) | Google Workspace Super Admin<br/>21-digit numeric Client ID (`uniqueId`) |
| **Atlassian Jira Cloud** | `FEDERATED` | [Jira Cloud Connector Guide](https://docs.cloud.google.com/gemini/enterprise/docs/connectors/jira-cloud) | [Atlassian Developer Console](https://developer.atlassian.com/console/myapps/)<br/>[Atlassian Admin Console](https://admin.atlassian.com) | Atlassian Org Admin / Site Admin<br/>OAuth 2.0 (3LO) App / Token (`TF_VAR_jira_auth`) |
| **Atlassian Confluence** | `FEDERATED` | [Confluence Cloud Connector Guide](https://docs.cloud.google.com/gemini/enterprise/docs/connectors/confluence-cloud) | [Atlassian Developer Console](https://developer.atlassian.com/console/myapps/) | Atlassian Org Admin / Site Admin<br/>OAuth 2.0 (3LO) or Shared Jira credentials |
| **Google People Directory** | `DATA_INGESTION` (Incremental) | [Google Directory API Guide](https://developers.google.com/admin-sdk/directory/v1/guides)<br/>[Cloud Identity Docs](https://cloud.google.com/identity/docs/) | [Workspace DWD Console](https://admin.google.com/ac/owl/domainwidedelegation) | Google Workspace Super Admin<br/>Service Agent DWD (0 additional credentials) |
| **HubSpot** | `FEDERATED` | [HubSpot Connector Guide](https://docs.cloud.google.com/gemini/enterprise/docs/connectors/hubspot) | [HubSpot App Settings](https://app.hubspot.com) | HubSpot Super Admin<br/>Private App Service Key / Bearer Token (`TF_VAR_hubspot_auth`) |

**Checklist:**
- [ ] Retrieved 21-digit numeric `client_id`, service agent email, and scope CSV via `make dwd-checklist`
- [ ] Authorized DWD client for each environment in Google Workspace Admin Console (including Directory scopes)
- [ ] Allowed GCP projects under Google Cloud Core Services
- [ ] Configured Jira OAuth app / API token via `make jira-checklist` (if Jira planned)
- [ ] Configured Confluence OAuth app / credentials via `make confluence-checklist` (if Confluence planned)
- [ ] Inspected People Directory settings via `make people-checklist` (if People Directory planned)
- [ ] Configured HubSpot Private App service key via `make hubspot-checklist` (if HubSpot planned)
- [ ] Validated prerequisites and enabled planned connectors via `make enable-connectors` (or flipped `enable_* = true` in `terraform.tfvars`)

---

## Stage 3 — Workspace, Jira, Confluence & HubSpot Connectors, Search Engines & Assistants

**Owner:** Agent (after Stage 2 Human Gate)

**Preconditions (machine-checkable):**
- `make status` returns exit code 0 (`phase: 3, phase_name: "connectors_and_engines_apply"`).
- `enable_connectors` is `true` in `terraform.tfvars` (or `enable_jira_connector` / `enable_confluence_connector` / `enable_hubspot_connector` with configured URI).

**Do:**
1. Generate and guard the connectors plan:
   ```bash
   make plan-connectors
   ```
2. Apply the guarded plan:
   ```bash
   make apply-connectors
   ```

**Done when:**
- `terraform output -json search_engine_names` contains all configured environments.
- `terraform output -json assistant_names` contains all configured environments.
- All provisioned connectors (Workspace, Jira, and/or Confluence) exist in state.
- Re-plan produces zero diff.

**If it fails:**
- Connector creation fails with `PERMISSION_DENIED` or `unauthorized_client`: Domain-Wide Delegation OAuth tokens can take up to 5–15 minutes to propagate. Wait 5 minutes and retry `make apply-connectors`.
- Jira or Confluence connector fails with authentication/network error: Verify instance URI is reachable, allowlist static IPs if enabled, and verify `TF_VAR_jira_auth` / `TF_VAR_confluence_auth`.
- If permission failure persists after 15 minutes: Escalate with the **dwd**, **jira**, or **confluence** template to re-verify Client ID and scope entries.
- `google_discovery_engine_assistant.default` fails with `409 Already Exists`: Provisioning a search engine with `SEARCH_ADD_ON_LLM` automatically creates `default_assistant`. Import it into state (`terraform import 'google_discovery_engine_assistant.default["<env>"]' projects/<PROJECT_ID>/locations/global/collections/default_collection/engines/<ENGINE_ID>/assistants/default_assistant`) and re-run `make plan-connectors && make apply-connectors`.
- If permission failure persists after 15 minutes: Escalate with the **dwd** template to re-verify Client ID and scope entries.

**Checklist:**
- [ ] `make plan-connectors` generated `.plans/connectors.tfplan` with 0 deletes/replaces
- [ ] Workspace data connectors provisioned (`google_mail`, `google_calendar`, `google_drive`, `google_chat`)
- [ ] Atlassian Jira connector provisioned with multi-entity data stores (if enabled)
- [ ] Atlassian Confluence connector provisioned with multi-entity federated data stores (if enabled)
- [ ] Unified Search Engine provisioned for each environment with flattened connector data stores
- [ ] Governed Gemini Enterprise Assistant provisioned with web grounding
- [ ] Engine-scoped IAM permissions granted to User Cloud Identity Groups

---

## Stage 4 — License Seat Distribution & User Store Binding

**Owner:** Agent (Human gate only if subscription IDs are missing)

**Preconditions (machine-checkable):**
- `license_config_id` and `subscription_id` in `terraform.tfvars` are populated with active billing subscription IDs. (If only the subscription name is visible in Cloud Console, run `python3 scripts/allocate_licenses.py --discover` to look up both UUIDs from the Billing Account.)
- `make status` returns exit code 0 (`phase: 4, phase_name: "license_distribution"`).

**Do:**
1. *(Optional)* Auto-discover active subscription and `license_config_id` from the Billing Account:
   ```bash
   python3 scripts/allocate_licenses.py --discover
   ```
2. Perform preflight checks and dry-run distribution:
   ```bash
   make licenses-dryrun
   ```
3. Execute seat distribution from Cloud Billing Account pool to environment projects:
   ```bash
   make licenses
   ```
4. List active project license configurations:
   ```bash
   make licenses-list
   ```
5. **Close the declarative loop:** Emit the distributed license configuration names and add them to `terraform.tfvars`:
   ```bash
   python3 scripts/allocate_licenses.py --emit-tfvars
   ```
   Add the generated `license_config_names = { ... }` block to `terraform.tfvars` and run `make plan-connectors && make apply-connectors` to ensure `google_discovery_engine_user_store.default_license_config` is drift-free and managed by Terraform.

**Done when:**
- `make licenses-list` shows `ACTIVE` state with the expected seat allocations for each environment.
- `make status` returns exit code 0 (`phase: 5, phase_name: "verification"`).

**If it fails:**
- Missing subscription IDs: Run `python3 scripts/allocate_licenses.py --discover`. If no active subscription exists on the Billing Account, `make status` exits with code 2; escalate with the **subscription** template.
- Project number mismatch: Preflight assertions fail loudly. Verify that `config/license_allocations.json` project numbers match Cloud Resource Manager metadata.
- Insufficient pool capacity: Billing account pool lacks free seats. Increase capacity in Google Cloud Console or reduce `seat_allocations`.

**Checklist:**
- [ ] `make licenses-dryrun` passed preflight project verification and capacity checks
- [ ] `make licenses` successfully distributed seats across environment projects
- [ ] `license_config_names` added to `terraform.tfvars` and reconciled via `terraform apply`

---

## Stage 5 — Verification & End-User Handoff

**Owner:** Agent, then Human (User Acceptance Testing)

**Preconditions (machine-checkable):**
- `make status` returns exit code 0 (`phase: 5, phase_name: "verification"`).

**Do:**
1. Run end-to-end verification (polls with timeout for connectors to transition to `ACTIVE`):
   ```bash
   make verify WAIT=15m
   ```
2. Review the printed summary table and Vertex AI Search console URLs.
3. Conduct User Acceptance Testing (Human):
   - Add pilot users to the provisioned Cloud Identity User Group (`<customer_id>-<env>-users@<domain>`).
   - Allow **1–3 minutes** for Cloud Identity group membership and User Store license auto-assignment to propagate.
   - Open the Vertex AI Search application console in an Incognito browser window.
   - Verify search queries across Gmail, Calendar, Drive, and Chat.
   - Verify Gemini Enterprise Assistant answers and web grounding.

**Done when:**
- `make verify` exits with code 0 (all components report `ACTIVE`).
- Pilot users can log in and execute search queries successfully.

**If it fails:**
- Connectors stuck in `INITIALIZING`: Allow up to 15–30 minutes for initial Workspace connector federation handshakes.
- User login denied or license not yet assigned: Wait 1–3 minutes for group membership propagation, and verify user store auto-registration is `true`.

**Checklist:**
- [ ] `make verify` passes with all components `ACTIVE`
- [ ] Console URLs confirmed accessible
- [ ] Pilot users granted access via Cloud Identity group
- [ ] End-to-end user search verification completed
