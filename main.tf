# Locals to construct environment details, services, and connectors
locals {
  environment_details = {
    "non-prod" = { display_name = "Non-Production" }
    "prod"     = { display_name = "Production" }
    "dev"      = { display_name = "Development" }
    "pilot"    = { display_name = "Pilot" }
    "staging"  = { display_name = "Staging" }
  }

  environments = {
    for env in var.environments : env => {
      display_name = lookup(local.environment_details, env, { display_name = title(replace(env, "-", " ")) }).display_name
      project_id   = lookup(var.custom_project_ids, env, "${var.project_id_prefix}${var.customer_id}-${env}")
      seat_count   = lookup(var.seat_allocations, env, 0)
    }
  }

  connector_meta = {
    "google_mail" = {
      display_name = "Gmail"
      service      = "gmail.googleapis.com"
      collection   = "gmail-collection"
    }
    "google_calendar" = {
      display_name = "Google Calendar"
      service      = "calendar-json.googleapis.com"
      collection   = "calendar-collection"
    }
    "google_drive" = {
      display_name = "Google Drive"
      service      = "drive.googleapis.com"
      collection   = "drive-collection"
    }
    "google_chat" = {
      display_name = "Google Chat"
      service      = "chat.googleapis.com"
      collection   = "chat-collection"
    }
  }

  # Map of all services that need to be enabled per customer environment project
  base_services = [
    "discoveryengine.googleapis.com",
    "cloudidentity.googleapis.com",
    "admin.googleapis.com",
    "gmail.googleapis.com",
    "calendar-json.googleapis.com",
    "drive.googleapis.com",
    "chat.googleapis.com",
    "iamcredentials.googleapis.com",
    "iam.googleapis.com"
  ]

  project_services = merge([
    for env_key, env_val in local.environments : {
      for svc in local.base_services : "${env_key}-${svc}" => {
        project_id = google_project.projects[env_key].project_id
        service    = svc
      }
    }
  ]...)

  # Workspace connectors per environment (when enabled)
  workspace_environment_connectors = var.enable_connectors ? {
    for pair in setproduct(keys(local.environments), tolist(var.workspace_connectors)) :
    "${pair[0]}-${pair[1]}" => {
      env_key             = pair[0]
      connector           = pair[1]
      data_source         = pair[1]
      data_source_version = null
      display_name        = lookup(local.connector_meta, pair[1], { display_name = title(replace(pair[1], "_", " ")), service = "", collection = "${replace(pair[1], "_", "-")}-collection" }).display_name
      collection_id       = lookup(local.connector_meta, pair[1], { display_name = "", service = "", collection = "${replace(pair[1], "_", "-")}-collection" }).collection
      project_id          = google_project.projects[pair[0]].project_id
      entities = [
        {
          entity_name = pair[1]
          params      = null
        }
      ]
      connector_modes              = ["FEDERATED"]
      sync_mode                    = null
      refresh_interval             = "0s"
      incremental_refresh_interval = null
      static_ip_enabled            = null
      auto_run_disabled            = null
      incremental_sync_disabled    = null
      params                       = {}
      action_params                = {}
      enable_actions               = false
      enabled_actions              = []
      instance_uri                 = ""
    }
  } : {}

  # Map user-friendly or legacy auth type to canonical Discovery Engine auth_type
  effective_jira_auth_type = {
    "OAUTH"            = "OAUTH"
    "OAUTH2"           = "OAUTH"
    "BASIC_AUTH"       = "BASIC_AUTH"
    "API_TOKEN"        = "BASIC_AUTH"
    "OAUTH_TWO_LEGGED" = "OAUTH_TWO_LEGGED"
  }[var.jira_auth_type]

  effective_jira_instance_id = try(coalesce(
    trimspace(nonsensitive(try(var.jira_auth.instance_id, ""))),
    trimspace(try(var.jira_config.instance_id, ""))
  ), "")

  # Default data source and version based on auth type:
  # Discovery Engine 'jira' (Cloud) only accepts OAuth params (instance_uri, instance_id, client_id, client_secret),
  # whereas API_TOKEN / BASIC_AUTH uses 'jira_server' with (api_token_type, username, api_token) and destination_configs.
  effective_jira_data_source = local.effective_jira_auth_type == "BASIC_AUTH" ? "jira_server" : coalesce(var.jira_config.data_source, "jira")
  default_jira_version       = local.effective_jira_auth_type == "BASIC_AUTH" ? 1 : 3
  effective_jira_version     = coalesce(var.jira_config.data_source_version, local.default_jira_version)

  jira_server_entity_map = {
    "project"    = "projects"
    "issue"      = "issues"
    "attachment" = "attachments"
    "comment"    = "comments"
    "worklog"    = "worklogs"
  }

  jira_entity_params = merge(
    length(coalesce(var.jira_config.project_keys_include, [])) > 0 ? {
      "inclusion_filters" = {
        "projectKey" = var.jira_config.project_keys_include
      }
    } : {},
    length(coalesce(var.jira_config.project_keys_exclude, [])) > 0 ? {
      "exclusion_filters" = {
        "projectKey" = var.jira_config.project_keys_exclude
      }
    } : {}
  )

  # Atlassian Jira connector per environment (when enabled)
  jira_environment_connectors = var.enable_jira_connector ? {
    for env_key, env_val in local.environments :
    "${env_key}-jira" => {
      env_key             = env_key
      connector           = "jira"
      data_source         = local.effective_jira_data_source
      data_source_version = local.effective_jira_version
      display_name        = "Atlassian Jira"
      collection_id       = try(coalesce(trimspace(var.jira_config.collection_id)), "") != "" ? trimspace(var.jira_config.collection_id) : (contains(coalesce(var.jira_config.connector_modes, ["FEDERATED"]), "FEDERATED") ? "jira-federated-collection" : "jira-collection")
      project_id          = google_project.projects[env_key].project_id
      entities = [
        for e in coalesce(var.jira_config.entities, ["project", "issue", "attachment", "comment", "worklog"]) : {
          entity_name = local.effective_jira_data_source == "jira_server" ? lookup(local.jira_server_entity_map, e, e) : e
          params      = (contains(["project", "projects"], e) && length(local.jira_entity_params) > 0) ? jsonencode(local.jira_entity_params) : null
        }
      ]
      connector_modes              = coalesce(var.jira_config.enable_actions, false) ? distinct(concat(coalesce(var.jira_config.connector_modes, ["FEDERATED"]), ["ACTIONS"])) : coalesce(var.jira_config.connector_modes, ["FEDERATED"])
      sync_mode                    = contains(coalesce(var.jira_config.connector_modes, ["FEDERATED"]), "FEDERATED") ? null : var.jira_config.sync_mode
      refresh_interval             = coalesce(var.jira_config.refresh_interval, "86400s")
      incremental_refresh_interval = (local.effective_jira_data_source == "jira_server" || contains(coalesce(var.jira_config.connector_modes, ["FEDERATED"]), "FEDERATED")) ? null : var.jira_config.incremental_refresh_interval
      static_ip_enabled            = var.jira_config.static_ip_enabled
      auto_run_disabled            = var.jira_config.auto_run_disabled
      incremental_sync_disabled    = (local.effective_jira_data_source == "jira_server" || contains(coalesce(var.jira_config.connector_modes, ["FEDERATED"]), "FEDERATED")) ? null : var.jira_config.incremental_sync_disabled
      instance_uri                 = try(coalesce(var.jira_config.instance_uri), "")
      params = local.effective_jira_data_source == "jira_server" ? merge(
        { "api_token_type" = "BASIC_AUTH" },
        var.jira_auth.user_account != "" ? { "username" = var.jira_auth.user_account } : {},
        var.jira_auth.api_token != "" ? { "api_token" = var.jira_auth.api_token } : {},
        coalesce(var.jira_config.extra_params, {})
        ) : merge(
        var.jira_config.instance_uri != "" ? { "instance_uri" = var.jira_config.instance_uri } : {},
        local.effective_jira_instance_id != "" ? { "instance_id" = local.effective_jira_instance_id } : {},
        var.jira_auth.client_id != "" ? { "client_id" = var.jira_auth.client_id } : {},
        var.jira_auth.client_secret != "" ? { "client_secret" = var.jira_auth.client_secret } : {},
        coalesce(var.jira_config.extra_params, {})
      )
      action_params = merge(
        var.jira_config.instance_uri != "" ? { "instance_uri" = var.jira_config.instance_uri } : {},
        local.effective_jira_instance_id != "" ? { "instance_id" = local.effective_jira_instance_id } : {},
        { "auth_type" = "OAUTH" },
        var.jira_auth.client_id != "" ? { "client_id" = var.jira_auth.client_id } : {},
        var.jira_auth.client_secret != "" ? { "client_secret" = var.jira_auth.client_secret } : {}
      )
      enable_actions  = coalesce(var.jira_config.enable_actions, false)
      enabled_actions = coalesce(var.jira_config.enabled_actions, [])
    }
  } : {}

  # Map user-friendly or legacy auth type to canonical Discovery Engine auth_type for Confluence
  effective_confluence_auth_type = {
    "OAUTH"            = "OAUTH"
    "OAUTH2"           = "OAUTH"
    "BASIC_AUTH"       = "BASIC_AUTH"
    "API_TOKEN"        = "BASIC_AUTH"
    "OAUTH_TWO_LEGGED" = "OAUTH_TWO_LEGGED"
  }[var.confluence_auth_type]

  # Confluence instance URI and instance ID with automatic fallback to Jira values when omitted
  effective_confluence_instance_uri = try(coalesce(
    trimspace(try(var.confluence_config.instance_uri, "")),
    trimspace(try(var.jira_config.instance_uri, ""))
  ), "")

  effective_confluence_instance_id = try(coalesce(
    trimspace(nonsensitive(try(var.confluence_auth.instance_id, ""))),
    trimspace(try(var.confluence_config.instance_id, "")),
    local.effective_jira_instance_id
  ), "")

  effective_confluence_client_id = try(coalesce(
    trimspace(nonsensitive(try(var.confluence_auth.client_id, ""))),
    trimspace(nonsensitive(try(var.jira_auth.client_id, "")))
  ), "")

  effective_confluence_client_secret = try(coalesce(
    trimspace(nonsensitive(try(var.confluence_auth.client_secret, ""))),
    trimspace(nonsensitive(try(var.jira_auth.client_secret, "")))
  ), "")

  effective_confluence_user_account = try(coalesce(
    trimspace(nonsensitive(try(var.confluence_auth.user_account, ""))),
    trimspace(nonsensitive(try(var.jira_auth.user_account, "")))
  ), "")

  effective_confluence_api_token = try(coalesce(
    trimspace(nonsensitive(try(var.confluence_auth.api_token, ""))),
    trimspace(nonsensitive(try(var.jira_auth.api_token, "")))
  ), "")

  # Default data source and version based on auth type:
  # Discovery Engine 'confluence' (Cloud) v4 supports FEDERATED and ACTIONS via OAuth (instance_uri, instance_id, client_id, client_secret),
  # whereas BASIC_AUTH / API_TOKEN uses 'confluence_server' v1 with (user_account, password) and destination_configs.
  effective_confluence_data_source = local.effective_confluence_auth_type == "BASIC_AUTH" ? "confluence_server" : coalesce(var.confluence_config.data_source, "confluence")
  default_confluence_version       = local.effective_confluence_auth_type == "BASIC_AUTH" ? 1 : 4
  effective_confluence_version     = coalesce(var.confluence_config.data_source_version, local.default_confluence_version)

  confluence_cloud_entity_map = {
    "blogpost"    = "blog"
    "spaces"      = "space"
    "pages"       = "page"
    "attachments" = "attachment"
    "comments"    = "comment"
    "whiteboards" = "whiteboard"
  }

  confluence_server_entity_map = {
    "space"      = "spaces"
    "page"       = "pages"
    "blog"       = "blogposts"
    "blogpost"   = "blogposts"
    "attachment" = "attachments"
    "comment"    = "comments"
  }

  confluence_cloud_space_params = merge(
    length(coalesce(var.confluence_config.space_keys_include, [])) > 0 ? {
      "inclusion_filters" = {
        "spaceKey" = var.confluence_config.space_keys_include
      }
    } : {},
    length(coalesce(var.confluence_config.space_keys_exclude, [])) > 0 ? {
      "exclusion_filters" = {
        "spaceKey" = var.confluence_config.space_keys_exclude
      }
    } : {}
  )

  confluence_server_space_params = merge(
    length(coalesce(var.confluence_config.space_keys_include, [])) > 0 ? {
      "inclusion_filters" = {
        "Key" = var.confluence_config.space_keys_include
      }
    } : {},
    length(coalesce(var.confluence_config.space_keys_exclude, [])) > 0 ? {
      "exclusion_filters" = {
        "Key" = var.confluence_config.space_keys_exclude
      }
    } : {}
  )

  confluence_space_entity_params = local.effective_confluence_data_source == "confluence_server" ? local.confluence_server_space_params : local.confluence_cloud_space_params

  # Atlassian Confluence connector per environment (when enabled)
  confluence_environment_connectors = var.enable_confluence_connector ? {
    for env_key, env_val in local.environments :
    "${env_key}-confluence" => {
      env_key             = env_key
      connector           = "confluence"
      data_source         = local.effective_confluence_data_source
      data_source_version = local.effective_confluence_version
      display_name        = "Atlassian Confluence"
      collection_id       = try(coalesce(trimspace(var.confluence_config.collection_id)), "") != "" ? trimspace(var.confluence_config.collection_id) : (contains(coalesce(var.confluence_config.connector_modes, ["FEDERATED"]), "FEDERATED") ? "confluence-federated-collection" : "confluence-collection")
      project_id          = google_project.projects[env_key].project_id
      entities = [
        for e in coalesce(var.confluence_config.entities, ["space", "page", "blog", "attachment", "comment"]) : {
          entity_name = local.effective_confluence_data_source == "confluence_server" ? lookup(local.confluence_server_entity_map, e, e) : lookup(local.confluence_cloud_entity_map, e, e)
          params      = (contains(["space", "spaces"], e) && length(local.confluence_space_entity_params) > 0) ? jsonencode(local.confluence_space_entity_params) : null
        }
      ]
      connector_modes              = coalesce(var.confluence_config.enable_actions, false) ? distinct(concat(coalesce(var.confluence_config.connector_modes, ["FEDERATED"]), ["ACTIONS"])) : coalesce(var.confluence_config.connector_modes, ["FEDERATED"])
      sync_mode                    = contains(coalesce(var.confluence_config.connector_modes, ["FEDERATED"]), "FEDERATED") ? null : var.confluence_config.sync_mode
      refresh_interval             = coalesce(var.confluence_config.refresh_interval, "86400s")
      incremental_refresh_interval = (local.effective_confluence_data_source == "confluence_server" || contains(coalesce(var.confluence_config.connector_modes, ["FEDERATED"]), "FEDERATED")) ? null : var.confluence_config.incremental_refresh_interval
      static_ip_enabled            = var.confluence_config.static_ip_enabled
      auto_run_disabled            = var.confluence_config.auto_run_disabled
      incremental_sync_disabled    = (local.effective_confluence_data_source == "confluence_server" || contains(coalesce(var.confluence_config.connector_modes, ["FEDERATED"]), "FEDERATED")) ? null : var.confluence_config.incremental_sync_disabled
      instance_uri                 = local.effective_confluence_instance_uri
      params = local.effective_confluence_data_source == "confluence_server" ? merge(
        { "api_token_type" = "BASIC_AUTH" },
        local.effective_confluence_user_account != "" ? { "username" = local.effective_confluence_user_account } : {},
        local.effective_confluence_api_token != "" ? { "password" = local.effective_confluence_api_token } : {},
        coalesce(var.confluence_config.extra_params, {})
        ) : merge(
        local.effective_confluence_instance_uri != "" ? { "instance_uri" = local.effective_confluence_instance_uri } : {},
        local.effective_confluence_instance_id != "" ? { "instance_id" = local.effective_confluence_instance_id } : {},
        local.effective_confluence_client_id != "" ? { "client_id" = local.effective_confluence_client_id } : {},
        local.effective_confluence_client_secret != "" ? { "client_secret" = local.effective_confluence_client_secret } : {},
        coalesce(var.confluence_config.extra_params, {})
      )
      action_params = merge(
        local.effective_confluence_instance_uri != "" ? { "instance_uri" = local.effective_confluence_instance_uri } : {},
        local.effective_confluence_instance_id != "" ? { "instance_id" = local.effective_confluence_instance_id } : {},
        { "auth_type" = "OAUTH" },
        local.effective_confluence_client_id != "" ? { "client_id" = local.effective_confluence_client_id } : {},
        local.effective_confluence_client_secret != "" ? { "client_secret" = local.effective_confluence_client_secret } : {}
      )
      enable_actions  = coalesce(var.confluence_config.enable_actions, false)
      enabled_actions = coalesce(var.confluence_config.enabled_actions, [])
    }
  } : {}

  # Entity parameters for Google People & Org Directory
  people_directory_entity_params = merge(
    var.people_directory_config.include_suspended_users ? { "include_suspended_users" = "true" } : {},
    length(coalesce(var.people_directory_config.org_units_include, [])) > 0 ? {
      "org_units" = var.people_directory_config.org_units_include
    } : {},
    length(coalesce(var.people_directory_config.custom_schemas_include, [])) > 0 ? {
      "custom_schemas" = var.people_directory_config.custom_schemas_include
    } : {}
  )

  # Map user-friendly or legacy data_source names to canonical Discovery Engine data_source
  effective_people_directory_data_source = "native_cloud_identity"

  # Google Cloud Identity / Workspace People & Org Directory connector per environment (when enabled)
  people_directory_environment_connectors = var.enable_people_directory_connector ? {
    for env_key, env_val in local.environments :
    "${env_key}-people-directory" => {
      env_key             = env_key
      connector           = "people_directory"
      data_source         = local.effective_people_directory_data_source
      data_source_version = null
      display_name        = coalesce(var.people_directory_config.display_name, "Google People Directory")
      collection_id       = coalesce(var.people_directory_config.collection_id, "people-directory-collection")
      project_id          = google_project.projects[env_key].project_id
      entities = [
        {
          entity_name = "users"
          params      = length(local.people_directory_entity_params) > 0 ? jsonencode(local.people_directory_entity_params) : null
        }
      ]
      connector_modes              = ["DATA_INGESTION"]
      sync_mode                    = "PERIODIC"
      refresh_interval             = coalesce(var.people_directory_config.refresh_interval, "86400s")
      incremental_refresh_interval = null
      static_ip_enabled            = false
      auto_run_disabled            = coalesce(var.people_directory_config.auto_run_disabled, false)
      incremental_sync_disabled    = false
      instance_uri                 = ""
      params = {
        "impersonated_user_email_address" = var.workspace_admin_email
        "super_admin_service_account"     = "service-${google_project.projects[env_key].number}@gcp-sa-discoveryengine.iam.gserviceaccount.com"
      }
      action_params   = {}
      enable_actions  = false
      enabled_actions = []
    }
  } : {}

  # HubSpot connector per environment (when enabled)
  hubspot_entity_map = {
    "contact"   = "contacts"
    "contacts"  = "contacts"
    "company"   = "companies"
    "companies" = "companies"
    "deal"      = "deals"
    "deals"     = "deals"
    "ticket"    = "tickets"
    "tickets"   = "tickets"
  }

  effective_hubspot_token = try(coalesce(
    trimspace(nonsensitive(try(var.hubspot_auth.private_app_access_token, ""))),
    trimspace(nonsensitive(try(var.hubspot_auth.api_token, ""))),
    trimspace(nonsensitive(try(var.hubspot_auth.bearer_token, "")))
  ), "")

  hubspot_environment_connectors = var.enable_hubspot_connector ? {
    for env_key, env_val in local.environments :
    "${env_key}-hubspot" => {
      env_key             = env_key
      connector           = "hubspot"
      data_source         = coalesce(var.hubspot_config.data_source, "hubspot")
      data_source_version = var.hubspot_config.data_source_version
      display_name        = "HubSpot"
      collection_id       = try(coalesce(trimspace(var.hubspot_config.collection_id)), "") != "" ? trimspace(var.hubspot_config.collection_id) : "hubspot-federated-collection"
      project_id          = google_project.projects[env_key].project_id
      entities = [
        for e in coalesce(var.hubspot_config.entities, ["contacts", "companies", "deals", "tickets"]) : {
          entity_name = lookup(local.hubspot_entity_map, lower(trimspace(e)), e)
          params      = null
        }
      ]
      connector_modes              = coalesce(var.hubspot_config.connector_modes, ["FEDERATED"])
      sync_mode                    = contains(coalesce(var.hubspot_config.connector_modes, ["FEDERATED"]), "FEDERATED") ? null : var.hubspot_config.sync_mode
      refresh_interval             = coalesce(var.hubspot_config.refresh_interval, "86400s")
      incremental_refresh_interval = var.hubspot_config.incremental_refresh_interval
      static_ip_enabled            = var.hubspot_config.static_ip_enabled
      auto_run_disabled            = var.hubspot_config.auto_run_disabled
      incremental_sync_disabled    = var.hubspot_config.incremental_sync_disabled
      instance_uri                 = coalesce(var.hubspot_config.instance_uri, "https://api.hubapi.com")
      params = merge(
        { "auth_type" = "BEARER_TOKEN" },
        local.effective_hubspot_token != "" ? {
          "private_app_access_token" = local.effective_hubspot_token,
          "Private App Access Token" = local.effective_hubspot_token,
          "bearer_token"             = local.effective_hubspot_token,
          "api_token"                = local.effective_hubspot_token
        } : {},
        coalesce(var.hubspot_config.extra_params, {})
      )
      action_params   = {}
      enable_actions  = false
      enabled_actions = []
    }
  } : {}

  environment_connectors = merge(
    local.workspace_environment_connectors,
    local.jira_environment_connectors,
    local.confluence_environment_connectors,
    local.people_directory_environment_connectors,
    local.hubspot_environment_connectors
  )

  # Domain-Wide Delegation OAuth scopes required for Workspace connectors & user directory
  dwd_scopes = [
    "https://www.googleapis.com/auth/admin.directory.user.readonly",
    "https://www.googleapis.com/auth/admin.directory.group.readonly",
    "https://www.googleapis.com/auth/admin.directory.group.member.readonly",
    "https://www.googleapis.com/auth/admin.directory.orgunit.readonly",
    "https://www.googleapis.com/auth/admin.directory.userschema.readonly",
    "https://www.googleapis.com/auth/directory.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/chat.spaces.readonly",
    "https://www.googleapis.com/auth/chat.messages.readonly"
  ]


  # Normalized optional parameters
  effective_sa_email  = try(trimspace(var.sa_email), "") != "" ? trimspace(var.sa_email) : null
  effective_folder_id = try(trimspace(var.folder_id), "") != "" ? trimspace(var.folder_id) : null
  effective_org_id    = local.effective_folder_id == null && try(trimspace(var.org_id), "") != "" ? trimspace(var.org_id) : null
}

