output "project_ids" {
  description = "The project IDs of the created customer environment projects"
  value       = { for k, v in google_project.projects : k => v.project_id }
}

output "project_numbers" {
  description = "The project numbers of the created customer environment projects"
  value       = { for k, v in google_project.projects : k => v.number }
}

output "user_group_emails" {
  description = "Emails of the provisioned User Cloud Identity Groups per environment"
  value       = { for k, v in google_cloud_identity_group.users : k => v.group_key[0].id }
}

output "service_agent_emails" {
  description = "Discovery Engine Service Agent email addresses per environment"
  value = {
    for k, v in google_project.projects : k =>
    "service-${v.number}@gcp-sa-discoveryengine.iam.gserviceaccount.com"
  }
}

output "data_connector_names" {
  description = "Full resource names of the provisioned Data Connectors per environment"
  value       = { for k, v in google_discovery_engine_data_connector.connectors : k => v.name }
}

output "search_engine_names" {
  description = "Full resource names of the provisioned Search Engines per environment"
  value       = { for k, v in google_discovery_engine_search_engine.engines : k => v.name }
}

output "assistant_names" {
  description = "Full resource names of the provisioned Discovery Engine Assistants per environment"
  value       = { for k, v in google_discovery_engine_assistant.default : k => v.name }
}

output "user_store_names" {
  description = "Full resource names of the provisioned Discovery Engine User Stores per environment"
  value       = { for k, v in google_discovery_engine_user_store.default : k => v.name }
}

output "dwd_checklist" {
  description = "Domain-Wide Delegation (DWD) authorization checklist for Google Workspace Admin Console per environment"
  value = {
    for k, v in local.environments : k => {
      project_id          = google_project.projects[k].project_id
      project_number      = google_project.projects[k].number
      service_agent_email = "service-${google_project.projects[k].number}@gcp-sa-discoveryengine.iam.gserviceaccount.com"
      admin_console_url   = "https://admin.google.com/ac/owl/domainwidedelegation"
      oauth_scopes        = local.dwd_scopes
      oauth_scopes_csv    = join(",", local.dwd_scopes)
      action_instructions = "Add DWD API Client in Google Workspace Admin Console using the 21-digit numeric Client ID (uniqueId) from make dwd-checklist with oauth_scopes_csv."
    }
  }
}

output "jira_checklist" {
  description = "Atlassian Jira connector configuration and onboarding checklist per environment"
  value = {
    for k, v in local.environments : k => {
      project_id                   = google_project.projects[k].project_id
      instance_uri                 = try(coalesce(var.jira_config.instance_uri), "")
      instance_id                  = nonsensitive(local.effective_jira_instance_id)
      auth_type                    = local.effective_jira_auth_type
      data_source_version          = local.effective_jira_version
      oauth_ingestion_callback_url = "https://vertexaisearch.cloud.google.com/console/oauth/jira_oauth.html"
      oauth_actions_callback_url   = "https://vertexaisearch.cloud.google.com/oauth-redirect"
      developer_console_url        = "https://developer.atlassian.com/console/myapps/"
      admin_console_url            = "https://admin.atlassian.com"
      instance_id_help             = "Retrieve your Atlassian Cloud ID UUID via: curl -s https://<site>.atlassian.net/_edge/tenant_info | jq -r .cloudId"
      oauth_scopes = coalesce(var.jira_config.enable_actions, false) ? [
        "read:jira-work",
        "read:jira-user",
        "read:issue-details:jira",
        "read:project:jira",
        "read:jql:jira",
        "read:board-scope:jira-software",
        "write:jira-work",
        "write:issue:jira",
        "write:comment:jira",
        "write:attachment:jira",
        "offline_access"
        ] : [
        "read:jira-work",
        "read:jira-user",
        "read:issue-details:jira",
        "read:project:jira",
        "read:jql:jira",
        "read:board-scope:jira-software",
        "offline_access"
      ]
      entities            = coalesce(var.jira_config.entities, ["project", "issue", "attachment", "comment", "worklog"])
      static_ip_addresses = contains(keys(google_discovery_engine_data_connector.connectors), "${k}-jira") ? google_discovery_engine_data_connector.connectors["${k}-jira"].static_ip_addresses : []
      action_instructions = contains(["OAUTH", "OAUTH_TWO_LEGGED"], local.effective_jira_auth_type) ? "Create an Atlassian 3LO app at https://developer.atlassian.com/console/myapps/ with callback URL https://vertexaisearch.cloud.google.com/console/oauth/jira_oauth.html (and https://vertexaisearch.cloud.google.com/oauth-redirect if Actions enabled), configure scopes, retrieve cloudId (instance_id) from https://<instance_uri>/_edge/tenant_info, and supply client_id, client_secret, and instance_id via TF_VAR_jira_auth or terraform.tfvars." : "Generate an Atlassian API token at https://id.atlassian.com/manage-profile/security/api-tokens and supply user_account and api_token via TF_VAR_jira_auth."
    }
  }
}

