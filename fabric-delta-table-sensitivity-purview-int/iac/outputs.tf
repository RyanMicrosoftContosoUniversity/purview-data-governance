# =============================================================================
# Outputs
# =============================================================================

# --- Fabric --------------------------------------------------------------

output "lakehouse_id" {
  description = "The ID of the created Fabric lakehouse."
  value       = fabric_lakehouse.this.id
}

output "lakehouse_properties" {
  description = "Read-only properties exposed by the lakehouse resource (includes SQL endpoint info when available)."
  value       = fabric_lakehouse.this.properties
}

output "notebook_id" {
  description = "The ID of the created Fabric notebook."
  value       = fabric_notebook.this.id
}

output "notebook_run_trigger_id" {
  description = "ID of the null_resource that triggered the on-demand notebook run."
  value       = null_resource.run_notebook_once.id
}

# --- Function ------------------------------------------------------------

output "function_app_name" {
  description = "Function app name."
  value       = azurerm_function_app_flex_consumption.func.name
}

output "function_app_principal_id" {
  description = "System-assigned managed identity principal ID for the Function."
  value       = azurerm_function_app_flex_consumption.func.identity[0].principal_id
}

output "function_app_url" {
  description = "Default hostname of the Function app."
  value       = "https://${azurerm_function_app_flex_consumption.func.default_hostname}"
}

# --- Purview -------------------------------------------------------------

output "purview_account_id" {
  description = "Purview account resource ID."
  value       = local.purview_account_id
}

output "purview_atlas_endpoint" {
  description = "Purview Atlas API endpoint."
  value       = "https://${var.purview_account_name}.purview.azure.com/catalog/api/atlas/v2"
}

output "classification_typedef_names" {
  description = "Names of the 4 custom classification typedefs created in Purview."
  value       = [for k, v in local.classification_defs : v.typedef_name]
}

output "purview_atlas_notification_config_id" {
  description = "Resource ID of the Purview kafkaConfigurations notification wiring."
  value       = azapi_resource.purview_atlas_notification_config.id
}

# --- Event Hub -----------------------------------------------------------

output "atlas_notifications_event_hub_name" {
  description = "Name of the Event Hub that receives Purview Atlas Notification messages."
  value       = azurerm_eventhub.atlas_notifications.name
}
