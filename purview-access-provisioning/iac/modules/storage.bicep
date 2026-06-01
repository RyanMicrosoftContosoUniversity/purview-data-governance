// ---------------------------------------------------------------------------
// Module: Storage Account + Queue for Purview access-request pipeline
// ---------------------------------------------------------------------------

@description('Azure region for all resources.')
param location string

@description('Deployment environment name (dev, prod, etc.).')
param environmentName string

@description('Unique suffix for globally unique resource names.')
param uniqueSuffix string

var storageAccountName = 'pvfab${environmentName}st${uniqueSuffix}'
var queueName = 'purview-access-requests'

var tags = {
  project: 'purview-fabric-access'
  environment: environmentName
}

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageAccountName
  location: location
  tags: tags
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
  properties: {
    supportsHttpsTrafficOnly: true
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
  }
}

resource queueService 'Microsoft.Storage/storageAccounts/queueServices@2023-05-01' = {
  parent: storageAccount
  name: 'default'
}

resource accessRequestQueue 'Microsoft.Storage/storageAccounts/queueServices/queues@2023-05-01' = {
  parent: queueService
  name: queueName
}

@description('Name of the deployed Storage Account.')
output storageAccountName string = storageAccount.name

@description('Connection string for the Storage Account.')
@secure()
output connectionString string = 'DefaultEndpointsProtocol=https;AccountName=${storageAccount.name};EndpointSuffix=${environment().suffixes.storage};AccountKey=${storageAccount.listKeys().keys[0].value}'

@description('Name of the access-request queue.')
output queueName string = queueName
