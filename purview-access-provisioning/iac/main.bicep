// ---------------------------------------------------------------------------
// Orchestrator: Purview-to-Fabric self-service access workflow
// Deploys Storage + Queue, Function App + App Insights, Key Vault w/ RBAC
// ---------------------------------------------------------------------------

targetScope = 'resourceGroup'

// ── Parameters ──────────────────────────────────────────────────────────────

@description('Azure region for all resources. Defaults to the resource group location.')
param location string = resourceGroup().location

@description('Deployment environment name (e.g., dev, prod).')
@allowed(['dev', 'staging', 'prod'])
param environmentName string

@description('Name of the Microsoft Purview account to integrate with.')
param purviewAccountName string

@description('Microsoft Fabric workspace ID that will receive access grants.')
param fabricWorkspaceId string

// ── Variables ───────────────────────────────────────────────────────────────

var uniqueSuffix = uniqueString(resourceGroup().id)

var tags = {
  project: 'purview-fabric-access'
  environment: environmentName
}

// ── Derived names ───────────────────────────────────────────────────────────
// Construct the Key Vault URI from the deterministic naming convention so the
// Function App module doesn't depend on the Key Vault module output, avoiding
// a circular dependency (Function App ↔ Key Vault).
var keyVaultName = 'pvfab-${environmentName}-kv-${uniqueSuffix}'
var keyVaultUri = 'https://${keyVaultName}${environment().suffixes.keyvaultDns}/'

// ── Modules ─────────────────────────────────────────────────────────────────

// 1. Storage Account + Queue (no dependencies)
module storage 'modules/storage.bicep' = {
  name: 'storage-${uniqueSuffix}'
  params: {
    location: location
    environmentName: environmentName
    uniqueSuffix: uniqueSuffix
  }
}

// 2. Function App (depends on Storage only; Key Vault URI is pre-computed)
module functionApp 'modules/function-app.bicep' = {
  name: 'functionApp-${uniqueSuffix}'
  params: {
    location: location
    environmentName: environmentName
    uniqueSuffix: uniqueSuffix
    storageConnectionString: storage.outputs.connectionString
    keyVaultUri: keyVaultUri
    queueName: storage.outputs.queueName
    purviewAccountName: purviewAccountName
  }
}

// 3. Key Vault + role assignment (depends on Function App for principalId)
module keyVault 'modules/keyvault.bicep' = {
  name: 'keyVault-${uniqueSuffix}'
  params: {
    location: location
    environmentName: environmentName
    uniqueSuffix: uniqueSuffix
    functionAppPrincipalId: functionApp.outputs.principalId
  }
}

// ── Outputs ─────────────────────────────────────────────────────────────────

@description('Deployed Storage Account name.')
output storageAccountName string = storage.outputs.storageAccountName

@description('Name of the access-request queue.')
output queueName string = storage.outputs.queueName

@description('Deployed Function App name.')
output functionAppName string = functionApp.outputs.functionAppName

@description('Function App default hostname.')
output functionAppHostname string = functionApp.outputs.defaultHostname

@description('Key Vault name.')
output keyVaultName string = keyVault.outputs.vaultName

@description('Key Vault URI.')
output keyVaultUri string = keyVault.outputs.vaultUri

@description('Resource tags applied to all resources.')
output appliedTags object = tags

@description('Fabric Workspace ID (echoed for downstream pipeline use).')
output fabricWorkspaceId string = fabricWorkspaceId
