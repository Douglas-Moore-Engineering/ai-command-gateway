targetScope = 'resourceGroup'

@description('Region of the existing private foundation and the new manual job.')
param location string = resourceGroup().location

@description('The exact naming seed used for the existing foundation. This wrapper does not create or update foundation resources.')
@minLength(1)
@maxLength(32)
param workloadName string = 'aicg'

@description('Reviewed published sha256 image digest; deployment preflight validates lowercase hexadecimal syntax.')
@minLength(71)
@maxLength(71)
param imageDigest string

@description('Explicit runner behavior; this deployment provisions the manual job but does not start an execution.')
@allowed(['demo', 'dataset-analysis'])
param jobMode string = 'demo'

// Preserve main.bicep's deterministic names and tags while leaving its network,
// peerings, endpoints, identities, RBAC, storage and monitoring configurations alone.
var suffix = uniqueString(resourceGroup().id, workloadName)
var nameStem = 'aicg-${suffix}'
var tags = {
  workload: 'ai-command-gateway'
  environment: 'nonproduction'
  authority: 'mock-only'
  managedBy: 'bicep'
}

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2024-11-30' existing = {
  name: 'id-${nameStem}'
}

resource environment 'Microsoft.App/managedEnvironments@2025-07-01' existing = {
  name: 'cae-${nameStem}'
}

resource registry 'Microsoft.ContainerRegistry/registries@2025-11-01' existing = {
  name: 'craicg${suffix}'
}

resource storage 'Microsoft.Storage/storageAccounts@2025-01-01' existing = {
  name: 'staicg${suffix}'
}

module job './modules/job.bicep' = {
  name: '${nameStem}-job'
  params: {
    location: location
    jobName: 'job-${nameStem}'
    tags: tags
    environmentId: environment.id
    identityId: identity.id
    identityClientId: identity.properties.clientId
    registryLoginServer: registry.properties.loginServer
    imageDigest: imageDigest
    storageAccountUrl: storage.properties.primaryEndpoints.blob
    jobMode: jobMode
  }
}

output jobName string = 'job-${nameStem}'
output jobResourceId string = job.outputs.jobId
