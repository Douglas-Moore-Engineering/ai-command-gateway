targetScope = 'resourceGroup'

@description('Azure region; defaults to the explicitly selected resource group region. Verify service availability and quota before deployment.')
param location string = resourceGroup().location

@description('Logical workload discriminator used only as a deterministic naming seed. Changing it creates a separate resource set.')
@minLength(1)
@maxLength(32)
param workloadName string = 'aicg'

@description('False bootstraps private infrastructure. Set true only after publishing and verifying the image digest in the private registry.')
param provisionJob bool = false

@description('Published image digest, sha256 followed by a colon and 64 lowercase hex digits. Required when provisionJob is true; deployment script validates format.')
@maxLength(71)
param imageDigest string = ''

@description('Explicit job behavior. Demo runs synthetic checks; dataset-analysis processes the five pinned Blob inputs.')
@allowed(['demo', 'dataset-analysis'])
param jobMode string = 'demo'

@description('Output Blob lifecycle age in days. Deletion is asynchronous; seven additional days of soft-delete recovery apply. Inputs are never expired by this rule.')
@minValue(7)
@maxValue(90)
param artifactRetentionDays int = 30

@description('Log Analytics retention, separate from Blob artifact retention.')
@minValue(30)
@maxValue(90)
param logRetentionDays int = 30

@description('New isolated VNet address space. Validate overlap against target networks before deployment.')
param vnetAddressPrefix string = '10.42.0.0/16'

@description('Dedicated /23 Container Apps workload-profile subnet inside the VNet.')
param environmentSubnetPrefix string = '10.42.0.0/23'

@description('Separate /24 private-endpoint subnet inside the VNet.')
param privateEndpointSubnetPrefix string = '10.42.2.0/24'

var suffix = uniqueString(resourceGroup().id, workloadName)
var nameStem = 'aicg-${suffix}'
var tags = {
  workload: 'ai-command-gateway'
  environment: 'nonproduction'
  authority: 'mock-only'
  managedBy: 'bicep'
}

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2024-11-30' = {
  name: 'id-${nameStem}'
  location: location
  tags: tags
}

module network './modules/network.bicep' = {
  name: '${nameStem}-network'
  params: {
    location: location
    nameStem: nameStem
    tags: tags
    vnetAddressPrefix: vnetAddressPrefix
    environmentSubnetPrefix: environmentSubnetPrefix
    privateEndpointSubnetPrefix: privateEndpointSubnetPrefix
  }
}

module monitoring './modules/monitoring.bicep' = {
  name: '${nameStem}-monitoring'
  params: {
    location: location
    nameStem: nameStem
    tags: tags
    logRetentionDays: logRetentionDays
    privateEndpointSubnetId: network.outputs.privateEndpointSubnetId
    monitorDnsZoneIds: network.outputs.monitorDnsZoneIds
  }
}

module storage './modules/storage.bicep' = {
  name: '${nameStem}-storage'
  params: {
    location: location
    nameStem: nameStem
    storageName: 'staicg${suffix}'
    tags: tags
    principalId: identity.properties.principalId
    identityResourceId: identity.id
    artifactRetentionDays: artifactRetentionDays
    privateEndpointSubnetId: network.outputs.privateEndpointSubnetId
    blobDnsZoneId: network.outputs.blobDnsZoneId
    workspaceId: monitoring.outputs.workspaceId
  }
}

module registry './modules/registry.bicep' = {
  name: '${nameStem}-registry'
  params: {
    location: location
    nameStem: nameStem
    registryName: 'craicg${suffix}'
    tags: tags
    principalId: identity.properties.principalId
    identityResourceId: identity.id
    privateEndpointSubnetId: network.outputs.privateEndpointSubnetId
    registryDnsZoneId: network.outputs.registryDnsZoneId
    workspaceId: monitoring.outputs.workspaceId
  }
}

module environment './modules/environment.bicep' = {
  name: '${nameStem}-environment'
  params: {
    location: location
    nameStem: nameStem
    tags: tags
    environmentSubnetId: network.outputs.environmentSubnetId
    workspaceId: monitoring.outputs.workspaceId
  }
}

module job './modules/job.bicep' = if (provisionJob) {
  name: '${nameStem}-job'
  params: {
    location: location
    jobName: 'job-${nameStem}'
    tags: tags
    environmentId: environment.outputs.environmentId
    identityId: identity.id
    identityClientId: identity.properties.clientId
    registryLoginServer: registry.outputs.loginServer
    imageDigest: imageDigest
    storageAccountUrl: storage.outputs.accountUrl
    jobMode: jobMode
  }
}

output registryName string = registry.outputs.registryName
output registryLoginServer string = registry.outputs.loginServer
output storageAccountName string = storage.outputs.accountName
output storageAccountUrl string = storage.outputs.accountUrl
output inputContainerName string = 'inputs'
output outputContainerName string = 'outputs'
output managedIdentityClientId string = identity.properties.clientId
output managedIdentityResourceId string = identity.id
output environmentName string = environment.outputs.environmentName
output logAnalyticsWorkspaceId string = monitoring.outputs.workspaceId
output vnetId string = network.outputs.vnetId
output jobName string = 'job-${nameStem}'
output jobResourceId string = provisionJob ? job!.outputs.jobId : ''

