---
title: "feat(connector): Support Google Cloud Identity / Workspace People Directory Connector"
priority: "P4 - Low-Medium"
labels: ["enhancement", "connector", "priority:p4", "google-workspace", "identity"]
---

### Summary
Add a dedicated **Google Cloud Identity / Workspace People & Org Directory** data connector to Prism. While Prism already configures Cloud Identity group bindings and Workspace DWD for Gmail/Drive/Calendar/Chat, this connector indexes the complete enterprise organizational hierarchy, employee profiles, department taxonomy, job titles, reporting lines, skills, and office locations into a dedicated People Data Store.

This powers natural language organizational queries in Gemini Enterprise, such as *"Who manages the APAC Cloud Architecture team?"*, *"Find staff engineers with Kubernetes expertise in London"*, or *"Show me the reporting chain for John Doe"*.

### Priority
**P4 - Low-Medium** (Rank #4 in planned connector pipeline)

### Target Entities
- [x] **User Profiles:** Full name, primary email, alias emails, employee ID, avatar URI
- [x] **Job Architecture:** Job title, department, cost center, division, job level
- [x] **Reporting Lines / Org Hierarchy:** Direct manager email, reporting chain, direct and indirect reports
- [x] **Location & Contact:** Desk/office location, building, city, work phone, time zone
- [x] **Custom User Attributes:** Enterprise skills, projects, certifications, custom schema fields

### Authentication & Authorization
- **Auth Mode:** Reuses the existing **Discovery Engine Service Agent Domain-Wide Delegation (DWD)** configuration!
- **Required Google Workspace Directory Scopes:**
  - `https://www.googleapis.com/auth/admin.directory.user.readonly` (already included in Prism's `dwd_scopes`!)
  - `https://www.googleapis.com/auth/admin.directory.orgunit.readonly`
  - `https://www.googleapis.com/auth/admin.directory.customschema.readonly`
- **Zero Additional Credentials Needed:** Leverages the service account authorization already authorized in Google Workspace Admin Console (`admin.google.com`).

### Proposed Terraform Configuration Architecture
```hcl
variable "enable_people_directory_connector" {
  description = "Whether to provision the Google People Directory connector per environment"
  type        = bool
  default     = false
}

variable "people_directory_config" {
  description = "Configuration parameters for People & Org Directory ingestion"
  type = object({
    include_suspended_users = optional(bool, false)
    org_units_include       = optional(list(string), []) # Target specific OUs (e.g. /Employees)
    custom_schemas_include  = optional(list(string), []) # Include custom employee attributes
    refresh_interval        = optional(string, "86400s") # Daily synchronization
    sync_mode               = optional(string, "INCREMENTAL")
  })
  default = {}
}
```

### Discovery Engine Integration Details
- **Collection ID:** `people-directory-collection`
- **Data Source Name:** `google_people_directory`
- **Entity Schema:** Graph-structured schema supporting hierarchical manager lookups and attribute-based search.

### Acceptance Criteria
- [x] Variables defined in `variables.tf` (`enable_people_directory_connector`, `people_directory_config`) and exported in `outputs.tf` (`people_directory_checklist`).
- [x] Validate that existing DWD client authorization covers all needed Directory API endpoints (`admin.directory.user.readonly`, `admin.directory.orgunit.readonly`, `admin.directory.customschema.readonly`).
- [x] Add query examples in `PRACTITIONERS_GUIDE.md` demonstrating org-search and people-finder conversational queries.
- [x] Automated validation in `scripts/status.py` and `scripts/verify.py` ensuring Directory service agent permissions and connector state are intact.
