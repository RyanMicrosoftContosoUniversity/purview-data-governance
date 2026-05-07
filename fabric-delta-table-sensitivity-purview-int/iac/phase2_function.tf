data "azurerm_client_config" "current" {}

# Existing Purview account ARM ID (constructed; account is not managed here)
locals {
  purview_account_id = "/subscriptions/${var.subscription_id}/resourceGroups/${var.phase2_resource_group}/providers/Microsoft.Purview/accounts/${var.purview_account_name}"
}

# Storage account for the Function (deployment package + runtime state)
resource "azurerm_storage_account" "func" {
  name                          = var.function_storage_account_name
  resource_group_name           = var.phase2_resource_group
  location                      = var.phase2_location
  account_tier                  = "Standard"
  account_replication_type      = "LRS"
  min_tls_version               = "TLS1_2"
  public_network_access_enabled = true

  blob_properties {
    delete_retention_policy {
      days = 7
    }
  }
}

resource "azurerm_storage_container" "deployments" {
  name                  = "deployments"
  storage_account_id    = azurerm_storage_account.func.id
  container_access_type = "private"
}

# App Insights for Function telemetry
resource "azurerm_log_analytics_workspace" "func" {
  name                = "law-${var.function_app_name}"
  location            = var.phase2_location
  resource_group_name = var.phase2_resource_group
  sku                 = "PerGB2018"
  retention_in_days   = 30
}

resource "azurerm_application_insights" "func" {
  name                = "appi-${var.function_app_name}"
  location            = var.phase2_location
  resource_group_name = var.phase2_resource_group
  workspace_id        = azurerm_log_analytics_workspace.func.id
  application_type    = "web"
}

# Flex Consumption plan
resource "azurerm_service_plan" "func" {
  name                = "asp-${var.function_app_name}"
  location            = var.phase2_location
  resource_group_name = var.phase2_resource_group
  os_type             = "Linux"
  sku_name            = "FC1"
}

# Package the Function code (with vendored deps from .python_packages)
data "archive_file" "function_zip" {
  type        = "zip"
  source_dir  = "${path.module}/function"
  output_path = "${path.module}/function.zip"
  excludes    = ["__pycache__", "local.settings.json", "tests", "requirements-dev.txt", ".pytest_cache", ".ruff_cache"]
}

resource "azurerm_storage_blob" "function_zip" {
  name                   = "function-${data.archive_file.function_zip.output_sha256}.zip"
  storage_account_name   = azurerm_storage_account.func.name
  storage_container_name = azurerm_storage_container.deployments.name
  type                   = "Block"
  source                 = data.archive_file.function_zip.output_path
  content_md5            = data.archive_file.function_zip.output_md5
}

