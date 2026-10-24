variable "project_id_prefix" {
  type        = string
  description = "An optional prefix to prepend to each customer project ID to ensure global uniqueness"
  default     = ""
}

variable "customer_id" {
  type        = string
  description = "Short identifier/slug for the customer (used in project IDs and resource names, e.g. acme)"
}

variable "customer_name" {
  type        = string
  description = "The human-readable display name of the customer (e.g. Acme Corp)"
}

variable "environments" {
  type        = set(string)
  description = "Configurable list/set of environments to provision for the customer (e.g. ['non-prod', 'prod'] or ['dev', 'pilot', 'prod'])"
  default     = ["non-prod", "prod"]

  validation {
    condition     = length(var.environments) > 0
    error_message = "At least one environment must be specified in var.environments."
  }
}

variable "location" {
  type        = string
  description = "The location for the Discovery Engine resources (e.g., global, us, eu)"
  default     = "global"
}

variable "company_domain" {
  type        = string
  description = "The primary domain name for the Google Workspace tenant (e.g., example.com)"
}

variable "workspace_customer_id" {
  type        = string
  description = "The Google Workspace Customer ID (e.g., C01234567)"
}

variable "workspace_admin_email" {
  type        = string
  description = "The email address of a Google Workspace Administrator (optional)"
  default     = null
}

variable "folder_id" {
  type        = string
  description = "The ID of the GCP Folder where projects should be created (optional). If omitted, null, or empty string (\"\"), projects are provisioned directly at the root of the Organization."
  default     = null
}

variable "org_id" {
  type        = string
  description = "The ID of the GCP Organization where the projects should be created (optional, if not using a folder)"
  default     = null
}

variable "billing_account" {
  type        = string
  description = "The billing account ID to associate with the created projects"
}

variable "billing_project" {
  type        = string
  description = "The GCP project ID to use for API quota and billing overrides"
  default     = null
}

variable "sa_email" {
  type        = string
  description = "The email address of a custom GCP service account for provisioning (optional). When omitted or null/empty, active Application Default Credentials (ADC) are used and custom SA IAM grant is skipped."
  default     = null
}

variable "workspace_connectors" {
  type        = set(string)
  description = "Set of Google Workspace connector types to provision (e.g. google_mail, google_calendar, google_drive, google_chat)"
  default     = ["google_mail", "google_calendar", "google_drive", "google_chat"]
}

variable "enable_connectors" {
  type        = bool
  description = "Whether to provision Discovery Engine Workspace data connectors. Set to false for initial foundation apply, then true after Domain-Wide Delegation is authorized."
  default     = false
}

variable "assistant_instructions" {
  type        = string
  description = "System instruction / prompt preamble for the Gemini Enterprise assistant"
  default     = "You are an enterprise AI assistant helping employees find information across Google Workspace and internal knowledge bases. Provide accurate, helpful, and concise answers based on available enterprise data."
}

variable "seat_allocations" {
  type        = map(number)
  description = "Map of environment names to seat counts allocated (e.g. { prod = 4, non-prod = 1 })"
  default = {
    prod     = 4
    non-prod = 1
  }
}

variable "license_config_names" {
  type        = map(string)
  description = "Optional map of environment name to full license config resource name (e.g. projects/{project}/locations/{location}/licenseConfigs/{id})"
  default     = {}
}

variable "license_config_id" {
  type        = string
  description = "The Billing Account License Config ID for Gemini Enterprise"
  default     = ""
}

variable "subscription_id" {
  type        = string
  description = "The Gemini Enterprise subscription ID"
  default     = ""
}

variable "subscription_tier" {
  type        = string
  description = "The Gemini Enterprise subscription tier"
  default     = "Gemini Enterprise Standard"
}

variable "enable_jira_connector" {
  type        = bool
  description = "Whether to provision the Atlassian Jira Discovery Engine data connector. Set to true after Jira OAuth/API credentials are configured."
  default     = false
}

variable "jira_auth_type" {
  type        = string
  description = "Authentication method for Jira connector: 'OAUTH' (or 'OAUTH2'), 'BASIC_AUTH' (or 'API_TOKEN'), or 'OAUTH_TWO_LEGGED'"
  default     = "OAUTH"

  validation {
    condition     = contains(["OAUTH", "OAUTH2", "BASIC_AUTH", "API_TOKEN", "OAUTH_TWO_LEGGED"], var.jira_auth_type)
    error_message = "jira_auth_type must be one of 'OAUTH', 'OAUTH2', 'BASIC_AUTH', 'API_TOKEN', or 'OAUTH_TWO_LEGGED'."
  }
}

