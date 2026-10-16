@description('Azure resource region.')
param location string
@description('Generated job name.')
param jobName string
@description('Nonproduction resource tags.')
param tags object
@description('Private workload-profile environment resource ID.')
param environmentId string
@description('User-assigned identity resource ID.')
param identityId string
@description('User-assigned identity client ID for ManagedIdentityCredential.')
param identityClientId string
@description('Private registry login server.')
param registryLoginServer string
@description('Published immutable image digest; deployment preflight additionally validates sha256 syntax.')
@minLength(71)
@maxLength(71)
param imageDigest string
@description('HTTPS Blob service URL.')
param storageAccountUrl string
@description('Explicit runner mode.')
@allowed(['demo', 'dataset-analysis'])
param jobMode string

resource job 'Microsoft.App/jobs@2025-01-01' = {
  name: jobName
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${identityId}': {} }
  }
  properties: {
    environmentId: environmentId
    workloadProfileName: 'Consumption'
    configuration: {
      triggerType: 'Manual'
      replicaTimeout: 1800
      replicaRetryLimit: 0
      manualTriggerConfig: { parallelism: 1, replicaCompletionCount: 1 }
      registries: [{ server: registryLoginServer, identity: identityId }]
      identitySettings: [{ identity: identityId, lifecycle: 'Main' }]
    }
    template: {
      containers: [{
        name: 'gateway'
        image: '${registryLoginServer}/ai-command-gateway@${imageDigest}'
        command: ['python', '-m', 'ai_command_gateway.azure_job']
        resources: { cpu: 1, memory: '2Gi' }
        env: [
          { name: 'AZURE_CLIENT_ID', value: identityClientId }
          { name: 'AZURE_STORAGE_ACCOUNT_URL', value: storageAccountUrl }
          { name: 'AZURE_INPUT_CONTAINER', value: 'inputs' }
          { name: 'AZURE_OUTPUT_CONTAINER', value: 'outputs' }
          { name: 'AI_GATEWAY_JOB_MODE', value: jobMode }
          { name: 'AI_GATEWAY_WORKSPACE', value: '/tmp/ai-command-gateway' }
        ]
      }]
    }
  }
}

output jobId string = job.id