# Flex Consumption Function App (Python 3.11)
resource "azurerm_function_app_flex_consumption" "func" {
  name                = var.function_app_name
  location            = var.phase2_location
  resource_group_name = var.phase2_resource_group
  service_plan_id     = azurerm_service_plan.func.id

  storage_container_type      = "blobContainer"
  storage_container_endpoint  = "${azurerm_storage_account.func.primary_blob_endpoint}${azurerm_storage_container.deployments.name}"
  storage_authentication_type = "SystemAssignedIdentity"

  runtime_name    = "python"
  runtime_version = "3.11"

  maximum_instance_count = 40
  instance_memory_in_mb  = 2048

  identity {
    type = "SystemAssigned"
  }

  app_settings = {
    APPLICATIONINSIGHTS_CONNECTION_STRING = azurerm_application_insights.func.connection_string
    SOURCE_WORKSPACE_ID                   = var.workspace_id
    SOURCE_LAKEHOUSE_ID                   = fabric_lakehouse.this.id
    SOURCE_LAKEHOUSE_NAME                 = var.lakehouse_name
    PURVIEW_ACCOUNT                       = var.purview_account_name
    PURVIEW_ENDPOINT                      = data.external.purview_catalog_endpoint.result.uri
    CLASSIFICATION_NAMESPACE              = var.classification_namespace
    SENSITIVITY_LEVEL_MAP_JSON            = jsonencode(var.sensitivity_levels)
    # Identity-based AzureWebJobsStorage: only this prefixed setting is needed.
    # The host uses it to find host-level storage (host secrets, function key
    # store, scale-controller state, EH listener checkpoints/leases) over
    # Microsoft Entra via the function's system-assigned MI.
    #
    # IMPORTANT: do NOT also set `AzureWebJobsStorage` (without a suffix), even
    # to "". An empty `AzureWebJobsStorage` was found to suppress the
    # identity-based path and silently disable the EH listener (no telemetry,
    # no invocations, stale lease blobs) on Flex Consumption. The line was
    # removed deliberately; if azurerm starts auto-injecting a broken value,
    # use a `lifecycle { ignore_changes = ... }` block instead of re-adding it.
    AzureWebJobsStorage__accountName      = azurerm_storage_account.func.name
    # Required for the Python v2 programming model: tells the host to discover
    # functions by importing function_app.py and reading its decorators
    # (instead of scanning per-function function.json files).
    AzureWebJobsFeatureFlags               = "EnableWorkerIndexing"
    # Event Hub trigger uses identity-based binding. The connection name in
    # function_app.py is "PurviewEvents"; the host resolves the FQNS via this
    # prefixed setting and authenticates using the function's MI.
    PurviewEvents__fullyQualifiedNamespace = "${azurerm_eventhub_namespace.purview_events.name}.servicebus.windows.net"
    # REQUIRED on Flex Consumption (and recommended elsewhere): tells the host
    # AND the platform scale controller to authenticate to Event Hubs using
    # the function's system-assigned managed identity. Without this, the
    # scale controller can't poll the EH for events, so it never scales up
    # an instance to process them — the listener appears DEAD even though
    # the function is healthy.
    PurviewEvents__credential = "managedidentity"
    # NOTE: Do NOT set WEBSITE_RUN_FROM_PACKAGE on Flex Consumption.
    # Flex uses functionAppConfig.deployment.storage (configured by the
    # storage_container_* arguments above), and WEBSITE_RUN_FROM_PACKAGE
    # takes precedence and blocks the Flex deploy pipeline with
    # "RunFromExternalUrlException: Deployment is not needed in this case".
  }

  site_config {
    application_insights_connection_string = azurerm_application_insights.func.connection_string

    # Allow the Azure Portal "Test/Run" UI to invoke the function.
    cors {
      allowed_origins     = ["https://portal.azure.com"]
      support_credentials = false
    }
  }
}

# Function MI needs Storage Blob Data Owner on its own deployment storage
# (Flex Consumption uses MI to fetch the package).
resource "azurerm_role_assignment" "func_storage" {
  scope                = azurerm_storage_account.func.id
  role_definition_name = "Storage Blob Data Owner"
  principal_id         = azurerm_function_app_flex_consumption.func.identity[0].principal_id
}

# AzureWebJobsStorage with MI needs Queue + Table data plane access too
# (host stores leases, secrets cache, scale metrics in queues/tables).
resource "azurerm_role_assignment" "func_storage_queue" {
  scope                = azurerm_storage_account.func.id
  role_definition_name = "Storage Queue Data Contributor"
  principal_id         = azurerm_function_app_flex_consumption.func.identity[0].principal_id
}

resource "azurerm_role_assignment" "func_storage_table" {
  scope                = azurerm_storage_account.func.id
  role_definition_name = "Storage Table Data Contributor"
  principal_id         = azurerm_function_app_flex_consumption.func.identity[0].principal_id
}

