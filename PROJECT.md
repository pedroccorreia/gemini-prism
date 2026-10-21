# Project: Gemini Prism Interactive Connector Onboarding & Terraform Variable Configuration Engine

## Architecture
Gemini Prism is a reference deployment and validation framework for Gemini Enterprise and Discovery Engine. This project adds an interactive, stage-aware connector configuration and onboarding engine (`scripts/configure.py`) with cross-harness combo-box integration, missing-variable auditing, Help Center guidance, status engine hooks, and Terraform variable definitions.

### Data Flow
1. **Interactive / Harness Input**:
   - Harness Mode (Mode A): Coding harness agents invoke `scripts/configure.py --check --json`, receive `interactive_questions` schema, present native combo-box UI (`ask_question` / `AskUserQuestion`), and apply selections non-interactively via `--apply-json '<json>'` or CLI flags (`--connectors`, `--set`).
   - Terminal Mode (Mode B): Interactive terminal (`sys.stdin.isatty() == True`) renders ANSI arrow-key (`[↑/↓]`) and spacebar (`[Space]`) multi-select combo-box (`[✓] / [ ]`), falling back to numbered selection on non-TTY streams. Typing `?` renders inline boxed "Where to find this" guide with console URLs and CLI commands.
2. **Configuration Persistence**:
   - `terraform.tfvars`: Receives `planned_connectors` list and customer configuration.
   - Stage 0 Safety Guard: Forces `enable_connectors = false`, `enable_jira_connector = false`, `enable_people_directory_connector = false` in Stage 0 regardless of input.
   - `.env.jira`: Receives Jira API token credentials, protected by `.gitignore` (`.env` and `.env.*`).
3. **Auditing & Status**:
   - Missing Variable Audit (`--check` / `make check-inputs`): Validates populated vs missing/placeholder variables, providing step-by-step lookup guides, admin URLs, CLI lookup commands, required IAM roles, and official Help Center documentation URLs.
   - Status Integration (`scripts/status.py`): In Stage 0, guides user to `make configure` / `make check-inputs` and embeds `interactive_questions` in `--json`. In Stage 2, validates `planned_connectors` against foundation prerequisites and guides user to `make enable-connectors`.
4. **Stage 2 Enablement Helper**:
   - `scripts/configure.py --enable-connectors` (or `make enable-connectors`): Verifies foundation prerequisites and required variables for `planned_connectors`, then flips matching `enable_* = true` flags in `terraform.tfvars`.
5. **Testing & Verification**:
   - `scripts/test_red.py`: Comprehensive Red Team test harness running with 100% Python standard library (`unittest`), verifying CLI, schemas, interactive fallbacks, status detection, docs contracts, git branch, and data scrubbing.
   - `make test`: Unified verification gate executing unit tests, `terraform fmt -check`, and `terraform validate`.

