@description('Azure resource region.')
param location string
@description('Generated resource name stem.')
param nameStem string
@description('Nonproduction resource tags.')
param tags object
@description('Log Analytics retention in days.')
param logRetentionDays int
@description('Private endpoint subnet ID.')
param privateEndpointSubnetId string
@description('The five Azure Monitor private DNS zone IDs, including the shared Blob private DNS zone.')
param monitorDnsZoneIds array

resource workspace 'Microsoft.OperationalInsights/workspaces@2025-02-01' = {
  name: 'log-${nameStem}'
  location: location
  tags: tags
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: logRetentionDays
    features: {
      disableLocalAuth: true
      enableLogAccessUsingOnlyResourcePermissions: true
    }
    publicNetworkAccessForIngestion: 'Disabled'
    publicNetworkAccessForQuery: 'Disabled'
    workspaceCapping: { dailyQuotaGb: 1 }
  }
}

resource scope 'Microsoft.Insights/privateLinkScopes@2021-07-01-preview' = {
  name: 'ampls-${nameStem}'
  location: 'global'
  tags: tags
  properties: {
    accessModeSettings: {
      ingestionAccessMode: 'PrivateOnly'
      queryAccessMode: 'PrivateOnly'
    }
  }
}

resource scopedWorkspace 'Microsoft.Insights/privateLinkScopes/scopedResources@2021-07-01-preview' = {
  parent: scope
  name: 'workspace'
  properties: { linkedResourceId: workspace.id }
}

resource endpoint 'Microsoft.Network/privateEndpoints@2024-07-01' = {
  name: 'pep-${nameStem}-monitor'
  location: location
  tags: tags
  properties: {
    subnet: { id: privateEndpointSubnetId }
    privateLinkServiceConnections: [{
      name: 'monitor'
      properties: {
        privateLinkServiceId: scope.id
        groupIds: ['azuremonitor']
      }
    }]
  }
  dependsOn: [scopedWorkspace]
}

resource dnsGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-07-01' = {
  parent: endpoint
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [for (zoneId, index) in monitorDnsZoneIds: {
      name: 'monitor-${index}'
      properties: { privateDnsZoneId: zoneId }
    }]
  }
}

output workspaceId string = workspace.id

