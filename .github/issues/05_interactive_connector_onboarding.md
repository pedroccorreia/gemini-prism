---
title: "feat(onboarding): Interactive Connector Onboarding Wizard & Input Variable Configuration Engine"
priority: "P0 - Immediate / Core DX"
labels: ["enhancement", "onboarding", "cli", "wizard", "priority:p0"]
---

### Summary
Implement an interactive connector onboarding wizard and Terraform input variable configuration engine with cross-harness combo-box integration, missing-variable auditing, and Gemini Enterprise Help Center guidance in `gemini-prism`.

This eliminates onboarding friction and prevents premature deployment errors by introducing:
1. **Mode A (Cross-Harness Combo-Box Integration)**: `--check --json` outputting machine-parseable `interactive_questions` schemas for coding harness agent tools (`ask_question`, `AskUserQuestion`), alongside non-interactive `--apply-json`, `--connectors`, and `--set` application flags.
2. **Mode B (Interactive Terminal Combo-Box)**: 100% Python standard library terminal UI supporting arrow-key navigation (`[↑/↓]`), spacebar toggle (`[Space]`), inline `?` boxed help guides, and automatic fallback to numbered prompts on non-TTY streams.
3. **Stage-Aware Deployment Safety**: Stage 0 records `planned_connectors` while guaranteeing runtime flags (`enable_connectors`, `enable_jira_connector`, `enable_people_directory_connector`) remain `false`. Stage 2 provides `make enable-connectors` to validate prerequisites and flip `enable_* = true`.
4. **Missing Variable Audit (`make check-inputs`)**: Comprehensive reporting of configured vs. missing/placeholder variables with direct links to Admin Consoles, CLI lookup commands, required IAM roles, and official Google Cloud Help Center documentation.

### Priority
**P0 - Immediate / Core DX** (Foundational enabler for interactive multi-agent and operator setup)

### Architecture & Dual-Mode Mechanics

#### Mode A: Cross-Harness Combo-Box Integration
- `--check --json` outputs an `interactive_questions` array with question text, `is_multi_select: true`, options, and official Help Center documentation URLs so coding harness agents can directly invoke their native combo-box tool (`ask_question`, `AskUserQuestion`).
- `--apply-json '<json>'` (and CLI `--connectors` / `--set`) applies selections non-interactively to `terraform.tfvars` and `.env.jira`.

#### Mode B: Interactive Terminal UI
- When run in an interactive terminal (`sys.stdin.isatty() == True`), renders an arrow-key (`[↑/↓]`) and spacebar (`[Space]`) multi-select combo-box (`[✓] / [ ]`) for `planned_connectors` and sub-options, with automatic fallback to numbered selection on non-TTY streams.
- Supports typing `?` at any prompt to display an inline boxed "Where to find this" guide with exact console links, CLI commands, and Help Center documentation.

#### Stage-Aware Deployment Safety
- In Stage 0, sets `enable_connectors = false`, `enable_jira_connector = false`, and `enable_people_directory_connector = false` in `terraform.tfvars` while recording `planned_connectors` to prevent bypassing Stage 1 Foundation and Stage 2 Human Gates.

#### Missing Variable Audit
- Compares configured vs. missing/placeholder variables, providing step-by-step lookup instructions (`where_to_get`, `admin_url`, `lookup_command`, required IAM roles), and official Google Cloud Gemini Enterprise Help Center URLs for all planned connectors.

#### Stage 2 Enablement Helper
- `scripts/configure.py --enable-connectors` (and `make enable-connectors`) verifies that all required variables and credentials for `planned_connectors` are populated and valid, then flips the corresponding `enable_* = true` flags in `terraform.tfvars`.

### Proposed Terraform Configuration Architecture
```hcl
variable "planned_connectors" {
  type        = list(string)
  description = "List of enterprise connectors planned for deployment (workspace, jira, people_directory)"
  default     = ["workspace"]

  validation {
    condition = alltrue([
      for c in var.planned_connectors : contains(["workspace", "jira", "people_directory"], c)
    ])
    error_message = "Each element of planned_connectors must be one of: 'workspace', 'jira', 'people_directory'."
  }
}
```

In `terraform.tfvars.example`:
```hcl
# Planned Enterprise Connectors (workspace, jira, people_directory)
# Stage 0 records intent; actual connectors are provisioned in Stage 3 after Stage 2 authorization.
planned_connectors = ["workspace"]
```

In `.gitignore`:
```gitignore
# Environment & Helper Secret Files
.env
.env.*
```

### Discovery Engine Integration Details
- **Google Workspace (`workspace`):** Real-time federated intranet search across Gmail, Drive, Calendar, and Chat under user OAuth identity via Domain-Wide Delegation.
- **Atlassian Jira Cloud (`jira`):** Federated search across Jira Cloud issues, comments, attachments, and worklogs via OAuth 2.0 (3LO).
- **People & Org Directory (`people_directory`):** Employee profiles, reporting structures, organizational hierarchy, and team search indexed via Workspace Directory API scopes.

### Acceptance Criteria
- [ ] `git branch --show-current` is `feat/interactive-connector-onboarding`.
- [ ] `.github/issues/05_interactive_connector_onboarding.md` created following repository template.
- [ ] `scripts/create_github_issues.sh` registers issue `05` and supports targeted publishing (e.g. `bash scripts/create_github_issues.sh 05`).
- [ ] `variables.tf` declares `planned_connectors` with validation, and `terraform.tfvars.example` specifies `planned_connectors = ["workspace"]`.
- [ ] `.gitignore` ignores `.env` and `.env.*`.
- [ ] `scripts/configure.py` implemented with 100% Python standard library (no external `pip` dependencies).
- [ ] `python3 scripts/configure.py --check --json` outputs `interactive_questions` schema with Help Center URLs.
- [ ] `python3 scripts/configure.py --apply-json '<json>'` safely updates `terraform.tfvars` with Stage 0 safety guards (`enable_* = false`).
- [ ] Mode B terminal combo-box provides `[↑/↓]` arrow-key navigation and spacebar selection with non-TTY numbered fallback and inline `?` guide.
- [ ] `scripts/configure.py --enable-connectors` validates prerequisites and flips `enable_* = true`.
- [ ] `scripts/status.py` integrates Stage 0 configure guidance and `interactive_questions` in `--json`, and Stage 2 planned connectors guidance.
- [ ] `Makefile` provides `configure`, `check-inputs`, and `enable-connectors` targets.
- [ ] `RUNBOOK.md` preserves all 5 contract subheadings and includes Connector Help Center reference table.
- [ ] `AGENTS.md` adds combo-box protocol and hand-off templates while remaining `<= 150` lines.
- [ ] All unit, contract, and data scrubbing tests pass with 0 errors in `make test`.