# Flex Consumption requires an actual deploy call to load code into wwwroot;
# the storage_container_* config on the app only points at the deployment
# location, it doesn't push the package. The azurerm provider doesn't have a
# Flex-deploy resource yet, so shell out to `az functionapp deployment source
# config-zip`. Re-runs whenever the zip hash changes.
resource "null_resource" "function_deploy" {
  triggers = {
    zip_sha256       = data.archive_file.function_zip.output_sha256
    function_app_id  = azurerm_function_app_flex_consumption.func.id
    storage_role_id  = azurerm_role_assignment.func_storage.id
  }

  # The az CLI's post-deploy "host key check" sporadically returns exit 1
  # even when the zip deploy itself succeeded (202 + sync triggers). Verify
  # the function is registered after the deploy and treat that as the
  # success signal instead of trusting the CLI exit code.
  provisioner "local-exec" {
    interpreter = ["pwsh", "-NoProfile", "-Command"]
    command     = <<-EOT
      $ErrorActionPreference = 'Continue'
      az functionapp deployment source config-zip `
        --resource-group ${var.phase2_resource_group} `
        --name ${var.function_app_name} `
        --src ${data.archive_file.function_zip.output_path} `
        --build-remote true 2>&1 | Out-Host
      Start-Sleep -Seconds 30
      $fns = az functionapp function list `
        --resource-group ${var.phase2_resource_group} `
        --name ${var.function_app_name} `
        --query "[].name" -o tsv 2>$null
      if (-not $fns) {
        Write-Error "Deploy verification failed: no functions registered on ${var.function_app_name}"
        exit 1
      }
      Write-Host "Deployed functions: $fns"
    EOT
  }

  depends_on = [
    azurerm_function_app_flex_consumption.func,
    azurerm_role_assignment.func_storage,
    azurerm_role_assignment.func_storage_queue,
    azurerm_role_assignment.func_storage_table,
    azurerm_storage_blob.function_zip,
  ]
}

# Function MI needs to read OneLake Files (Delta logs).
# Granted via Fabric workspace role assignment (Viewer is enough for Files reads).
# fabric_workspace_role_assignment is part of the microsoft/fabric provider.
resource "fabric_workspace_role_assignment" "func_workspace_viewer" {
  workspace_id = var.workspace_id
  principal = {
    id   = azurerm_function_app_flex_consumption.func.identity[0].principal_id
    type = "ServicePrincipal"
  }
  role = "Contributor"
}

# --- Event Hub: trigger function on Purview scan status events --------------
#
# Purview Unified accounts (post-rebrand) no longer publish to Azure Event
# Grid system topics — `Microsoft.Purview.Accounts` is no longer a registered
# topic type. The supported path is:
#   Purview diagnostic settings -> Event Hub -> Function (eventHubTrigger)
#
# Diagnostic category `ScanStatusLogEvent` carries the same payload the legacy
# system topic used to emit. We filter to successful scans inside the function
# (the diag pipeline doesn't support payload-based filters).

resource "azurerm_eventhub_namespace" "purview_events" {
  name                = "ehns-fabricsens-rh"
  location            = var.phase2_location
  resource_group_name = var.phase2_resource_group
  sku                 = "Standard"
  capacity            = 1
}

resource "azurerm_eventhub" "scan_status" {
  name              = "purview-scan-status"
  namespace_id      = azurerm_eventhub_namespace.purview_events.id
  partition_count   = 2
  message_retention = 1
}

# Diagnostic settings authenticate to Event Hub via an authorization rule on
# the namespace (not via MI yet — diag settings -> EH still requires SAS).
resource "azurerm_eventhub_namespace_authorization_rule" "diag_send" {
  name                = "diag-send"
  namespace_name      = azurerm_eventhub_namespace.purview_events.name
  resource_group_name = var.phase2_resource_group
  listen              = false
  send                = true
  manage              = false
}

# Wire Purview's `ScanStatusLogEvent` category to the Event Hub.
resource "azurerm_monitor_diagnostic_setting" "purview_to_eh" {
  name                           = "scan-status-to-eh"
  target_resource_id             = local.purview_account_id
  eventhub_authorization_rule_id = azurerm_eventhub_namespace_authorization_rule.diag_send.id
  eventhub_name                  = azurerm_eventhub.scan_status.name

  enabled_log {
    category = "ScanStatusLogEvent"
  }
}

# Function MI needs Receive on the Event Hub for the eventHubTrigger to use
# identity-based binding (no SAS in app settings).
resource "azurerm_role_assignment" "func_eh_receiver" {
  scope                = azurerm_eventhub_namespace.purview_events.id
  role_definition_name = "Azure Event Hubs Data Receiver"
  principal_id         = azurerm_function_app_flex_consumption.func.identity[0].principal_id
}

# NOTE: Data Curator on the Purview collection must be granted manually via
# the Purview UI for the Function MI (`func-fabricsens-rh`):
#   Purview portal -> Data Map -> Collections -> {collection containing the
#   Fabric source} -> Role assignments -> Data curators -> Add -> select the
#   Function App's managed identity.
#
# The metadata-roles REST API was attempted via restapi_object but the path
# /policystore/metadataRoles/{id}/members 404s in this account (collection id
# format / API surface inconsistent across Purview versions). Manual grant is
# the supported path for now.
