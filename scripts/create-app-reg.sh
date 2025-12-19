az ad app create \
    --display-name "FabricAuditIntegrationApp" \
    --sign-in-audience "AzureADMyOrg" \

APP_ID=$(az ad app list --display-name "FabricAuditIntegrationApp" --query "[0].appId" -o tsv)
TENANT_ID=$(az account show --query "tenantId" -o tsv)

# create client secret
az ad app credential reset \
    --id $APP_ID \
    --display-name "FabricAuditIntegrationAppSecret" \
    --years 2

echo "Application (client) ID: $APP_ID"
echo "Directory (tenant) ID: $TENANT_ID"
    --query "appId" -o tsv  


# secret stored in kv: kvfabricprodeus2rh

