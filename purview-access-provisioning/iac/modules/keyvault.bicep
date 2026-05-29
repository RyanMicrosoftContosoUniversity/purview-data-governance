// ---------------------------------------------------------------------------
// Module: Key Vault with RBAC authorization
// ---------------------------------------------------------------------------

@description('Azure region for all resources.')
param location string

@description('Deployment environment name (dev, prod, etc.).')
param environmentName string

@description('Unique suffix for globally unique resource names.')
param uniqueSuffix string

@description('Principal ID of the Function App managed identity to grant Key Vault Secrets User role.')
param functionAppPrincipalId string

var keyVaultName = 'pvfab-${environmentName}-kv-${uniqueSuffix}'

var tags = {
  project: 'purview-fabric-access'
  environment: environmentName
}

// Built-in role: Key Vault Secrets User
var keyVaultSecretsUserRoleId = '4633458b-17de-408a-b874-0445c86b69e6'

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: keyVaultName
  location: location
  tags: tags
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: subscription().tenantId
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 90
    enablePurgeProtection: true
  }
}

resource keyVaultSecretsUserRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, functionAppPrincipalId, keyVaultSecretsUserRoleId)
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', keyVaultSecretsUserRoleId)
    principalId: functionAppPrincipalId
    principalType: 'ServicePrincipal'
  }
}

@description('Name of the deployed Key Vault.')
output vaultName string = keyVault.name

@description('URI of the deployed Key Vault.')
output vaultUri string = keyVault.properties.vaultUri
