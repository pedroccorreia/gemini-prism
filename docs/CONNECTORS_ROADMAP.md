# Prism — Connectors Roadmap & Feature Pipeline

This document defines the authoritative prioritized roadmap for planned enterprise data connectors in **Gemini Prism**.

Prism unifies disparate enterprise knowledge systems into **Google Gemini Enterprise (Vertex AI Search / Discovery Engine)** through automated, multi-environment Terraform IaC.

---

## Connector Priority Matrix

| Priority | Connector | Target System | Ingestion Scope / Entities | Auth Architecture | Target Release | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Current** | **Google Workspace** | Google Workspace | Gmail, Calendar, Drive, Chat | Domain-Wide Delegation (DWD) | `v1.0.0` | 🟢 **GA (Shipped)** |
| **Current** | **Atlassian Jira** | Jira Cloud / Data Center | Projects, Issues, Comments, Attachments, Worklogs | OAuth 2.0 (3LO) / API Token | `v1.1.0` | 🟢 **GA (Shipped)** |
| **P1 (High)** | **Atlassian Confluence** | Confluence Cloud / DC | Spaces, Pages, Blogposts, Attachments, Comments | OAuth 2.0 (3LO) / API Token | `v1.2.0` | 📋 **Accepted / Backlog** |
| **P2 (Med-High)** | **Slack Enterprise** | Slack Enterprise Grid | Channels, Messages, Threads, Canvases, Files | Bot User OAuth (`xoxb-`) | `v1.3.0` | 📋 **Accepted / Backlog** |
| **P3 (Medium)** | **HubSpot CRM** | HubSpot Cloud | Contacts, Companies, Deals, Tickets, Engagements | Private App Token / OAuth | `v1.4.0` | 📋 **Accepted / Backlog** |
| **P4 (Low-Med)** | **People Directory** | Google Cloud Identity / Workspace | User Profiles, Org Chart, Manager Hierarchy, Offices | Discovery Engine DWD SA | `v1.5.0` | 📋 **Accepted / Backlog** |

---

## Detailed Specifications

### 1. [P1] Atlassian Confluence Connector
- **Repository Issue:** [.github/issues/01_confluence_connector.md](../.github/issues/01_confluence_connector.md)
- **Objective:** Ingest Confluence spaces, technical architecture documentation, runbooks, and team wikis.
- **Synergies:** Directly reuses Atlassian OAuth / API token credential handling built for the Jira connector.
- **Collection ID:** `confluence-collection`

### 2. [P2] Slack Enterprise Connector
- **Repository Issue:** [.github/issues/02_slack_connector.md](../.github/issues/02_slack_connector.md)
- **Objective:** Index conversational team chat, message threads, channel canvases, and shared files.
- **Privacy Controls:** Strict channel inclusion/exclusion filters with user-account email mapping to Google Cloud Identity.
- **Collection ID:** `slack-collection`

### 3. [P3] HubSpot CRM Connector
- **Repository Issue:** [.github/issues/03_hubspot_connector.md](../.github/issues/03_hubspot_connector.md)
- **Objective:** Enable conversational retrieval over CRM accounts, pipeline stages, deals, and support tickets.
- **Security:** Ingestion of Private App tokens via GCP Secret Manager.
- **Collection ID:** `hubspot-collection`

### 4. [P4] Google People & Org Directory Connector
- **Repository Issue:** [.github/issues/04_people_directory_connector.md](../.github/issues/04_people_directory_connector.md)
- **Objective:** Provide conversational org-chart navigation, manager hierarchies, and talent discovery.
- **Advantage:** Requires **zero new credentials**; reuses the existing Discovery Engine DWD client ID and Directory Admin scopes.
- **Collection ID:** `people-directory-collection`

---

## Creating These Issues on GitHub

To publish these feature requests directly to GitHub issues on `pedroccorreia/gemini-prism`:

```bash
# Run the automated issue creation script
bash scripts/create_github_issues.sh
```
