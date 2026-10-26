.PHONY: status configure check-inputs enable-connectors plan-foundation apply-foundation dwd-checklist jira-checklist confluence-checklist slack-checklist people-checklist hubspot-checklist plan-connectors apply-connectors licenses-dryrun licenses licenses-list verify test help

WAIT ?= 15m

help:
	@echo ""
	@echo "  ═══╗  ╱╲"
	@echo "  ═══╬─╱  ╲──✦   P R I S M   │ Gemini Enterprise Provisioning Engine"
	@echo "  ═══╝╱____╲     v1.0        │ Workspace · Jira · Confluence · Slack · HubSpot · Identity · Licensing"
	@echo ""
	@echo "Available targets:"
	@echo "  status               - Check deployment status & live phase"
	@echo "  configure            - Run interactive connector onboarding & configuration wizard"
	@echo "  check-inputs         - Audit Terraform inputs, missing variables, and Help Center links"
	@echo "  enable-connectors    - Validate prerequisites and enable planned connectors for Stage 3"
	@echo "  plan-foundation      - Generate Stage 1 Foundation plan with plan guard"
	@echo "  apply-foundation     - Apply Stage 1 Foundation plan (0 deletes/replaces)"
	@echo "  dwd-checklist        - Print Google Workspace Domain-Wide Delegation authorization checklist"
	@echo "  jira-checklist       - Print Atlassian Jira connector onboarding checklist"
	@echo "  confluence-checklist - Print Atlassian Confluence connector onboarding checklist"
	@echo "  slack-checklist      - Print Slack Enterprise connector onboarding checklist"
	@echo "  people-checklist     - Print Google People Directory connector onboarding checklist"
	@echo "  hubspot-checklist    - Print HubSpot CRM connector onboarding checklist"
	@echo "  plan-connectors      - Generate Stage 3 Connectors & Engines plan with plan guard"
	@echo "  apply-connectors     - Apply Stage 3 Connectors & Engines plan"
	@echo "  licenses-dryrun      - Dry-run license distribution preflight assertions"
	@echo "  licenses             - Distribute subscription seats to customer environment projects"
	@echo "  licenses-list        - List active license allocations and seat quotas"
	@echo "  verify               - Run post-deployment verification (WAIT=$(WAIT))"
	@echo "  test                 - Run test harness and Terraform validation"

status:
	python3 scripts/status.py $(ARGS)

configure:
	python3 scripts/configure.py $(ARGS)

check-inputs:
	python3 scripts/configure.py --check $(ARGS)

enable-connectors:
	python3 scripts/configure.py --enable-connectors $(ARGS)

plan-foundation:
	@mkdir -p .plans
	terraform plan -input=false -var="enable_connectors=false" -var="enable_jira_connector=false" -var="enable_confluence_connector=false" -var="enable_slack_connector=false" -var="enable_people_directory_connector=false" -var="enable_hubspot_connector=false" -out=.plans/foundation.tfplan
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

slack-checklist:
	@python3 scripts/status.py --slack-checklist

people-checklist:
	@python3 scripts/status.py --people-directory-checklist

hubspot-checklist:
	@python3 scripts/status.py --hubspot-checklist

plan-connectors:
	@mkdir -p .plans
	terraform plan -input=false -out=.plans/connectors.tfplan
	python3 scripts/plan_guard.py .plans/connectors.tfplan

apply-connectors:
	python3 scripts/plan_guard.py .plans/connectors.tfplan
	terraform apply -input=false .plans/connectors.tfplan

licenses-dryrun:
	python3 scripts/allocate_licenses.py --distribute --dry-run

licenses: licenses-dryrun
	python3 scripts/allocate_licenses.py --distribute

licenses-list:
	python3 scripts/allocate_licenses.py --list

verify:
	python3 scripts/verify.py --wait $(WAIT)

test:
	python3 scripts/test_red.py
	terraform fmt -check
	terraform validate