# 0. Provision GCP Projects per Customer Environment
resource "google_project" "projects" {
  for_each        = local.environments
  name            = lookup(var.custom_project_names, each.key, substr("${var.customer_name} ${each.value.display_name}", 0, 30))
  project_id      = each.value.project_id
  folder_id       = local.effective_folder_id
  org_id          = local.effective_org_id
  billing_account = var.billing_account
  deletion_policy = contains(["prod", "production", "ge-prism"], lower(each.key)) ? "PREVENT" : "DELETE"
}

# 1. Enable GCP Services per Customer Environment Project
resource "google_project_service" "services" {
  for_each           = local.project_services
  project            = each.value.project_id
  service            = each.value.service
  disable_on_destroy = false
}

# 1.5 Pre-create Discovery Engine Service Agent Identity
resource "google_project_service_identity" "discoveryengine_sa" {
  provider = google-beta
  for_each = local.environments
  project  = google_project.projects[each.key].project_id
  service  = "discoveryengine.googleapis.com"

  depends_on = [google_project_service.services]
}

# Service Account Token Creator role for Discovery Engine Service Agent (required by native_cloud_identity)
resource "google_project_iam_member" "discoveryengine_sa_token_creator" {
  for_each = var.enable_people_directory_connector ? local.environments : {}
  project  = google_project.projects[each.key].project_id
  role     = "roles/iam.serviceAccountTokenCreator"
  member   = "serviceAccount:service-${google_project.projects[each.key].number}@gcp-sa-discoveryengine.iam.gserviceaccount.com"

  depends_on = [google_project_service_identity.discoveryengine_sa]
}


