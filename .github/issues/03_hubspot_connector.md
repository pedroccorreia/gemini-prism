---
title: "feat(connector): Support HubSpot CRM Data Connector"
priority: "P3 - Medium"
labels: ["enhancement", "connector", "priority:p3", "crm"]
---

### Summary
Add **HubSpot CRM** data connector support to Prism, enabling unified search and generative Q&A across CRM customer accounts, contacts, sales pipelines, deals, customer service tickets, and communication engagements.

This empowers sales, solutions engineering, and account executives to ask Gemini Enterprise questions like *"What is the renewal status and recent meeting notes for Customer X?"* or *"List all open P1 support tickets for Account Y"*.

### Priority
**P3 - Medium** (Rank #3 in planned connector pipeline)

### Target Entities
- [x] **Contacts:** Names, emails, job titles, phone numbers, lifecycle stage
- [x] **Companies / Accounts:** Domain, industry, revenue tier, associated contacts
- [x] **Deals / Pipeline:** Deal name, stage, amount, expected close date, pipeline stage history
- [x] **Tickets:** Support issue title, priority, status, category, resolution notes
- [x] **Engagements:** Meeting summaries, call transcripts, logged email correspondences, customer notes

### Authentication & Authorization
- **Primary Auth Mode:** HubSpot Private App Token or OAuth 2.0 Client Credentials.
- **Required HubSpot Scopes:**
  - `crm.objects.contacts.read`
  - `crm.objects.companies.read`
  - `crm.objects.deals.read`
  - `crm.objects.owners.read`
  - `crm.schemas.contacts.read`
  - `crm.schemas.deals.read`
  - `tickets` (for service ticket reading)

### Proposed Terraform Configuration Architecture
```hcl
variable "enable_hubspot_connector" {
  description = "Whether to provision the HubSpot CRM connector per environment"
  type        = bool
  default     = false
}

variable "hubspot_config" {
  description = "Configuration parameters for HubSpot CRM ingestion"
  type = object({
    portal_id                    = optional(string, "")
    entities                     = optional(list(string), ["contact", "company", "deal", "ticket", "engagement"])
    deal_pipelines_include       = optional(list(string), []) # Filter specific sales pipelines
    refresh_interval             = optional(string, "86400s")
    incremental_refresh_interval = optional(string, "7200s") # 2-hour delta sync
    sync_mode                    = optional(string, "INCREMENTAL")
  })
  default = {}
}

variable "hubspot_auth" {
  description = "HubSpot Private App Access Token or OAuth credentials"
  type = object({
    private_app_token = optional(string, "")
    client_id         = optional(string, "")
    client_secret     = optional(string, "")
    refresh_token     = optional(string, "")
  })
  default   = {}
  sensitive = true
}
```

### Discovery Engine Integration Details
- **Collection ID:** `hubspot-collection`
- **Data Source Name:** `hubspot`
- **Structured Schema:** High-fidelity structured schema mapping for entity relationships (Contact ↔ Company ↔ Deal).

### Acceptance Criteria
- [ ] Variables defined in `variables.tf` and exported in `outputs.tf`.
- [ ] Support both Private App Tokens and OAuth 2.0 flows.
- [ ] Data sanitization & PII controls documented in `RUNBOOK.md`.
- [ ] Secret Manager integration for `private_app_token` storage and runtime injection.
