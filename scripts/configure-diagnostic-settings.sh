# Configure diagnostic settings for audit logs on a supported Azure resource
# Note: Microsoft Fabric capacities do NOT support diagnostic settings.
# Use this template for supported resources like Azure Purview accounts, Storage Accounts, etc.
# Replace placeholders with actual values.

# Example for Azure Purview account (if you have one):
# az monitor diagnostic-settings create \
#   --name PurviewAuditToEventHub \
#   --resource <PURVIEW-ACCOUNT-NAME> \
#   --resource-group <RESOURCE-GROUP> \
#   --resource-type accounts \
#   --resource-namespace Microsoft.Purview \
#   --event-hub fabric-telemetry-eh \
#   --event-hub-rule RootManageSharedAccessKey \
#   --logs '[{"category": "AuditEvent", "enabled": true}]'

# Example for Azure Storage Account:
# az monitor diagnostic-settings create \
#   --name StorageAuditToEventHub \
#   --resource <STORAGE-ACCOUNT-NAME> \
#   --resource-group <RESOURCE-GROUP> \
#   --resource-type Microsoft.Storage/storageAccounts \
#   --event-hub fabric-telemetry-eh \
#   --event-hub-rule RootManageSharedAccessKey \
#   --logs '[{"category": "StorageRead", "enabled": true}, {"category": "StorageWrite", "enabled": true}]' \
#   --metrics '[{"category": "Transaction", "enabled": true}]'

# For Fabric audit logs, use unified audit logging (already enabled) and access via Microsoft 365 compliance center.

# Setup for streaming Fabric audit logs to Event Hub via Log Analytics
# 1. Create Log Analytics workspace
az monitor log-analytics workspace create \
  --resource-group fabric-monitoring-rg \
  --name fabric-audit-law \
  --location eastus \
  --sku PerGB2018

# 2. Create data export rule to stream AuditLogs to Event Hub
az monitor log-analytics workspace data-export create \
  --resource-group fabric-monitoring-rg \
  --workspace-name fabric-audit-law \
  --name FabricAuditExport \
  --destination /subscriptions/910ebf13-1058-405d-b6cf-eda03e5288d1/resourceGroups/fabric-monitoring-rg/providers/Microsoft.EventHub/namespaces/fabric-telemetry-ehns/eventhubs/fabric-telemetry-eh \
  --enable true \
  --table AuditLogs

# 3. Manual step: Connect Office 365 audit logs to the workspace
# In Azure Portal: Log Analytics workspaces > fabric-audit-law > Legacy solutions > Add > Office 365 Audit Logs
# Or in Microsoft 365 Admin Center > Audit > Connect to Azure Monitor > Select workspace