variable "jira_auth" {
  type = object({
    user_account  = optional(string, "")
    api_token     = optional(string, "")
    client_id     = optional(string, "")
    client_secret = optional(string, "")
    instance_id   = optional(string, "")
    refresh_token = optional(string, "")
  })
  description = "Sensitive authentication credentials for Jira connector (pass via TF_VAR_jira_auth environment variable)"
  default     = {}
  sensitive   = true
}

variable "jira_config" {
  type = object({
    instance_uri                 = optional(string, "")
    instance_id                  = optional(string, "")
    data_source                  = optional(string, "jira")
    data_source_version          = optional(number, null)
    connector_modes              = optional(list(string), ["DATA_INGESTION"])
    sync_mode                    = optional(string, "PERIODIC")
    refresh_interval             = optional(string, "86400s")
    incremental_refresh_interval = optional(string, "10800s")
    entities                     = optional(list(string), ["project", "issue", "attachment", "comment", "worklog"])
    static_ip_enabled            = optional(bool, false)
    enable_actions               = optional(bool, false)
    enabled_actions              = optional(list(string), ["create_issue", "update_issue", "change_issue_status", "create_comment", "update_comment", "upload_attachment"])
    project_keys_include         = optional(list(string), [])
    project_keys_exclude         = optional(list(string), [])
    auto_run_disabled            = optional(bool, false)
    incremental_sync_disabled    = optional(bool, false)
    extra_params                 = optional(map(string), {})
  })
  description = "Configuration for the Atlassian Jira data connector"
  default     = {}

  validation {
    condition     = contains(["jira", "jira_server"], coalesce(var.jira_config.data_source, "jira"))
    error_message = "jira_config.data_source must be 'jira' or 'jira_server'."
  }
}

variable "enable_slack_connector" {
  type        = bool
  description = "Whether to provision the Slack Enterprise Discovery Engine data connector per environment. Set to true after Slack OAuth/Bot credentials are configured."
  default     = false
}

variable "slack_auth_type" {
  type        = string
  description = "Authentication method for Slack connector: 'OAUTH' (or 'OAUTH2') for v3 federated/actions (Google-managed or BYO app), or 'BOT_TOKEN' ('API_TOKEN' / 'USER_TOKEN') for legacy v1 ingestion"
  default     = "OAUTH"

  validation {
    condition     = contains(["OAUTH", "OAUTH2", "BOT_TOKEN", "USER_TOKEN", "API_TOKEN"], var.slack_auth_type)
    error_message = "slack_auth_type must be one of 'OAUTH', 'OAUTH2', 'BOT_TOKEN', 'USER_TOKEN', or 'API_TOKEN'."
  }
}

variable "slack_auth" {
  type = object({
    bot_token     = optional(string, "")
    user_token    = optional(string, "")
    api_token     = optional(string, "")
    client_id     = optional(string, "")
    client_secret = optional(string, "")
    refresh_token = optional(string, "")
    team_id       = optional(string, "")
  })
  description = "Sensitive authentication credentials for Slack connector (pass via TF_VAR_slack_auth environment variable)"
  default     = {}
  sensitive   = true
}

variable "slack_config" {
  type = object({
    instance_uri                 = optional(string, "")
    team_id                      = optional(string, "")
    data_source                  = optional(string, "slack")
    data_source_version          = optional(number, null)
    connector_modes              = optional(list(string), ["FEDERATED"])
    sync_mode                    = optional(string, "PERIODIC")
    refresh_interval             = optional(string, "43200s")
    incremental_refresh_interval = optional(string, "10800s")
    entities                     = optional(list(string), ["conversation", "message", "file"])
    channels_include             = optional(list(string), [])
    channels_exclude             = optional(list(string), [])
    include_private_channels     = optional(bool, false)
    include_dms                  = optional(bool, false)
    static_ip_enabled            = optional(bool, false)
    enable_actions               = optional(bool, false)
    enabled_actions              = optional(list(string), ["slack_send_message", "slack_schedule_message", "slack_create_canvas", "slack_send_message_draft"])
    auto_run_disabled            = optional(bool, false)
    incremental_sync_disabled    = optional(bool, false)
    extra_params                 = optional(map(string), {})
  })
  description = "Configuration parameters for the Slack Enterprise data connector"
  default     = {}

  validation {
    condition     = coalesce(var.slack_config.data_source, "slack") == "slack"
    error_message = "slack_config.data_source must be 'slack'."
  }
}