---

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Git Feature Branch | Create and check out feature branch `feat/interactive-connector-onboarding` | M1 | R1 |
| 2 | Issue 05 Specification | Structured feature request `.github/issues/05_interactive_connector_onboarding.md` following repo template | M1 | R1 |
| 3 | Issue Creation Script Update | Update `scripts/create_github_issues.sh` to register issue 05 and support targeted argument `05` | M1 | R1 |
| 4 | Terraform Variable `planned_connectors` | Add `planned_connectors` (`list(string)`, allowed: `workspace`, `jira`, `people_directory`, default `["workspace"]`) to `variables.tf` | M1 | R2 |
| 5 | Terraform Example Values | Update `terraform.tfvars.example` with `planned_connectors = ["workspace"]` | M1 | R2 |
| 6 | Gitignore Credential Protection | Add `.env` and `.env.*` to `.gitignore` | M1 | R2 |
| 7 | Zero-Dependency Script (`scripts/configure.py`) | 100% Python standard library implementation, no pip dependencies | M2 | R3 |
| 8 | Mode A: Combo-Box Schema (`--check --json`) | Outputs `interactive_questions` array with `is_multi_select: true`, options, and official Help Center URLs | M2 | R3 |
| 9 | Mode A: Non-Interactive Apply | `--apply-json '<json>'` and CLI flags (`--connectors`, `--set`) safely applying config to `terraform.tfvars` & `.env.jira` | M2 | R3 |
| 10 | Mode B: Terminal Interactive Combo-Box | Arrow-key navigation (`[↑/↓]`) and spacebar toggle (`[Space]`) combo-box (`[✓] / [ ]`) when `sys.stdin.isatty() == True` | M2 | R3 |
| 11 | Mode B: Non-TTY Fallback | Automatic fallback to numbered selection on non-interactive / redirected streams | M2 | R3 |
| 12 | Mode B: Inline Help (`?`) | Typing `?` renders boxed "Where to find this" guide with console URLs, CLI commands, and docs links | M2 | R3 |
| 13 | Stage-Aware Deployment Safety | Stage 0 forces `enable_connectors = false`, `enable_jira_connector = false`, `enable_people_directory_connector = false` | M2 | R3 |
| 14 | Missing Variable Audit (`--check` / `make check-inputs`) | Reports configured vs missing variables, lookup commands, admin URLs, IAM roles, and Help Center URLs | M2 | R3 |
| 15 | Stage 2 Enablement Helper (`--enable-connectors`) | Verifies prerequisites/credentials for `planned_connectors` and flips matching `enable_* = true` | M2 | R3 |
| 16 | Status Engine Stage 0 Integration | `scripts/status.py` points to `make configure` and `make check-inputs`, includes `interactive_questions` in `--json` | M3 | R4 |
| 17 | Status Engine Stage 2 Integration | `scripts/status.py` validates `planned_connectors` and guides user to `make enable-connectors` | M3 | R4 |
| 18 | Makefile Targets | Add `configure`, `check-inputs`, `enable-connectors` targets and update `help` in `Makefile` | M3 | R4 |
| 19 | Runbook Stage 0 & Stage 2 Documentation | Update `RUNBOOK.md` preserving all 5 contract subheadings; add Connector Help Center reference table | M3 | R5 |
| 20 | Agent Protocol & Template Update | Update `AGENTS.md` with Stage 0 combo-box protocol and hand-off templates, strictly maintaining `<= 150` lines | M3 | R5 |
| 21 | Readme & Practitioner Guide Docs | Update `README.md` and `PRACTITIONERS_GUIDE.md` with new targets, flags, and workflow | M3 | R5 |
| 22 | E2E Test Suite (Tiers 1-4) | Comprehensive unit and integration test coverage in `scripts/test_red.py` | M_E2E | Verification |
| 23 | Final Integrated Verification | Pass `make test` (46 existing + all new unit tests, `terraform fmt -check`, `terraform validate`, 0 leaks) | M_FINAL | AC 54-65 |

---

## Milestones

| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Git Branch, Issue 05, and Terraform Declarations | R1 + R2: Git branch checkout `feat/interactive-connector-onboarding`, issue 05 spec file, issue publisher update, `variables.tf`, `terraform.tfvars.example`, `.gitignore` | None | DONE |
| M2 | Interactive Configuration Engine (`scripts/configure.py`) | R3: Zero-dependency onboarding & audit engine, Mode A & Mode B combo-box, stage safety, missing inputs audit, Stage 2 enablement helper | M1 | DONE |
| M3 | Status Engine, Makefile, and Documentation Integration | R4 + R5: `scripts/status.py` stage 0/2 hooks, `Makefile` targets, `RUNBOOK.md` contract subheadings & Help Center table, `AGENTS.md` (<=150 lines), `README.md`, `PRACTITIONERS_GUIDE.md` | M1, M2 | DONE |
| M_E2E | E2E Test Suite & Testing Track | Test suite expansion in `scripts/test_red.py`: Mode A/B tests, schema tests, stage 0 safety tests, stage 2 enablement tests, status tests, contract tests | M1, M2, M3 | DONE |
| M_FINAL | Full Verification, Adversarial Hardening & Audit | Execution of `make test`, `git branch` check, data scrubbing check, forensic audit with binary veto | M_E2E | DONE |

---

## Interface Contracts

