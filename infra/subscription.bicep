targetScope = 'subscription'

@description('Name of a NEW resource group. Verify absence before what-if and again before any apply. For an existing group, use the resource-group deployment scripts instead; this wrapper would update group tags.')
@minLength(1)
@maxLength(90)
param resourceGroupName string

@description('Explicitly reviewed region for the new resource group and all regional foundation resources.')
param location string

@description('Logical workload discriminator, passed unchanged to the existing resource-group foundation.')
@minLength(1)
@maxLength(32)
param workloadName string = 'aicg'

@description('New VNet IPv4 address space. Validate canonical CIDR, containment, reserved ranges and target-network conflicts before review.')
param vnetAddressPrefix string = '10.42.0.0/16'

@description('Dedicated Container Apps workload-profile subnet; /27 or larger and contained in the VNet.')
param environmentSubnetPrefix string = '10.42.0.0/23'

@description('Private-endpoint subnet including Azure Monitor Private Link; /27 or larger, inside the VNet and disjoint from the environment subnet.')
param privateEndpointSubnetPrefix string = '10.42.2.0/24'

@description('Derived output lifecycle age in days. Inputs are excluded; deletion is asynchronous with additional soft-delete retention.')
@minValue(7)
@maxValue(90)
param artifactRetentionDays int = 30

@description('Log Analytics retention in days, separate from artifact lifecycle retention.')
@minValue(30)
@maxValue(90)
param logRetentionDays int = 30

// The caller must reject an existing group. ARM resource declarations are not
// create-only operations and would otherwise update that group's tags.
resource newResourceGroup 'Microsoft.Resources/resourceGroups@2025-04-01' = {
  name: resourceGroupName
  location: location
  tags: {
    workload: 'ai-command-gateway'
    environment: 'nonproduction'
    authority: 'mock-only'
    managedBy: 'bicep'
  }
}

// Keep the established bootstrap deployment name so its outputs can be read by
// the existing publishing instructions. This wrapper cannot enable a job.
module foundation './main.bicep' = {
  name: 'aicg-bootstrap'
  scope: newResourceGroup
  params: {
    location: location
    workloadName: workloadName
    provisionJob: false
    imageDigest: ''
    jobMode: 'demo'
    vnetAddressPrefix: vnetAddressPrefix
    environmentSubnetPrefix: environmentSubnetPrefix
    privateEndpointSubnetPrefix: privateEndpointSubnetPrefix
    artifactRetentionDays: artifactRetentionDays
    logRetentionDays: logRetentionDays
  }
}

output resourceGroupName string = newResourceGroup.name
output resourceGroupId string = newResourceGroup.id
output foundationDeploymentName string = foundation.name
output registryName string = foundation.outputs.registryName
output registryLoginServer string = foundation.outputs.registryLoginServer
output storageAccountName string = foundation.outputs.storageAccountName
output storageAccountUrl string = foundation.outputs.storageAccountUrl
output managedIdentityClientId string = foundation.outputs.managedIdentityClientId
output managedIdentityResourceId string = foundation.outputs.managedIdentityResourceId
output environmentName string = foundation.outputs.environmentName
output logAnalyticsWorkspaceId string = foundation.outputs.logAnalyticsWorkspaceId
output vnetId string = foundation.outputs.vnetId
output jobProvisioned bool = false