# Optional Provisioner Service Account IAM binding
resource "google_project_iam_member" "sa_discoveryengine_admin" {
  for_each = local.effective_sa_email != null ? local.environments : {}
  project  = google_project.projects[each.key].project_id
  role     = "roles/discoveryengine.admin"
  member   = "serviceAccount:${local.effective_sa_email}"

  depends_on = [google_project_service.services]
}

# 2. Configure Discovery Engine Location Identity Provider (GSuite IdP)
resource "google_discovery_engine_acl_config" "idp" {
  for_each = local.environments
  project  = google_project.projects[each.key].project_id
  location = var.location

  idp_config {
    idp_type = "GSUITE"
  }

  depends_on = [
    google_project_service.services,
    google_project_service_identity.discoveryengine_sa
  ]
}

# 3. Provision Cloud Identity User Groups
resource "google_cloud_identity_group" "users" {
  for_each     = local.environments
  display_name = "${var.customer_name} (${each.value.display_name}) Users"
  parent       = "customers/${var.workspace_customer_id}"

  group_key {
    id = "${var.customer_id}-${each.key}-users@${var.company_domain}"
  }

  labels = {
    "cloudidentity.googleapis.com/groups.discussion_forum" = ""
  }

  depends_on = [google_project_service.services]
}

# 4. Provision Discovery Engine User Store with Auto-Registration
resource "google_discovery_engine_user_store" "default" {
  for_each                           = local.environments
  project                            = google_project.projects[each.key].project_id
  location                           = var.location
  user_store_id                      = "default_user_store"
  default_license_config             = lookup(var.license_config_names, each.key, null)
  enable_license_auto_register       = lookup(var.license_config_names, each.key, null) != null
  enable_expired_license_auto_update = lookup(var.license_config_names, each.key, null) != null

  depends_on = [
    google_project_service.services,
    google_discovery_engine_acl_config.idp
  ]
}

