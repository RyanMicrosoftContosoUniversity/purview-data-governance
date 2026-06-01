# =============================================================================
# Event Hub namespace, hubs, and the Purview -> EH diagnostic setting
# =============================================================================
# Purview Unified accounts (post-rebrand) no longer publish to Azure Event
# Grid system topics — `Microsoft.Purview.Accounts` is no longer a registered
# topic type. The supported path is:
#   Purview diagnostic settings -> Event Hub -> Function (eventHubTrigger)
#
# Diagnostic category `ScanStatusLogEvent` carries the same payload the legacy
# system topic used to emit. We filter to successful scans inside the function
# (the diag pipeline doesn't support payload-based filters).
#
# The atlas_notifications EH is BYO storage for Purview Atlas
# ENTITY_NOTIFICATION_V2 messages; Purview is granted Contributor on the
# namespace (see rbac.tf) and wires itself up via the kafkaConfigurations
# resource in purview.tf.

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

resource "azurerm_eventhub" "atlas_notifications" {
  name              = var.atlas_notification_eventhub_name
  namespace_id      = azurerm_eventhub_namespace.purview_events.id
  partition_count   = 4
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