### 1. `scripts/configure.py` CLI & Schema Interface
- **Commands**:
  - `python3 scripts/configure.py`: Interactive Mode B wizard (TTY combo-box or non-TTY numbered fallback).
  - `python3 scripts/configure.py --check`: Audits `terraform.tfvars` against `planned_connectors`. Prints human-readable status table, returns exit code 0 if all configured, exit code 1 if variables are missing/placeholder.
  - `python3 scripts/configure.py --check --json`: Audits and emits JSON payload with schema:
    ```json
    {
      "status": "ok" | "missing_variables",
      "stage": 0 | 1 | 2 | 3 | 4,
      "interactive_questions": [
        {
          "id": "planned_connectors",
          "header": "Planned Connectors",
          "question": "Which data connectors do you plan to onboard for Gemini Enterprise?",
          "is_multi_select": true,
          "options": [
            {
              "value": "workspace",
              "label": "Google Workspace (Gmail, Drive, Docs)",
              "description": "Domain-Wide Delegation connector for corporate email and files",
              "docs_url": "https://docs.cloud.google.com/gemini/enterprise/docs/connectors/drive"
            },
            {
              "value": "jira",
              "label": "Jira Cloud",
              "description": "Atlassian Jira Cloud project and issue search connector",
              "docs_url": "https://docs.cloud.google.com/gemini/enterprise/docs/connectors/jira-cloud"
            },
            {
              "value": "people_directory",
              "label": "Google Workspace People Directory",
              "description": "User profile and directory search connector",
              "docs_url": "https://developers.google.com/admin-sdk/directory/v1/guides"
            }
          ],
          "default": ["workspace"]
        }
      ],
      "configured_variables": { ... },
      "missing_variables": [
        {
          "name": "string",
          "description": "string",
          "connector": "workspace" | "jira" | "people_directory" | "foundation",
          "where_to_get": "string",
          "admin_url": "string",
          "lookup_command": "string",
          "required_roles": ["string"],
          "help_center_url": "string"
        }
      ]
    }
    ```
  - `python3 scripts/configure.py --apply-json '<json>'`: Non-interactively applies selections. In Stage 0, strictly sets `enable_connectors = false`, `enable_jira_connector = false`, and `enable_people_directory_connector = false`.
  - `python3 scripts/configure.py --connectors <c1,c2>`: CLI flag equivalent to `--apply-json`.
  - `python3 scripts/configure.py --enable-connectors`: Verifies prerequisites and flips matching `enable_* = true`.

### 2. `scripts/status.py` Integration Contract
- Stage 0 `status["next_action"]` must reference `make configure` and `make check-inputs`.
- Stage 0 `status.py --json` must include the `"interactive_questions"` key containing the combo-box schema.
- Stage 2 `status.py` must validate `planned_connectors` and guide to `make enable-connectors`.

### 3. Documentation & Scrubbing Contracts
- `AGENTS.md`: Must be `<= 150` lines.
- `RUNBOOK.md`: Every `## Stage \d+ — ` must retain all 5 subheadings: `**Owner:**`, `**Preconditions (machine-checkable):**`, `**Do:**`, `**Done when:**`, `**If it fails:**`.
- Data Scrubbing: Zero instances of any pattern in `LEAK_PATTERNS` (especially developer username) in any tracked file.

---

## Code Layout
- `.github/issues/05_interactive_connector_onboarding.md` (Issue 05 spec)
- `scripts/create_github_issues.sh` (Issue publisher)
- `variables.tf` (Terraform variables)
- `terraform.tfvars.example` (Terraform example config)
- `.gitignore` (Ignore `.env`, `.env.*`)
- `scripts/configure.py` (Interactive onboarding & audit engine)
- `scripts/status.py` (Status detection engine)
- `Makefile` (Make targets)
- `RUNBOOK.md` (Operator runbook)
- `AGENTS.md` (Agent hand-off protocols)
- `README.md` (Repository documentation)
- `PRACTITIONERS_GUIDE.md` (Practitioner onboarding guide)
- `scripts/test_red.py` (Red Team test harness)
