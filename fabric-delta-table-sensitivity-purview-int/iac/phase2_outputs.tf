output "function_app_name" {
  description = "Phase 2 Function app name."
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
