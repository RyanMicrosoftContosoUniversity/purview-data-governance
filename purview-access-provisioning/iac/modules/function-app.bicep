// ---------------------------------------------------------------------------
// Module: Function App (Python 3.11, Linux, Consumption) + App Insights
// ---------------------------------------------------------------------------

@description('Azure region for all resources.')
param location string

@description('Deployment environment name (dev, prod, etc.).')
param environmentName string

@description('Unique suffix for globally unique resource names.')
param uniqueSuffix string

@description('Storage Account connection string for AzureWebJobsStorage and queue trigger.')
@secure()
param storageConnectionString string

@description('URI of the Key Vault instance.')
param keyVaultUri string

@description('Name of the Storage Queue for access requests.')
param queueName string

@description('Microsoft Purview account name.')
param purviewAccountName string

var functionAppName = 'pvfab-${environmentName}-func-${uniqueSuffix}'
var appServicePlanName = 'pvfab-${environmentName}-plan-${uniqueSuffix}'
var appInsightsName = 'pvfab-${environmentName}-ai-${uniqueSuffix}'

var tags = {
  project: 'purview-fabric-access'
  environment: environmentName
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    Request_Source: 'rest'
    RetentionInDays: 90
  }
}

resource appServicePlan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: appServicePlanName
  location: location
  tags: tags
  kind: 'linux'
  sku: {
    name: 'Y1'
    tier: 'Dynamic'
  }
  properties: {
    reserved: true // required for Linux
  }
}

resource functionApp 'Microsoft.Web/sites@2023-12-01' = {
  name: functionAppName
  location: location
  tags: tags
  kind: 'functionapp,linux'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: appServicePlan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'Python|3.11'
      pythonVersion: '3.11'
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
      appSettings: [
        {
          name: 'AzureWebJobsStorage'
          value: storageConnectionString
        }
        {
          name: 'FUNCTIONS_WORKER_RUNTIME'
          value: 'python'
        }
        {
          name: 'FUNCTIONS_EXTENSION_VERSION'
          value: '~4'
        }
        {
          name: 'KEY_VAULT_URI'
          value: keyVaultUri
        }
        {
          name: 'QUEUE_NAME'
          value: queueName
        }
        {
          name: 'STORAGE_QUEUE_CONNECTION'
          value: storageConnectionString
        }
        {
          name: 'PURVIEW_ACCOUNT_NAME'
          value: purviewAccountName
        }
        {
          name: 'FABRIC_DEFAULT_ROLE'
          value: 'Viewer'
        }
        {
          name: 'APPINSIGHTS_INSTRUMENTATIONKEY'
          value: appInsights.properties.InstrumentationKey
        }
      ]
    }
  }
}

@description('Name of the deployed Function App.')
output functionAppName string = functionApp.name

@description('System-assigned managed identity principal ID.')
output principalId string = functionApp.identity.principalId

@description('Default hostname of the Function App.')
output defaultHostname string = functionApp.properties.defaultHostName
