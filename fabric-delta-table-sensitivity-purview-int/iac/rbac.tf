# =============================================================================
# Role assignments (data-plane RBAC) for the Function MI and Purview MI
# =============================================================================
# All role assignments in one place so PRs that change permissions are easy
# to review and audit.
#
# NOTE: Data Curator on the Purview collection must still be granted manually
# via the Purview UI for the Function MI (`func-fabricsens-rh`):
#   Purview portal -> Data Map -> Collections -> {collection containing the
#   Fabric source} -> Role assignments -> Data curators -> Add -> select the
#   Function App's managed identity.
#
# The metadata-roles REST API was attempted via restapi_object but the path
# /policystore/metadataRoles/{id}/members 404s in this account (collection id
# format / API surface inconsistent across Purview versions). Manual grant is
# the supported path for now.

# --- Function MI -> its own deployment storage ------------------------------
# Flex Consumption uses MI to fetch the package; needs Blob Data Owner.
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

# --- Function MI -> Event Hub Data Receiver ---------------------------------
# Function MI needs Receive on the Event Hub for the eventHubTrigger to use
# identity-based binding (no SAS in app settings).
resource "azurerm_role_assignment" "func_eh_receiver" {
  scope                = azurerm_eventhub_namespace.purview_events.id
  role_definition_name = "Azure Event Hubs Data Receiver"
  principal_id         = azurerm_function_app_flex_consumption.func.identity[0].principal_id
}

# --- Purview MI -> Event Hub Contributor ------------------------------------
# Purview's own MI needs Contributor on the EH namespace so its
# kafkaConfigurations resource can publish Atlas notifications to it.
resource "azurerm_role_assignment" "purview_eh_contributor" {
  scope                = azurerm_eventhub_namespace.purview_events.id
  role_definition_name = "Contributor"
  principal_id         = data.azapi_resource.purview_account.identity[0].principal_id
}

# Purview MI also needs Data Sender on the atlas-notifications hub itself —
# kafkaConfigurations PUT validates this at create time and 409s without it.
resource "azurerm_role_assignment" "purview_eh_data_sender" {
  scope                = azurerm_eventhub.atlas_notifications.id
  role_definition_name = "Azure Event Hubs Data Sender"
  principal_id         = data.azapi_resource.purview_account.identity[0].principal_id
}

# --- Function MI -> Fabric workspace ----------------------------------------
# Function MI needs to read OneLake Files (Delta logs).
# Granted via Fabric workspace role assignment (Viewer is enough for Files
# reads, but Contributor is required to write TBLPROPERTIES from the
# sync_classification flow). fabric_workspace_role_assignment is part of the
# microsoft/fabric provider.
resource "fabric_workspace_role_assignment" "func_workspace_viewer" {
  workspace_id = var.workspace_id
  principal = {
    id   = azurerm_function_app_flex_consumption.func.identity[0].principal_id
    type = "ServicePrincipal"
  }
  role = "Contributor"
}
