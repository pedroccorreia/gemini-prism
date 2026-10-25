# Prism — Connectors Roadmap & Feature Pipeline

This document defines the authoritative prioritized roadmap for planned enterprise data connectors in **Gemini Prism**.

Prism unifies disparate enterprise knowledge systems into **Google Gemini Enterprise (Vertex AI Search / Discovery Engine)** through automated, multi-environment Terraform IaC.

---

## Connector Priority Matrix

| Priority | Connector | Target System | Ingestion Scope / Entities | Auth Architecture | Target Release | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Current** | **Google Workspace** | Google Workspace | Gmail, Calendar, Drive, Chat | Domain-Wide Delegation (DWD) | `v1.0.0` | 🟢 **GA (Shipped)** |
| **Current** | **Atlassian Jira** | Jira Cloud / Data Center | Projects, Issues, Comments, Attachments, Worklogs | OAuth 2.0 (3LO) / API Token | `v1.1.0` | 🟢 **GA (Shipped)** |
| **Current** | **People Directory** | Google Cloud Identity / Workspace | User Profiles, Org Chart, Manager Hierarchy, Offices | Discovery Engine DWD SA | `v1.2.0` | 🟢 **GA (Shipped)** |
| **Current** | **Atlassian Confluence** | Confluence Cloud / DC | Spaces, Pages, Blogposts, Attachments, Comments (Federated Cloud v4 / DC v1) | OAuth 2.0 (3LO) / DC Basic Auth / Jira Fallback | `v1.3.0` | 🟢 **GA (Shipped)** |
| **Current** | **Slack Enterprise** | Slack Enterprise Grid / Workspace | Conversations, Messages, Files + MCP Actions (`FEDERATED`) | Google-Managed OAuth 2.0 / BYO App (`v3`) | `v1.4.0` | 🟢 **GA (Shipped)** |
| **P3 (Medium)** | **HubSpot CRM** | HubSpot Cloud | Contacts, Companies, Deals, Tickets, Engagements | Private App Token / OAuth | `v1.5.0` | 📋 **Accepted / Backlog** |

---

## Detailed Specifications

### 1. Atlassian Confluence Connector (Shipped GA)
- **Repository Issue:** [.github/issues/01_confluence_connector.md](../.github/issues/01_confluence_connector.md)
- **Objective:** Ingest and federate Confluence spaces, technical architecture documentation, runbooks, and team wikis.
- **Architectural Mode:** Native **`FEDERATED`** mode via Discovery Engine Confluence v4 (Cloud) and v1 (Data Center) — real-time queries with zero persistent data duplication.
- **Synergies:** Directly reuses Atlassian OAuth / API token credential handling built for Jira; automatically falls back to `jira_auth` and `jira_config.instance_uri` in shared tenant topologies.
- **Collection ID:** `confluence-federated-collection`
- **Status:** 🟢 **Shipped (v1.3.0)** — Configurable via `enable_confluence_connector`, `confluence_auth`, and `confluence_config` with helper `make confluence-checklist`.

### 2. Slack Enterprise Connector (Shipped GA)
- **Repository Issue:** [.github/issues/02_slack_connector.md](../.github/issues/02_slack_connector.md)
- **Objective:** Federate conversational team chat, message threads, channel canvases, shared files, and remote MCP actions (`https://mcp.slack.com`).
- **Architectural Mode:** Native **`FEDERATED`** + **`ACTIONS`** mode via Discovery Engine Slack `v3` (`PUBLIC_GA`) with Google-Managed OAuth 2.0 or BYO Slack App (`ByoOAuth`).
- **Privacy Controls:** Strict channel inclusion/exclusion filters, private-channel/DM opt-in guards, and per-user Slack OAuth identity enforcement.
- **Collection ID:** `slack-collection`
- **Status:** 🟢 **Shipped (v1.4.0)** — Configurable via `enable_slack_connector`, `slack_auth`, and `slack_config` with helper `make slack-checklist`.

### 3. [P3] HubSpot CRM Connector
- **Repository Issue:** [.github/issues/03_hubspot_connector.md](../.github/issues/03_hubspot_connector.md)
- **Objective:** Enable conversational retrieval over CRM accounts, pipeline stages, deals, and support tickets.
- **Security:** Ingestion of Private App tokens via GCP Secret Manager.
- **Collection ID:** `hubspot-collection`

### 4. Google People & Org Directory Connector (Shipped GA)
- **Repository Issue:** [.github/issues/04_people_directory_connector.md](../.github/issues/04_people_directory_connector.md)
- **Objective:** Provide conversational org-chart navigation, manager hierarchies, and talent discovery.
- **Advantage:** Requires **zero new credentials**; reuses the existing Discovery Engine DWD client ID and Directory Admin scopes.
- **Collection ID:** `people-directory-collection`
- **Status:** 🟢 **Shipped (v1.2.0)** — Configurable via `enable_people_directory_connector` and `people_directory_config`.

---

## Creating These Issues on GitHub

To publish these feature requests directly to GitHub issues on `pedroccorreia/gemini-prism`:

```bash
# Run the automated issue creation script
bash scripts/create_github_issues.sh
```
