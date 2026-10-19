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
      action_instructions = "Add DWD API Client in Google Workspace Admin Console using service_agent_email as Client ID with oauth_scopes_csv."
    }
  }
}

output "jira_checklist" {
  description = "Atlassian Jira connector configuration and onboarding checklist per environment"
  value = {
    for k, v in local.environments : k => {
      project_id                   = google_project.projects[k].project_id
      instance_uri                 = coalesce(var.jira_config.instance_uri, "")
      instance_id                  = local.effective_jira_instance_id
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
      action_instructions = contains(["OAUTH", "OAUTH_TWO_LEGGED"], local.effective_jira_auth_type) ? "Create an Atlassian 3LO app at https://developer.atlassian.com/console/myapps/ with callback URLs https://vertexaisearch.cloud.google.com/console/oauth/jira_oauth.html (Ingestion) and https://vertexaisearch.cloud.google.com/oauth-redirect (Actions), configure scopes, retrieve cloudId from https://<instance_uri>/_edge/tenant_info, and supply client_id, client_secret, instance_id, and refresh_token via TF_VAR_jira_auth." : "Generate an Atlassian API token at https://id.atlassian.com/manage-profile/security/api-tokens and supply user_account and api_token via TF_VAR_jira_auth."
    }
  }
}
