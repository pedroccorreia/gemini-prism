output "project_ids" {
  description = "The project IDs of the created customer environment projects"
  value       = { for k, v in google_project.projects : k => v.project_id }
}

output "project_numbers" {
  description = "The project numbers of the created customer environment projects"
  value       = { for k, v in google_project.projects : k => v.number }
}

output "admin_group_emails" {
  description = "Emails of the provisioned Administrator Cloud Identity Groups per environment"
  value       = { for k, v in google_cloud_identity_group.admins : k => v.group_key[0].id }
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
      workspace_actions = {
        for conn in tolist(var.workspace_connectors) : conn => {
          enable_actions  = (var.enable_workspace_actions || try(coalesce(var.workspace_actions_config[conn].enable_actions, false), false))
          connector_modes = (var.enable_workspace_actions || try(coalesce(var.workspace_actions_config[conn].enable_actions, false), false)) ? ["FEDERATED", "ACTIONS"] : ["FEDERATED"]
          enabled_actions = (var.enable_workspace_actions || try(coalesce(var.workspace_actions_config[conn].enable_actions, false), false)) ? (
            length(try(coalesce(var.workspace_actions_config[conn].enabled_actions, []), [])) > 0
            ? var.workspace_actions_config[conn].enabled_actions
            : lookup(local.connector_meta, conn, { display_name = "", service = "", collection = "", default_actions = [] }).default_actions
          ) : []
        }
      }
      workspace_admin_settings_url = "https://admin.google.com"
      action_instructions          = "Add DWD API Client in Google Workspace Admin Console (https://admin.google.com/ac/owl/domainwidedelegation) using the 21-digit numeric client_id (or service_agent_email) with oauth_scopes_csv. In https://admin.google.com, allow Google Cloud Core Services under Security > Access and data control > API controls, and verify Workspace data access is enabled under Generative AI > Gemini Enterprise."
    }
  }
}

