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

variable "planned_connectors" {
  type        = list(string)
  description = "List of enterprise connectors planned for deployment (workspace, jira, confluence, people_directory)"
  default     = ["workspace"]

  validation {
    condition = alltrue([
      for c in var.planned_connectors : contains(["workspace", "jira", "confluence", "people_directory"], c)
    ])
    error_message = "Each element of planned_connectors must be one of: 'workspace', 'jira', 'confluence', 'people_directory'."
  }
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
    collection_id                = optional(string, "jira-federated-collection")
    data_source                  = optional(string, "jira")
    data_source_version          = optional(number, null)
    connector_modes              = optional(list(string), ["FEDERATED"])
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

  validation {
    condition     = contains(coalesce(var.jira_config.connector_modes, ["FEDERATED"]), "FEDERATED") && !contains(coalesce(var.jira_config.connector_modes, ["FEDERATED"]), "DATA_INGESTION")
    error_message = "All connectors must use FEDERATED mode (connector_modes = [\"FEDERATED\"])."
  }
}

variable "enable_people_directory_connector" {
  type        = bool
  description = "Whether to provision the Google Cloud Identity / Workspace People & Org Directory Discovery Engine data connector. Set to true after Domain-Wide Delegation is authorized."
  default     = false
}

variable "people_directory_config" {
  type = object({
    data_source             = optional(string, "native_cloud_identity")
    collection_id           = optional(string, "people-directory-collection")
    display_name            = optional(string, "Google People Directory")
    include_suspended_users = optional(bool, false)
    org_units_include       = optional(list(string), []) # Target specific OUs (e.g. /Employees)
    custom_schemas_include  = optional(list(string), []) # Include custom employee attributes
    refresh_interval        = optional(string, "86400s") # Daily synchronization
    sync_mode               = optional(string, "PERIODIC")
    entities                = optional(list(string), ["users"])
    auto_run_disabled       = optional(bool, false)
  })
  description = "Configuration parameters for Google Cloud Identity / Workspace People & Org Directory data connector"
  default     = {}

  validation {
    condition     = contains(["native_cloud_identity", "google_people_directory", "people_directory"], coalesce(var.people_directory_config.data_source, "native_cloud_identity"))
    error_message = "people_directory_config.data_source must be 'native_cloud_identity', 'google_people_directory', or 'people_directory'."
  }
}

variable "enable_confluence_connector" {
  type        = bool
  description = "Whether to provision the Atlassian Confluence Discovery Engine data connector. Set to true after Confluence OAuth/API credentials are configured."
  default     = false
}

variable "confluence_auth_type" {
  type        = string
  description = "Authentication method for Confluence connector: 'OAUTH' (or 'OAUTH2'), 'BASIC_AUTH' (or 'API_TOKEN'), or 'OAUTH_TWO_LEGGED'"
  default     = "OAUTH"

  validation {
    condition     = contains(["OAUTH", "OAUTH2", "BASIC_AUTH", "API_TOKEN", "OAUTH_TWO_LEGGED"], var.confluence_auth_type)
    error_message = "confluence_auth_type must be one of 'OAUTH', 'OAUTH2', 'BASIC_AUTH', 'API_TOKEN', or 'OAUTH_TWO_LEGGED'."
  }
}

variable "confluence_auth" {
  type = object({
    user_account  = optional(string, "")
    api_token     = optional(string, "")
    client_id     = optional(string, "")
    client_secret = optional(string, "")
    instance_id   = optional(string, "")
    refresh_token = optional(string, "")
  })
  description = "Sensitive authentication credentials for Confluence connector (pass via TF_VAR_confluence_auth environment variable; falls back to TF_VAR_jira_auth when omitted)"
  default     = {}
  sensitive   = true
}

variable "confluence_config" {
  type = object({
    instance_uri                 = optional(string, "")
    instance_id                  = optional(string, "")
    collection_id                = optional(string, "confluence-federated-collection")
    data_source                  = optional(string, "confluence")
    data_source_version          = optional(number, null)
    connector_modes              = optional(list(string), ["FEDERATED"])
    sync_mode                    = optional(string, "PERIODIC")
    refresh_interval             = optional(string, "86400s")
    incremental_refresh_interval = optional(string, "3600s")
    entities                     = optional(list(string), ["space", "page", "blog", "attachment", "comment"])
    static_ip_enabled            = optional(bool, false)
    enable_actions               = optional(bool, false)
    enabled_actions              = optional(list(string), ["create_page", "update_page", "create_blogpost", "create_space", "upload_attachment", "download_attachment"])
    space_keys_include           = optional(list(string), [])
    space_keys_exclude           = optional(list(string), [])
    auto_run_disabled            = optional(bool, false)
    incremental_sync_disabled    = optional(bool, false)
    extra_params                 = optional(map(string), {})
  })
  description = "Configuration for the Atlassian Confluence data connector"
  default     = {}

  validation {
    condition     = contains(["confluence", "confluence_server"], coalesce(var.confluence_config.data_source, "confluence"))
    error_message = "confluence_config.data_source must be 'confluence' or 'confluence_server'."
  }

  validation {
    condition     = contains(coalesce(var.confluence_config.connector_modes, ["FEDERATED"]), "FEDERATED") && !contains(coalesce(var.confluence_config.connector_modes, ["FEDERATED"]), "DATA_INGESTION")
    error_message = "All connectors must use FEDERATED mode (connector_modes = [\"FEDERATED\"])."
  }
}