output "confluence_checklist" {
  description = "Atlassian Confluence connector configuration and onboarding checklist per environment"
  value = {
    for k, v in local.environments : k => {
      project_id                   = google_project.projects[k].project_id
      instance_uri                 = try(coalesce(local.effective_confluence_instance_uri), "")
      instance_id                  = nonsensitive(local.effective_confluence_instance_id)
      auth_type                    = local.effective_confluence_auth_type
      data_source_version          = local.effective_confluence_version
      oauth_ingestion_callback_url = "https://vertexaisearch.cloud.google.com/console/oauth/confluence_oauth.html"
      oauth_actions_callback_url   = "https://vertexaisearch.cloud.google.com/oauth-redirect"
      developer_console_url        = "https://developer.atlassian.com/console/myapps/"
      admin_console_url            = "https://admin.atlassian.com"
      instance_id_help             = "Retrieve your Atlassian Cloud ID UUID via: curl -s https://<site>.atlassian.net/_edge/tenant_info | jq -r .cloudId"
      oauth_scopes = coalesce(var.confluence_config.enable_actions, false) ? [
        "search:confluence",
        "read:page:confluence",
        "read:space:confluence",
        "read:comment:confluence",
        "read:attachment:confluence",
        "read:whiteboard:confluence",
        "write:page:confluence",
        "write:blogpost:confluence",
        "write:space:confluence",
        "write:attachment:confluence",
        "offline_access"
        ] : [
        "search:confluence",
        "read:page:confluence",
        "read:space:confluence",
        "read:comment:confluence",
        "read:attachment:confluence",
        "read:whiteboard:confluence",
        "offline_access"
      ]
      entities            = coalesce(var.confluence_config.entities, ["space", "page", "blog", "attachment", "comment"])
      static_ip_addresses = contains(keys(google_discovery_engine_data_connector.connectors), "${k}-confluence") ? google_discovery_engine_data_connector.connectors["${k}-confluence"].static_ip_addresses : []
      action_instructions = contains(["OAUTH", "OAUTH_TWO_LEGGED"], local.effective_confluence_auth_type) ? "Create an Atlassian 3LO app at https://developer.atlassian.com/console/myapps/ with callback URL https://vertexaisearch.cloud.google.com/console/oauth/confluence_oauth.html (and https://vertexaisearch.cloud.google.com/oauth-redirect if Actions enabled), configure scopes, retrieve cloudId (instance_id) from https://<instance_uri>/_edge/tenant_info, and supply client_id, client_secret, and instance_id via TF_VAR_confluence_auth (or reuse TF_VAR_jira_auth)." : "Generate an Atlassian API token at https://id.atlassian.com/manage-profile/security/api-tokens and supply user_account and api_token via TF_VAR_confluence_auth (or TF_VAR_jira_auth)."
    }
  }
}

output "people_directory_checklist" {
  description = "Google People & Org Directory connector configuration and DWD checklist per environment"
  value = {
    for k, v in local.environments : k => {
      project_id          = google_project.projects[k].project_id
      collection_id       = coalesce(var.people_directory_config.collection_id, "people-directory-collection")
      data_source         = coalesce(var.people_directory_config.data_source, "google_people_directory")
      sync_mode           = (coalesce(var.people_directory_config.sync_mode, "PERIODIC") == "INCREMENTAL") ? "PERIODIC" : coalesce(var.people_directory_config.sync_mode, "PERIODIC")
      refresh_interval    = coalesce(var.people_directory_config.refresh_interval, "86400s")
      entities            = coalesce(var.people_directory_config.entities, ["users"])
      service_agent_email = "service-${google_project.projects[k].number}@gcp-sa-discoveryengine.iam.gserviceaccount.com"
      admin_console_url   = "https://admin.google.com/ac/owl/domainwidedelegation"
      required_scopes = [
        "https://www.googleapis.com/auth/admin.directory.user.readonly",
        "https://www.googleapis.com/auth/admin.directory.orgunit.readonly",
        "https://www.googleapis.com/auth/admin.directory.userschema.readonly",
        "https://www.googleapis.com/auth/directory.readonly"
      ]
      action_instructions = "Ensure Domain-Wide Delegation in Google Workspace Admin Console includes the required Directory API scopes for the service agent email."
    }
  }
}

output "hubspot_checklist" {
  description = "HubSpot connector configuration and onboarding checklist per environment"
  value = {
    for k, v in local.environments : k => {
      project_id          = google_project.projects[k].project_id
      instance_uri        = coalesce(var.hubspot_config.instance_uri, "https://api.hubapi.com")
      entities            = coalesce(var.hubspot_config.entities, ["contact", "company", "deal", "ticket"])
      static_ip_addresses = contains(keys(google_discovery_engine_data_connector.connectors), "${k}-hubspot") ? google_discovery_engine_data_connector.connectors["${k}-hubspot"].static_ip_addresses : []
      action_instructions = "Generate a Service Key in HubSpot Settings > Development > Keys > Service Keys. Grant read applicable scopes and supply the secret token via export TF_VAR_hubspot_auth='{\"api_token\":\"<service_key>\"}'."
    }
  }
}

