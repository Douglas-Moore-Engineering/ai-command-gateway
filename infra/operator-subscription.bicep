targetScope = 'subscription'

@description('New, disposable operator resource group. Never point this at the foundation group.')
param operatorResourceGroupName string = 'rg-ai-command-gateway-operator'
param foundationResourceGroupName string = 'rg-ai-command-gateway-dev'
param location string = 'eastus2'
@description('Verified regional VM SKU with at least two vCPUs of available quota.')
param vmSize string
@secure()
@description('OpenSSH public key; keep the matching private key outside Git.')
param adminPublicKey string
param imageVersion string = '24.04.202609040'

resource operatorGroup 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: operatorResourceGroupName
  location: location
  tags: {
    workload: 'ai-command-gateway'
    purpose: 'temporary-private-operator'
    cleanup: 'after-pilot-verification'
    managedBy: 'bicep'
  }
}

module operator './operator.bicep' = {
  name: 'aicg-private-operator'
  scope: operatorGroup
  params: {
    location: location
    foundationResourceGroupName: foundationResourceGroupName
    vmSize: vmSize
    adminPublicKey: adminPublicKey
    imageVersion: imageVersion
  }
}

output operatorResourceGroupName string = operatorGroup.name
output vmResourceId string = operator.outputs.vmResourceId
output bastionName string = operator.outputs.bastionName
output identityClientId string = operator.outputs.identityClientId
output operatorVnetId string = operator.outputs.operatorVnetId
output foundationCleanupResourceIds array = operator.outputs.foundationCleanupResourceIds