# 5. Provision Workspace & Third-Party Data Connectors per Customer Environment Project (Staged)
resource "google_discovery_engine_data_connector" "connectors" {
  for_each                     = local.environment_connectors
  project                      = each.value.project_id
  location                     = var.location
  collection_id                = each.value.collection_id
  collection_display_name      = "${each.value.display_name} Collection"
  data_source                  = each.value.data_source
  data_source_version          = each.value.data_source_version
  params                       = each.value.params
  refresh_interval             = each.value.refresh_interval
  incremental_refresh_interval = each.value.incremental_refresh_interval
  sync_mode                    = each.value.sync_mode
  static_ip_enabled            = each.value.static_ip_enabled
  auto_run_disabled            = each.value.auto_run_disabled
  incremental_sync_disabled    = each.value.incremental_sync_disabled
  connector_modes              = each.value.connector_modes

  dynamic "entities" {
    for_each = each.value.entities
    content {
      entity_name = entities.value.entity_name
      params      = entities.value.params
    }
  }

  dynamic "destination_configs" {
    for_each = (each.value.instance_uri != "" && (each.value.enable_actions || contains(each.value.connector_modes, "FEDERATED") || each.value.data_source == "jira_server" || each.value.data_source == "confluence_server")) ? [each.value.instance_uri] : []
    content {
      key = "url"
      destinations {
        host = destination_configs.value
      }
    }
  }

  dynamic "action_config" {
    for_each = each.value.enable_actions ? [1] : []
    content {
      create_bap_connection = true
      action_params         = each.value.action_params
    }
  }

  dynamic "bap_config" {
    for_each = each.value.enable_actions ? [1] : []
    content {
      enabled_actions           = each.value.enabled_actions
      supported_connector_modes = ["ACTIONS"]
    }
  }

  depends_on = [
    google_project_service.services,
    google_discovery_engine_acl_config.idp,
    google_project_service_identity.discoveryengine_sa
  ]
}

