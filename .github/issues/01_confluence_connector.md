---
title: "feat(connector): Support Atlassian Confluence Data Connector"
priority: "P1 - High"
labels: ["enhancement", "connector", "priority:p1", "atlassian"]
---

### Summary
Add native **Atlassian Confluence** data connector support to Prism, enabling automated ingestion of Confluence spaces, documentation pages, blog posts, comments, and attachments into Gemini Enterprise (Vertex AI Search / Discovery Engine).

As an essential companion to the existing Atlassian Jira connector, Confluence represents the primary unstructured technical knowledge base for enterprise engineering and product organizations.

### Priority
**P1 - High** (Rank #1 in planned connector pipeline)

### Target Entities
- [x] **Spaces:** Space metadata, key, permissions, descriptions
- [x] **Pages:** Full-text HTML/storage format, title, author, version history, labels
- [x] **Blog Posts:** News updates, announcements, release notes
- [x] **Attachments:** PDFs, Word docs, presentations, images indexed via multimodal parsers
- [x] **Comments:** Page inline comments and discussion threads

### Authentication & Authorization
- **Primary Auth Mode:** Atlassian Cloud OAuth 2.0 (3LO) with offline refresh token.
- **Alternative Mode:** Atlassian API Token (`BASIC_AUTH` using `user_account` + `api_token`).
- **Required Atlassian Scopes:**
  - `read:confluence-content.all`
  - `read:confluence-space.summary`
  - `read:confluence-user`
  - `offline_access`
- **Secret Management:** Integration with GCP Secret Manager for `client_secret` and `refresh_token` rotation.

### Proposed Terraform Configuration Architecture
```hcl
variable "enable_confluence_connector" {
  description = "Whether to provision the Atlassian Confluence connector per environment"
  type        = bool
  default     = false
}

variable "confluence_config" {
  description = "Configuration parameters for Confluence ingestion"
  type = object({
    instance_uri                 = optional(string, "")
    space_keys_include           = optional(list(string), [])
    space_keys_exclude           = optional(list(string), [])
    entities                     = optional(list(string), ["space", "page", "blogpost", "attachment", "comment"])
    refresh_interval             = optional(string, "86400s") # Daily full crawl
    incremental_refresh_interval = optional(string, "3600s")  # Hourly incremental
    sync_mode                    = optional(string, "INCREMENTAL")
  })
  default = {}
}

variable "confluence_auth" {
  description = "Authentication credentials for Atlassian Confluence"
  type = object({
    auth_type     = optional(string, "OAUTH") # OAUTH or BASIC_AUTH
    client_id     = optional(string, "")
    client_secret = optional(string, "")
    refresh_token = optional(string, "")
    user_account  = optional(string, "")
    api_token     = optional(string, "")
  })
  default   = {}
  sensitive = true
}
```

### Discovery Engine Integration Details
- **Collection ID:** `confluence-collection`
- **Data Source Name:** `confluence`
- **Data Store Schema:** Document-level ACLs preserving Confluence space and page view restrictions to mirror user permissions.

### Acceptance Criteria
- [ ] Variables defined in `variables.tf` and exported in `outputs.tf`.
- [ ] `main.tf` dynamic locals merge Confluence into `environment_connectors`.
- [ ] Automated validation in `scripts/plan_guard.py` ensuring Confluence secrets are non-empty when enabled.
- [ ] Documentation updated in `RUNBOOK.md` and `PRACTITIONERS_GUIDE.md` with Confluence OAuth consent instructions.
- [ ] Successful dry-run `terraform plan` on `dev` and `non-prod` environments.
