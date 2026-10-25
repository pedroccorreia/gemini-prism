# Test Suite Readiness Report (`TEST_READY.md`)

## 1. Overview & Execution Command

The Gemini Prism Red Team Adversarial, Negative, and Contract Test Harness (`scripts/test_red.py`) has been expanded to validate all deliverables for the Interactive Connector Onboarding Wizard and Terraform Input Variable Configuration Engine.

### Test Runner Commands
```bash
# Unified gate (Runs all 69 unit/integration/contract tests, terraform fmt, terraform validate):
make test

# Standalone Red Team test harness:
python3 scripts/test_red.py

# Focused test runs by class:
python3 -m unittest scripts.test_red.TestConfigureCLI -v
python3 -m unittest scripts.test_red.TestConfigureInteractive -v
python3 -m unittest scripts.test_red.TestStatusConfigIntegration -v
python3 -m unittest scripts.test_red.TestBranchAndIssueContracts -v
python3 -m unittest scripts.test_red.TestDataScrubbing -v
python3 -m unittest scripts.test_red.TestDocumentationContracts -v
```

### Current Status
- **Total Tests:** 69 (46 baseline + 23 new test cases)
- **Total Classes:** 12 `unittest.TestCase` classes
- **Execution Time:** ~1.0s
- **Pass Rate:** 100% (69 passed, 0 failed, 0 errors, 0 skipped)
- **Data Scrubbing Leaks:** 0 across all git-tracked files
- **Terraform Formatting & Validation:** 100% compliant (`terraform fmt -check`, `terraform validate`)

---

## 2. Test Suite Architecture & Tiers

The test harness operates on 100% Python standard library (`unittest`, `subprocess`, `tempfile`, `json`, `re`, `io`, `os`, `sys`) with zero external `pip` dependencies.

| Tier | Test Class | Test Count | Description & Invariants Verified |
|---|---|:---:|---|
| **Tier 1** | `TestConfigureCLI` | 11 | Mode A CLI & schema validation: `--check` exit 1 on missing inputs, `--check --json` schema compliance, `interactive_questions` contract with Help Center URLs, idempotent `--apply-json`, malformed JSON rejection, invalid connector rejection, `--connectors` and `--set` flags, Stage 0 safety guard (`enable_* = false`), Stage 0 refusal of `--enable-connectors`, and Stage 2 clean enablement. |
| **Tier 2** | `TestConfigureInteractive` | 4 | Mode B terminal UI & non-TTY fallback: numbered fallback with piped stdin (`"1,2\n"`), inline boxed help (`"?"`) rendering console links and Help Center guides, default newline acceptance (`"\n"`), and direct `print_boxed_help` verification. |
| **Tier 3** | `TestStatusConfigIntegration` | 5 | Integration with `scripts/status.py`: Stage 0 guidance pointing to `make configure` and `make check-inputs`, Stage 0 `--json` embedding `interactive_questions` array, Stage 2 validation of `planned_connectors`, human gate guidance to `make enable-connectors`, non-list rejection, and unknown connector rejection. |
| **Tier 4** | `TestBranchAndIssueContracts` | 3 | Git repository & GitHub automation contracts: `git branch --show-current` == `feat/interactive-connector-onboarding`, `.github/issues/05_interactive_connector_onboarding.md` frontmatter & section headings contract, and `scripts/create_github_issues.sh` registration of `ISSUES["05"]` with targeted arguments (`05`, `5`) and invalid key rejection (`99`). |
| **Baseline** | `TestAllocateLicensesNegative` | 5 | Negative tests for license allocation: missing config, malformed JSON, project number mismatch, capacity exhaustion, and dry-run safety. |
| **Baseline** | `TestPlanGuard` | 6 | Plan guard safety tests: rejection of deletions/replacements, override via `ALLOW_DESTROY=1`, and allowance of creations/updates. |
| **Baseline** | `TestStatusPhaseDetection` | 17 | Core phase detection across Phase 0-5: tools check, ADC identity check, missing tfvars, placeholder detection, state mismatch protection, DWD/Jira/Directory human gates, and nested tfvars preservation. |
| **Baseline** | `TestVerifyConnectors` | 6 | Data connector verification: multi-entity Jira, People Directory, error reporting, and blocking reasons warnings. |
| **Baseline** | `TestDocumentationContracts` | 3 | Documentation contracts: `RUNBOOK.md` 5 mandatory subheadings across all stages, `AGENTS.md` `<= 150` lines and hand-off templates, and relative link resolution. |
| **Baseline** | `TestTerraformDefaultsContract` | 4 | Terraform defaults and scopes: null defaults for folder/SA, People Directory enablement default, Directory API DWD scopes. |
| **Baseline** | `TestVerifyWaitParsing` | 3 | Wait duration parsing: valid formats, malformed duration errors, CLI abort on invalid duration. |
| **Baseline** | `TestDataScrubbing` | 2 | Red Team Data Scrubbing across all `git ls-files` ensuring 0 leaked customer identifiers, domains, or real IDs. |

---

## 3. Feature Coverage Checklist