# 6. Provision Unified Gemini Enterprise Search App per Customer Environment Project
resource "google_discovery_engine_search_engine" "engines" {
  for_each          = (var.enable_connectors || var.enable_jira_connector || var.enable_confluence_connector || var.enable_people_directory_connector || var.enable_hubspot_connector) ? local.environments : {}
  project           = google_project.projects[each.key].project_id
  location          = var.location
  collection_id     = "default_collection"
  engine_id         = lookup(var.custom_engine_ids, each.key, "${var.customer_id}-${each.key}-search-engine")
  display_name      = lookup(var.custom_engine_names, each.key, "${var.customer_name} (${each.value.display_name}) Search App")
  industry_vertical = "GENERIC"
  app_type          = "APP_TYPE_INTRANET"

  data_store_ids = flatten([
    for conn_key, conn in local.environment_connectors : [
      for entity in google_discovery_engine_data_connector.connectors[conn_key].entities :
      basename(entity.data_store)
      if try(trimspace(entity.data_store), "") != ""
    ]
    if conn.env_key == each.key
  ])

  search_engine_config {
    search_tier    = "SEARCH_TIER_STANDARD"
    search_add_ons = ["SEARCH_ADD_ON_LLM"]
  }

  depends_on = [
    google_discovery_engine_data_connector.connectors
  ]
}

