targetScope = 'resourceGroup'

param operatorVnetId string
param operatorIdentityId string
param operatorPrincipalId string

resource foundationVnet 'Microsoft.Network/virtualNetworks@2024-07-01' existing = { name: 'vnet-aicg-sn5edmznrgh7s' }
resource registry 'Microsoft.ContainerRegistry/registries@2025-04-01' existing = { name: 'craicgsn5edmznrgh7s' }
resource storage 'Microsoft.Storage/storageAccounts@2025-01-01' existing = { name: 'staicgsn5edmznrgh7s' }
resource blobs 'Microsoft.Storage/storageAccounts/blobServices@2025-01-01' existing = { parent: storage, name: 'default' }
resource inputs 'Microsoft.Storage/storageAccounts/blobServices/containers@2025-01-01' existing = { parent: blobs, name: 'inputs' }
resource outputs 'Microsoft.Storage/storageAccounts/blobServices/containers@2025-01-01' existing = { parent: blobs, name: 'outputs' }
resource workspace 'Microsoft.OperationalInsights/workspaces@2025-02-01' existing = { name: 'log-aicg-sn5edmznrgh7s' }

resource peering 'Microsoft.Network/virtualNetworks/virtualNetworkPeerings@2024-07-01' = {
  parent: foundationVnet
  name: 'to-aicg-operator'
  properties: {
    remoteVirtualNetwork: { id: operatorVnetId }
    allowVirtualNetworkAccess: true
    allowForwardedTraffic: false
    allowGatewayTransit: false
    useRemoteGateways: false
  }
}

var dnsNames = [
  'privatelink.azurecr.io'
  'privatelink.blob.${environment().suffixes.storage}'
  'privatelink.monitor.azure.com'
  'privatelink.oms.opinsights.azure.com'
  'privatelink.ods.opinsights.azure.com'
  'privatelink.agentsvc.azure-automation.net'
]
resource zones 'Microsoft.Network/privateDnsZones@2024-06-01' existing = [for name in dnsNames: { name: name }]
resource links 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = [for (name, i) in dnsNames: {
  parent: zones[i]
  name: 'link-aicg-operator'
  location: 'global'
  properties: { registrationEnabled: false, virtualNetwork: { id: operatorVnetId } }
}]

// The operator is distinct from the job identity. Permissions expire operationally
// when these four explicit assignments and the temporary identity are deleted.
resource acrPush 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: registry
  name: guid(registry.id, operatorIdentityId, 'operator-acr-push')
  properties: {
    principalId: operatorPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '8311e382-0749-4cb8-b61a-304f252e45ec')
  }
}
resource inputWriter 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: inputs
  name: guid(inputs.id, operatorIdentityId, 'operator-input-upload')
  properties: {
    principalId: operatorPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
  }
}
resource outputReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: outputs
  name: guid(outputs.id, operatorIdentityId, 'operator-output-read')
  properties: {
    principalId: operatorPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1')
  }
}
resource logReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: workspace
  name: guid(workspace.id, operatorIdentityId, 'operator-log-read')
  properties: {
    principalId: operatorPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '73c42c96-874c-492b-b04d-ab87d138a893')
  }
}

var linkIds = [for (name, i) in dnsNames: links[i].id]
output cleanupResourceIds array = concat(
  [peering.id, acrPush.id, inputWriter.id, outputReader.id, logReader.id],
  linkIds
)