| Requirement | Feature Description | Test Coverage | Status |
|---|---|---|:---:|
| **R1.1** | Feature branch `feat/interactive-connector-onboarding` checked out | `TestBranchAndIssueContracts.test_git_branch_contract` | PASS |
| **R1.2** | Structured issue spec `05_interactive_connector_onboarding.md` created with frontmatter & standard headings | `TestBranchAndIssueContracts.test_issue_05_specification_contract` | PASS |
| **R1.3** | `scripts/create_github_issues.sh` registers `ISSUES["05"]` and supports targeted arguments (`05`, `5`) & rejection (`99`) | `TestBranchAndIssueContracts.test_create_github_issues_script_registration_and_args` | PASS |
| **R2.1** | `planned_connectors` declared in `variables.tf` with validation and in `terraform.tfvars.example` | `terraform validate`, `TestTerraformDefaultsContract` | PASS |
| **R2.2** | `.gitignore` ignores `.env` and `.env.*` helper credentials | Tested in repository hygiene & git status | PASS |
| **R3.1** | Zero-dependency implementation in `scripts/configure.py` | 100% Python standard library (`import` inspection & test suite) | PASS |
| **R3.2** | Mode A: `--check --json` outputs `interactive_questions` with `is_multi_select: true` and Help Center URLs | `TestConfigureCLI.test_configure_check_json_emits_valid_schema`, `test_configure_interactive_questions_contract` | PASS |
| **R3.3** | Mode A: `--apply-json '<json>'` updates `terraform.tfvars` idempotently without duplicates | `TestConfigureCLI.test_configure_apply_json_valid_updates_tfvars_idempotently` | PASS |
| **R3.4** | Mode A: CLI flags `--connectors` and `--set key=val` update `terraform.tfvars` cleanly | `TestConfigureCLI.test_configure_cli_flags_connectors_and_set` | PASS |
| **R3.5** | Mode A: Negative tests for malformed JSON and invalid connector names | `TestConfigureCLI.test_configure_apply_json_malformed_json_exits_1`, `test_configure_apply_json_invalid_connector_exits_1` | PASS |
| **R3.6** | Stage 0 Safety Guard: applying `enable_connectors: true` forces `enable_* = false` while saving `planned_connectors` | `TestConfigureCLI.test_configure_stage_0_safety_guard_forces_enable_false` | PASS |
| **R3.7** | Missing Variable Audit (`--check` / `make check-inputs`): table with Admin URLs, lookup commands, IAM roles, and docs URLs | `TestConfigureCLI.test_configure_check_missing_inputs_returns_exit_1`, `test_configure_check_success_when_all_variables_configured` | PASS |
| **R3.8** | Stage 2 Enablement Helper: refuses in Stage 0, cleanly flips `enable_* = true` in Stage 2 with satisfied prerequisites | `TestConfigureCLI.test_configure_enable_connectors_stage_0_refusal`, `test_configure_enable_connectors_stage_2_success` | PASS |
| **R3.9** | Mode B: Non-TTY piped input (`"1,2\n"`) accepts selections and default (`"\n"`) | `TestConfigureInteractive.test_mode_b_non_tty_fallback_piped_selection`, `test_mode_b_accepts_default_on_empty_newline` | PASS |
| **R3.10** | Mode B: Inline `?` help prompt renders boxed "Where to find this" guide with console links and Help Center docs | `TestConfigureInteractive.test_mode_b_inline_help_prompt`, `test_print_boxed_help_output` | PASS |
| **R4.1** | Stage 0 `status.py` points `next_action` to `make configure` and `make check-inputs` | `TestStatusConfigIntegration.test_status_stage_0_next_action_references_configure_and_check_inputs` | PASS |
| **R4.2** | Stage 0 `status.py --json` embeds `interactive_questions` array | `TestStatusConfigIntegration.test_status_stage_0_json_embeds_interactive_questions` | PASS |
| **R4.3** | Stage 2 `status.py` validates `planned_connectors` and guides operator to `make enable-connectors` | `TestStatusConfigIntegration.test_status_stage_2_planned_connectors_guidance` | PASS |
| **R4.4** | Stage 2 `status.py` rejects non-list and invalid connectors in `planned_connectors` | `TestStatusConfigIntegration.test_status_stage_2_rejects_non_list_planned_connectors`, `test_status_stage_2_rejects_invalid_planned_connector` | PASS |
| **R4.5** | `Makefile` provides `configure`, `check-inputs`, `enable-connectors` targets and updated `help` | Verified via `make check-inputs`, `make test` | PASS |
| **R5.1** | `RUNBOOK.md` preserves all 5 contract subheadings across all stages and includes Connector Help Center table | `TestDocumentationContracts.test_runbook_stages_headings_contract` | PASS |
| **R5.2** | `AGENTS.md` adds Stage 0 combo-box protocol and hand-off templates while remaining `<= 150` lines | `TestDocumentationContracts.test_agents_md_contract` (116 lines) | PASS |
| **R5.3** | Relative documentation links resolve across `README.md`, `RUNBOOK.md`, `AGENTS.md` | `TestDocumentationContracts.test_relative_markdown_links` | PASS |
| **Security** | Zero data scrubbing leaks across git-tracked files | `TestDataScrubbing.test_no_leaks_in_tracked_files` (0 leaks) | PASS |