# 7. Grant End-User Search Access Scoped to the Engine
resource "google_discovery_engine_search_engine_iam_member" "users" {
  for_each      = (var.enable_connectors || var.enable_jira_connector || var.enable_confluence_connector || var.enable_people_directory_connector || var.enable_hubspot_connector) ? local.environments : {}
  project       = google_project.projects[each.key].project_id
  location      = var.location
  collection_id = google_discovery_engine_search_engine.engines[each.key].collection_id
  engine_id     = google_discovery_engine_search_engine.engines[each.key].engine_id
  role          = "roles/discoveryengine.user"
  member        = "group:${google_cloud_identity_group.users[each.key].group_key[0].id}"
}

# 8. Provision Governed Gemini Enterprise Assistant
resource "google_discovery_engine_assistant" "default" {
  for_each           = (var.enable_connectors || var.enable_jira_connector || var.enable_confluence_connector || var.enable_people_directory_connector || var.enable_hubspot_connector) ? local.environments : {}
  project            = google_project.projects[each.key].project_id
  location           = var.location
  collection_id      = google_discovery_engine_search_engine.engines[each.key].collection_id
  engine_id          = google_discovery_engine_search_engine.engines[each.key].engine_id
  assistant_id       = "default_assistant"
  display_name       = "${var.customer_name} Assistant"
  web_grounding_type = "WEB_GROUNDING_TYPE_GOOGLE_SEARCH"

  generation_config {
    default_language = "en"
    system_instruction {
      additional_system_instruction = var.assistant_instructions
    }
  }

  depends_on = [
    google_discovery_engine_search_engine.engines
  ]
}

# 9. Emit License Allocations Configuration as Single Source of Truth
resource "local_file" "license_allocations" {
  filename = "${path.module}/config/license_allocations.json"
  content = jsonencode({
    licensing_project = coalesce(var.billing_project, try(values(google_project.projects)[0].project_id, ""))
    billing_account   = var.billing_account
    license_config_id = var.license_config_id
    subscription_id   = var.subscription_id
    subscription_tier = var.subscription_tier
    location          = var.location
    allocations = [
      for k, env in local.environments : {
        project_id       = google_project.projects[k].project_id
        project_number   = google_project.projects[k].number
        environment      = k
        environment_name = env.display_name
        seat_count       = env.seat_count
        status           = "active"
      }
    ]
  })
}
