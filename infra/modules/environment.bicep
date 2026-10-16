@description('Azure resource region.')
param location string
@description('Generated resource name stem.')
param nameStem string
@description('Nonproduction resource tags.')
param tags object
@description('Dedicated delegated Container Apps subnet ID.')
param environmentSubnetId string
@description('Diagnostic destination workspace resource ID.')
param workspaceId string

resource environment 'Microsoft.App/managedEnvironments@2025-07-01' = {
  name: 'cae-${nameStem}'
  location: location
  tags: tags
  properties: {
    publicNetworkAccess: 'Disabled'
    vnetConfiguration: { infrastructureSubnetId: environmentSubnetId, internal: true }
    workloadProfiles: [{ name: 'Consumption', workloadProfileType: 'Consumption' }]
    zoneRedundant: false
    appLogsConfiguration: { destination: 'azure-monitor' }
    peerAuthentication: { mtls: { enabled: true } }
    peerTrafficConfiguration: { encryption: { enabled: true } }
  }
}

// Azure Monitor diagnostic settings use a private Microsoft service channel;
// no Log Analytics shared keys or connection strings are supplied to the app.
resource diagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'environment-logs'
  scope: environment
  properties: {
    workspaceId: workspaceId
    logAnalyticsDestinationType: 'Dedicated'
    logs: [
      { category: 'ContainerAppConsoleLogs', enabled: true }
      { category: 'ContainerAppSystemLogs', enabled: true }
    ]
  }
}

output environmentId string = environment.id
output environmentName string = environment.name