output "jira_checklist" {
  description = "Atlassian Jira connector configuration and onboarding checklist per environment"
  value = {
    for k, v in local.environments : k => {
      project_id                   = google_project.projects[k].project_id
      instance_uri                 = try(coalesce(var.jira_config.instance_uri), "")
      instance_id                  = try(nonsensitive(local.effective_jira_instance_id), local.effective_jira_instance_id)
      auth_type                    = local.effective_jira_auth_type
      data_source_version          = local.effective_jira_version
      oauth_ingestion_callback_url = "https://vertexaisearch.cloud.google.com/console/oauth/jira_oauth.html"
      oauth_actions_callback_url   = "https://vertexaisearch.cloud.google.com/oauth-redirect"
      developer_console_url        = "https://developer.atlassian.com/console/myapps/"
      admin_console_url            = "https://admin.atlassian.com"
      instance_id_help             = "Retrieve your Atlassian Cloud ID UUID via: curl -s https://<site>.atlassian.net/_edge/tenant_info | jq -r .cloudId"
      oauth_scopes = coalesce(var.jira_config.enable_actions, false) ? [
        # Classic scopes (Permissions -> Jira API -> Classic scopes)
        "read:jira-work",
        "read:jira-user",
        "write:jira-work",
        "manage:jira-project",
        # Granular scopes (Permissions -> Jira API -> Granular scopes)
        "read:issue-details:jira",
        "read:project:jira",
        "read:jql:jira",
        "read:user:jira",
        "read:attachment:jira",
        "read:board-scope:jira-software",
        "write:issue:jira",
        "write:comment:jira",
        "write:attachment:jira",
        "write:project:jira",
        "write:issue-link:jira",
        "write:issue-worklog:jira",
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
      action_instructions = contains(["OAUTH", "OAUTH_TWO_LEGGED"], local.effective_jira_auth_type) ? "Create an Atlassian 3LO app at https://developer.atlassian.com/console/myapps/ with callback URL https://vertexaisearch.cloud.google.com/console/oauth/jira_oauth.html (and https://vertexaisearch.cloud.google.com/oauth-redirect if Actions enabled), add BOTH Classic and Granular Jira API scopes, set Distribution -> Sharing so non-owner users can authorize, retrieve cloudId (instance_id) from https://<instance_uri>/_edge/tenant_info, and supply client_id, client_secret, and instance_id via TF_VAR_jira_auth or terraform.tfvars." : "Generate an Atlassian API token at https://id.atlassian.com/manage-profile/security/api-tokens and supply user_account and api_token via TF_VAR_jira_auth."
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
        # Classic scopes (Permissions -> Confluence API -> Classic scopes)
        "search:confluence",
        "read:confluence-content.all",
        "read:confluence-space.summary",
        "read:confluence-groups",
        "read:confluence-user",
        "write:confluence-content",
        "write:confluence-file",
        "write:confluence-space",
        # User Identity API scope (Permissions -> User identity API -> Classic scopes)
        "read:me",
        # Granular scopes (Permissions -> Confluence API -> Granular scopes)
        "read:attachment:confluence",
        "read:blogpost:confluence",
        "read:comment:confluence",
        "read:configuration:confluence",
        "read:content-details:confluence",
        "read:content.metadata:confluence",
        "read:group:confluence",
        "read:page:confluence",
        "read:space:confluence",
        "read:space-details:confluence",
        "read:task:confluence",
        "read:user:confluence",
        "read:whiteboard:confluence",
        "write:attachment:confluence",
        "write:blogpost:confluence",
        "write:page:confluence",
        "write:space:confluence",
        "offline_access"
        ] : [
        "search:confluence",
        "offline_access"
      ]
      entities            = coalesce(var.confluence_config.entities, ["space", "page", "blog", "attachment", "comment"])
      static_ip_addresses = contains(keys(google_discovery_engine_data_connector.connectors), "${k}-confluence") ? google_discovery_engine_data_connector.connectors["${k}-confluence"].static_ip_addresses : []
      action_instructions = contains(["OAUTH", "OAUTH_TWO_LEGGED"], local.effective_confluence_auth_type) ? "Create an Atlassian 3LO app at https://developer.atlassian.com/console/myapps/ with callback URL https://vertexaisearch.cloud.google.com/console/oauth/confluence_oauth.html (and https://vertexaisearch.cloud.google.com/oauth-redirect if Actions enabled), add Classic + Granular Confluence API scopes (plus User identity API read:me when Actions enabled), set Distribution -> Sharing so non-owner users can authorize, retrieve cloudId (instance_id) from https://<instance_uri>/_edge/tenant_info, and supply client_id, client_secret, and instance_id via TF_VAR_confluence_auth (or reuse TF_VAR_jira_auth)." : "Generate an Atlassian API token at https://id.atlassian.com/manage-profile/security/api-tokens and supply user_account and api_token via TF_VAR_confluence_auth (or TF_VAR_jira_auth)."
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

output "slack_checklist" {
  description = "Slack Enterprise connector configuration and onboarding checklist per environment"
  value = {
    for k, v in local.environments : k => {
      project_id              = google_project.projects[k].project_id
      instance_uri            = try(coalesce(var.slack_config.instance_uri), "")
      team_id                 = try(nonsensitive(local.effective_slack_team_id), local.effective_slack_team_id)
      auth_type               = local.effective_slack_auth_type
      data_source_version     = local.effective_slack_version
      oauth_callback_url      = "https://vertexaisearch.cloud.google.com/oauth-redirect"
      slack_api_console_url   = "https://api.slack.com/apps"
      slack_admin_console_url = "https://app.slack.com/manage"
      oauth_scopes = coalesce(var.slack_config.enable_actions, false) ? [
        "channels:read",
        "channels:history",
        "groups:read",
        "groups:history",
        "files:read",
        "users:read",
        "users:read.email",
        "canvases:read",
        "reactions:read",
        "team:read",
        "chat:write",
        "canvases:write",
        "reactions:write"
        ] : [
        "channels:read",
        "channels:history",
        "groups:read",
        "groups:history",
        "files:read",
        "users:read",
        "users:read.email"
      ]
      entities                 = coalesce(var.slack_config.entities, ["conversation", "message", "file"])
      channels_include         = coalesce(var.slack_config.channels_include, [])
      channels_exclude         = coalesce(var.slack_config.channels_exclude, [])
      include_private_channels = coalesce(var.slack_config.include_private_channels, false)
      static_ip_addresses      = contains(keys(google_discovery_engine_data_connector.connectors), "${k}-slack") ? google_discovery_engine_data_connector.connectors["${k}-slack"].static_ip_addresses : []
      action_instructions      = local.effective_slack_auth_type == "OAUTH" ? "Default Google-Managed OAuth (v3 Federated + Actions) requires no TF_VAR_slack_auth secrets—set slack_config.instance_uri and slack_config.team_id, apply Stage 3, and have end users click Connect next to Slack in the Gemini Enterprise Web App Sources panel. For a custom BYO Slack App, create an app at https://api.slack.com/apps with redirect URL https://vertexaisearch.cloud.google.com/oauth-redirect, configure the required OAuth scopes, and supply client_id and client_secret via TF_VAR_slack_auth." : "Create a Slack App at https://api.slack.com/apps, configure Bot Token Scopes (channels:read, channels:history, groups:read, groups:history, files:read, users:read, users:read.email), install to workspace, and supply bot_token (xoxb-...) and team_id (T... or E...) via TF_VAR_slack_auth."
    }
  }
}

output "hubspot_checklist" {
  description = "HubSpot CRM connector configuration and onboarding checklist per environment"
  value = {
    for k, v in local.environments : k => {
      project_id          = google_project.projects[k].project_id
      instance_uri        = try(coalesce(var.hubspot_config.instance_uri), "https://api.hubapi.com")
      portal_id           = try(coalesce(var.hubspot_config.portal_id), "")
      auth_type           = var.hubspot_auth_type
      collection_id       = try(coalesce(trimspace(var.hubspot_config.collection_id)), "") != "" ? trimspace(var.hubspot_config.collection_id) : "hubspot-federated-collection"
      data_source         = coalesce(var.hubspot_config.data_source, "hubspot")
      connector_modes     = local.effective_hubspot_modes
      entities            = coalesce(var.hubspot_config.entities, ["contacts", "companies", "deals", "tickets"])
      static_ip_addresses = contains(keys(google_discovery_engine_data_connector.connectors), "${k}-hubspot") ? google_discovery_engine_data_connector.connectors["${k}-hubspot"].static_ip_addresses : []
      hubspot_console_url = "https://app.hubspot.com"
      required_scopes = [
        "crm.objects.contacts.read",
        "crm.objects.companies.read",
        "crm.objects.deals.read",
        "crm.objects.owners.read"
      ]
      action_instructions = "Create a HubSpot Service Key at https://app.hubspot.com (Development > Keys > Service Keys) with required CRM scopes, and supply your service key (pat-ap1-...) via TF_VAR_hubspot_auth='{\"oauth_access_token\":\"pat-ap1-...\"}' (or \"service_key\")."
    }
  }
}

output "geap_governance_checklist" {
  description = "GEAP Agent Governance Foundation readiness & Day-2 agent deployment handoff manifest per environment"
  value = {
    for k, v in local.environments : k => {
      project_id      = google_project.projects[k].project_id
      project_number  = google_project.projects[k].number
      location        = var.location
      governance_mode = var.geap_governance_mode
      enabled         = var.geap_governance_mode == "foundation"
      enabled_apis    = var.geap_governance_mode == "foundation" ? local.geap_governance_services : []
      admin_roles     = var.geap_governance_mode == "foundation" ? local.geap_admin_roles : []
      admin_group     = google_cloud_identity_group.admins[k].group_key[0].id
      user_group      = google_cloud_identity_group.users[k].group_key[0].id
      service_agents = var.geap_governance_mode == "foundation" ? {
        agentregistry = "service-${google_project.projects[k].number}@gcp-sa-agentregistry.iam.gserviceaccount.com"
        aiplatform    = "service-${google_project.projects[k].number}@gcp-sa-aiplatform.iam.gserviceaccount.com"
        iap           = "service-${google_project.projects[k].number}@gcp-sa-iap.iam.gserviceaccount.com"
        modelarmor    = "service-${google_project.projects[k].number}@gcp-sa-modelarmor.iam.gserviceaccount.com"
      } : {}
      spiffe_trust_domain_hint = trimspace(try(coalesce(var.org_id), "")) != "" ? "spiffe://${trimspace(var.org_id)}.org.id.goog/agents/..." : "spiffe://<ORG_ID>.org.id.goog/agents/..."
      console_urls = {
        agent_registry = "https://console.cloud.google.com/agent-registry?project=${google_project.projects[k].project_id}"
        model_armor    = "https://console.cloud.google.com/security/model-armor?project=${google_project.projects[k].project_id}"
        topology       = "https://console.cloud.google.com/net-intelligence/topology?project=${google_project.projects[k].project_id}"
        vertex_agents  = "https://console.cloud.google.com/vertex-ai/agents?project=${google_project.projects[k].project_id}"
      }
      day2_instructions = var.geap_governance_mode == "foundation" ? "GEAP Governance Foundation is active. Deploy ADK / Vertex AI Agent Engine workloads into this project for automatic Agent Registry discovery, register remote MCP servers & skills in Agent Registry, and attach SPIFFE Unified Access Policies, Agent Gateway, or Model Armor templates in your Day-2 agent repository." : "GEAP Governance is skipped (geap_governance_mode = 'none'). Run 'python3 scripts/configure.py --set geap_governance_mode=foundation' and apply to enable GEAP Governance APIs and Admin IAM."
    }
  }
}

output "workspace_actions_checklist" {
  description = "Google Workspace Actions (3LO OAuth + BAP) configuration checklist per environment"
  value = {
    for k, v in local.environments : k => {
      project_id                   = google_project.projects[k].project_id
      project_number               = google_project.projects[k].number
      enable_workspace_actions     = var.enable_workspace_actions
      oauth_credentials_configured = (local.effective_workspace_client_id != "" && local.effective_workspace_client_secret != "")
      client_id_hint               = local.effective_workspace_client_id != "" ? "${substr(local.effective_workspace_client_id, 0, 12)}..." : "NOT_CONFIGURED"
      authorized_redirect_uris = [
        "https://vertexaisearch.cloud.google.com/console/oauth/default_oauth.html",
        "https://vertexaisearch.cloud.google.com/oauth-redirect"
      ]
      credentials_console_url = "https://console.cloud.google.com/apis/credentials?project=${google_project.projects[k].project_id}"
      workspace_actions = {
        for conn in tolist(var.workspace_connectors) : conn => {
          enable_actions  = (var.enable_workspace_actions || try(coalesce(var.workspace_actions_config[conn].enable_actions, false), false))
          collection_id   = try(coalesce(trimspace(var.workspace_actions_config[conn].collection_id)), "") != "" ? trimspace(var.workspace_actions_config[conn].collection_id) : "${replace(conn, "_", "-")}-actions-collection"
          connector_modes = (var.enable_workspace_actions || try(coalesce(var.workspace_actions_config[conn].enable_actions, false), false)) ? ["FEDERATED", "ACTIONS"] : ["FEDERATED"]
          enabled_actions = (var.enable_workspace_actions || try(coalesce(var.workspace_actions_config[conn].enable_actions, false), false)) ? (
            length(try(coalesce(var.workspace_actions_config[conn].enabled_actions, []), [])) > 0
            ? var.workspace_actions_config[conn].enabled_actions
            : lookup(local.connector_meta, conn, { display_name = "", service = "", collection = "", default_actions = [] }).default_actions
          ) : []
        }
      }
      action_instructions = "Create a Web Application OAuth 2.0 Client in https://console.cloud.google.com/apis/credentials?project=${google_project.projects[k].project_id} with Authorized Redirect URIs https://vertexaisearch.cloud.google.com/console/oauth/default_oauth.html and https://vertexaisearch.cloud.google.com/oauth-redirect, and set OAuth Consent Screen to Internal. Then export TF_VAR_workspace_oauth='{\"client_id\":\"...\",\"client_secret\":\"...\"}' and run 'make plan-connectors && make apply-connectors'."
    }
  }
}


