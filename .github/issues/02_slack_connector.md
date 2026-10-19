---
title: "feat(connector): Support Slack Enterprise Data Connector"
priority: "P2 - Medium-High"
labels: ["enhancement", "connector", "priority:p2", "collaboration"]
---

### Summary
Add **Slack Enterprise (Grid / Workspace)** data connector support to Prism, enabling conversational chat indexing across public channels, shared team spaces, canvases, threads, and authorized file attachments into Gemini Enterprise.

This brings asynchronous conversational context and real-time team decisions into the unified intranet search and assistant experience.

### Priority
**P2 - Medium-High** (Rank #2 in planned connector pipeline)

### Target Entities
- [x] **Public Channels:** General, announce, team channels, channel topics and purposes
- [x] **Channel Messages & Threads:** Full message body, threaded replies, timestamps, emoji reactions
- [x] **Slack Canvases:** Rich-text team wiki and project overview documents attached to channels
- [x] **Files & Snippets:** Uploaded docs, markdown snippets, PDFs, and code clips
- [x] **User Metadata:** Slack user handles, display names, bot user mappings

### Authentication & Authorization
- **Primary Auth Mode:** Slack App OAuth 2.0 / Bot User OAuth Token (`xoxb-`) or User Token (`xoxp-`).
- **Slack App Scopes:**
  - `channels:read`
  - `channels:history`
  - `groups:read` (for private channels where the bot is invited)
  - `groups:history`
  - `files:read`
  - `users:read`
  - `users:read.email` (for identity mapping to Cloud Identity / Google Workspace accounts)
- **Security & Privacy Safeguards:** Explicit channel whitelist/blacklist to avoid crawling sensitive HR or executive channels.

### Proposed Terraform Configuration Architecture
```hcl
variable "enable_slack_connector" {
  description = "Whether to provision the Slack connector per environment"
  type        = bool
  default     = false
}

variable "slack_config" {
  description = "Configuration parameters for Slack ingestion"
  type = object({
    team_id                      = optional(string, "")
    channels_include             = optional(list(string), []) # Whitelist channel IDs
    channels_exclude             = optional(list(string), []) # Blacklist channel IDs
    include_private_channels     = optional(bool, false)
    entities                     = optional(list(string), ["channel", "message", "thread", "canvas", "file"])
    refresh_interval             = optional(string, "43200s") # 12-hour full crawl
    incremental_refresh_interval = optional(string, "1800s")  # 30-min incremental sync
    sync_mode                    = optional(string, "INCREMENTAL")
  })
  default = {}
}

variable "slack_auth" {
  description = "Slack Bot credentials and OAuth tokens"
  type = object({
    bot_token     = optional(string, "")
    client_id     = optional(string, "")
    client_secret = optional(string, "")
  })
  default   = {}
  sensitive = true
}
```

### Discovery Engine Integration Details
- **Collection ID:** `slack-collection`
- **Data Source Name:** `slack`
- **Identity Mapping:** Cross-references `users:read.email` against Cloud Identity User Store so search results respect channel membership visibility.

### Acceptance Criteria
- [ ] Variables defined in `variables.tf` and exported in `outputs.tf`.
- [ ] Ingestion schema properly formats conversational threads and parent-child message relationships.
- [ ] Privacy controls: Whitelist validation and automatic exclusion of direct messages (DMs/MPDMs) unless explicitly opted in.
- [ ] Terraform plan successfully verifies connector metadata and Secret Manager bindings.
