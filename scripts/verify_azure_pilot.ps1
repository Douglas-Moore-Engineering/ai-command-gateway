#Requires -Version 5.1
<#
.SYNOPSIS
Read deployed pilot configuration from Azure Resource Manager and verify it.
.DESCRIPTION
GET requests only. Does not register providers, change resources, request keys,
access Blob/ACR data, resolve private DNS, or test workload connectivity.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$')]
    [string] $SubscriptionId,
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[a-zA-Z0-9][a-zA-Z0-9._()-]{0,89}$')]
    [string] $ResourceGroup,
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^sha256:[0-9a-f]{64}$')]
    [string] $ExpectedImageDigest,
    [Parameter(Mandatory = $true)]
    [ValidateSet('demo', 'dataset-analysis')]
    [string] $ExpectedJobMode,
    [switch] $OperatorPresent,
    [ValidatePattern('^[a-zA-Z0-9][a-zA-Z0-9._()-]{0,89}$')]
    [string] $OperatorResourceGroup = 'rg-ai-command-gateway-operator',
    [string] $OutputDirectory
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$workspaceRoot = Split-Path -Parent $PSScriptRoot
$subscriptionPath = '/subscriptions/' + $SubscriptionId
$groupPath = $subscriptionPath + '/resourceGroups/' + $ResourceGroup
$outputRoot = if ($OutputDirectory) { [IO.Path]::GetFullPath($OutputDirectory) } else { Join-Path $workspaceRoot 'outputs/azure-pilot-verification' }
$runId = [guid]::NewGuid().ToString()
$runRoot = Join-Path $outputRoot $runId
New-Item -ItemType Directory -Path $runRoot -Force | Out-Null
$checks = New-Object System.Collections.Generic.List[object]
$script:pilotFailureCode = $null
$script:pilotReadCount = 0
$report = [ordered]@{
    schema_version = '1.0.0'
    recorded_at_utc = [DateTime]::UtcNow.ToString('o')
    scope = 'Azure control-plane configuration only; no private DNS, connectivity, data-plane or job execution test'
    subscription_id = $SubscriptionId
    resource_group = $ResourceGroup
    bootstrap_deployment = 'aicg-bootstrap'
    expected_image_digest = $ExpectedImageDigest
    expected_job_mode = $ExpectedJobMode
    operator_expected_present = [bool] $OperatorPresent
    operator_resource_group = $OperatorResourceGroup
    run_id = $runId
    passed = $false
    error_code = $null
    checks = @()
    arm_get_requests = 0
    arm_read_diagnostics = @()
    last_read_step = $null
    resource_changes_performed = $false
    secrets_requested = $false
    dns_resolution_tested = $false
    data_plane_tested = $false
    job_execution_tested = $false
}

function Stop-Verification {
    param([string] $Code)
    $script:pilotFailureCode = $Code
    throw 'Pilot verification stopped; see the bounded error code in the report.'
}

function Get-ReadFailureKind {
    param([string] $Diagnostic)
    # Only known transient transport/status errors qualify. Authentication,
    # certificate, resource-not-found and unrecognized errors never retry.
    if ($Diagnostic -match '(?i)certificate.verify.failed|AuthorizationFailed|AuthenticationFailed|InvalidAuthenticationToken') { return 'cli_failure' }
    if ($Diagnostic -match '(?i)RemoteDisconnected|ConnectionResetError|ConnectionAbortedError|ReadTimeout|ConnectTimeout|read timed out|connection (?:was forcibly closed|reset|aborted)') { return 'transient_transport' }
    if ($Diagnostic -match '(?im)^ERROR:\s*(?:\((?:TooManyRequests|ServiceUnavailable|InternalServerError|GatewayTimeout|OperationTimedOut)\)|Too Many Requests\b|Internal Server Error\b|Bad Gateway\b|Service Unavailable\b|Gateway Timeout\b|Request Timeout\b)') { return 'transient_http' }
    return 'cli_failure'
}

function Read-Arm {
    param([string] $Path, [string] $Label)
    $url = if ($Path.StartsWith('https://')) { $Path } else { 'https://management.azure.com' + $Path }
    $uri = [uri] $url
    if ($uri.Scheme -ne 'https' -or $uri.Host -ne 'management.azure.com' -or
        -not $uri.IsDefaultPort -or $uri.UserInfo -or $uri.Fragment -or
        -not $uri.AbsolutePath.StartsWith($subscriptionPath + '/', [StringComparison]::OrdinalIgnoreCase)) {
        Stop-Verification ('unexpected_arm_url:' + $Label)
    }
    $report.last_read_step = $Label
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        $script:pilotReadCount++
        $combined = @()
        $exitCode = $null
        $launchFailed = $false
        $previousPreference = $ErrorActionPreference
        try {
            # PS 5.1 turns native stderr into ErrorRecord objects. A successful
            # CLI warning must not abort before its exit code/stdout are checked.
            # Keep stderr only in memory; reports contain fixed codes, never its
            # provider response text. The bundled-Python launcher avoids cmd.exe.
            $ErrorActionPreference = 'Continue'
            $combined = @(& $az @azArgumentPrefix rest --subscription $SubscriptionId --method get --url $url --output json --only-show-errors 2>&1)
            $exitCode = $LASTEXITCODE
        } catch {
            $launchFailed = $true
        } finally {
            $ErrorActionPreference = $previousPreference
        }
        $json = @($combined | Where-Object { $_ -isnot [System.Management.Automation.ErrorRecord] })
        $stderr = (@($combined | Where-Object { $_ -is [System.Management.Automation.ErrorRecord] } | ForEach-Object { [string] $_ }) -join [Environment]::NewLine)
        $succeeded = -not $launchFailed -and $exitCode -eq 0
        $kind = if ($succeeded) { 'native_stderr_warning' } else { Get-ReadFailureKind $stderr }
        $retry = -not $succeeded -and -not $launchFailed -and $kind.StartsWith('transient_') -and $attempt -lt 3
        if ($stderr -or -not $succeeded) {
            if ($report.arm_read_diagnostics.Count -ge 80) { Stop-Verification 'read_diagnostic_limit' }
            $report.arm_read_diagnostics += [pscustomobject]@{ step = $Label; attempt = $attempt; exit_code = $exitCode; code = $kind; retry = $retry }
        }
        if ($succeeded) { break }
        if (-not $retry) { Stop-Verification ('arm_read_failed:' + $Label) }
        # At most two short waits, only before a GET to the same validated URL.
        Start-Sleep -Seconds (2 * $attempt)
    }
    try { $document = ($json -join [Environment]::NewLine) | ConvertFrom-Json } catch {
        Stop-Verification ('invalid_arm_json:' + $Label)
    }
    if ($null -eq $document -or $document -is [array] -or $document -isnot [pscustomobject]) {
        Stop-Verification ('invalid_arm_document:' + $Label)
    }
    return $document
}

function Read-ArmCollection {
    param([string] $Path, [string] $Label)
    $items = New-Object System.Collections.Generic.List[object]
    $next = $Path
    for ($page = 0; $next; $page++) {
        if ($page -ge 20) { Stop-Verification ('pagination_limit:' + $Label) }
        $document = Read-Arm $next $Label
        if ($null -eq $document.PSObject.Properties['value'] -or $document.value -isnot [array]) {
            Stop-Verification ('invalid_arm_collection:' + $Label)
        }
        foreach ($item in $document.value) {
            if ($items.Count -ge 2000 -or $item -isnot [pscustomobject]) { Stop-Verification ('collection_limit_or_schema:' + $Label) }
            $items.Add($item)
        }
        $next = if ($null -ne $document.PSObject.Properties['nextLink']) { [string] $document.nextLink } else { '' }
    }
    return $items.ToArray()
}

function Add-Check {
    param([string] $Name, [bool] $Passed, $Observed)
    $checks.Add([pscustomobject]@{ name = $Name; passed = $Passed; observed = $Observed })
}

function Test-BooleanValue {
    param($Value, [bool] $Expected)
    # PowerShell otherwise compares strings such as "false" equal to $false.
    return ($Value -is [bool] -and $Value -eq $Expected)
}

function Test-IntegerValue {
    param($Value, [long] $Expected)
    return (($Value -is [int] -or $Value -is [long]) -and $Value -eq $Expected)
}

function Find-Resource {
    param([string] $Type, [string] $Label)
    $foundResources = @($inventory | Where-Object { $_.type -eq $Type })
    if ($foundResources.Count -ne 1) { Stop-Verification ('unexpected_resource_count:' + $Label) }
    $id = [string] $foundResources[0].id
    if (-not $id.StartsWith($groupPath + '/providers/', [StringComparison]::OrdinalIgnoreCase)) { Stop-Verification ('unexpected_resource_scope:' + $Label) }
    return $id
}

function Get-OptionalArray {
    param($Object, [string] $Property, [string] $Label)
    $field = $Object.PSObject.Properties[$Property]
    if ($null -eq $field -or $null -eq $field.Value) { return @() }
    if ($field.Value -isnot [array]) { Stop-Verification ('invalid_array:' + $Label) }
    return $field.Value
}

function Test-Peering {
    param($Peering, [string] $ExpectedName, [string] $ExpectedTarget)
    return ($Peering.name -eq $ExpectedName -and $Peering.properties.remoteVirtualNetwork.id -eq $ExpectedTarget -and
        $Peering.properties.provisioningState -eq 'Succeeded' -and $Peering.properties.peeringState -eq 'Connected' -and
        (Test-BooleanValue $Peering.properties.allowVirtualNetworkAccess $true) -and
        (Test-BooleanValue $Peering.properties.allowForwardedTraffic $false) -and
        (Test-BooleanValue $Peering.properties.allowGatewayTransit $false) -and
        (Test-BooleanValue $Peering.properties.useRemoteGateways $false))
}

try {
    $az = (Get-Command az -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
    $azArgumentPrefix = @()
    if ([IO.Path]::GetExtension($az) -in @('.cmd', '.bat')) {
        # The MSI az.cmd expands %* through cmd.exe, which splits ARM URLs at &.
        # Call the same bundled Python entry point directly so URLs stay one arg.
        $cliRoot = Split-Path -Parent (Split-Path -Parent $az)
        $bundledPython = Join-Path $cliRoot 'python.exe'
        if (-not (Test-Path -LiteralPath $bundledPython -PathType Leaf)) {
            Stop-Verification 'unsupported_azure_cli_batch_launcher'
        }
        $az = $bundledPython
        $azArgumentPrefix = @('-IBm', 'azure.cli')
    }
    $deployment = Read-Arm ($groupPath + '/providers/Microsoft.Resources/deployments/aicg-bootstrap?api-version=2025-04-01') 'bootstrap_deployment'
    Add-Check 'bootstrap_deployment_succeeded' ($deployment.properties.provisioningState -eq 'Succeeded') $deployment.properties.provisioningState
    if ($deployment.properties.provisioningState -ne 'Succeeded') { Stop-Verification 'bootstrap_not_succeeded' }
    $outputs = $deployment.properties.outputs
    $inventory = @(Read-ArmCollection ($groupPath + '/resources?api-version=2021-04-01') 'resource_inventory')
    $storageId = Find-Resource 'Microsoft.Storage/storageAccounts' 'storage'
    $registryId = Find-Resource 'Microsoft.ContainerRegistry/registries' 'registry'
    $environmentId = Find-Resource 'Microsoft.App/managedEnvironments' 'environment'
    $identityId = Find-Resource 'Microsoft.ManagedIdentity/userAssignedIdentities' 'identity'
    $vnetId = Find-Resource 'Microsoft.Network/virtualNetworks' 'vnet'
    $workspaceId = Find-Resource 'Microsoft.OperationalInsights/workspaces' 'workspace'
    $monitorScopeId = Find-Resource 'Microsoft.Insights/privateLinkScopes' 'monitor_scope'
    $outputMatch = ($storageId.Split('/')[-1] -eq $outputs.storageAccountName.value -and
        $registryId.Split('/')[-1] -eq $outputs.registryName.value -and
        $environmentId.Split('/')[-1] -eq $outputs.environmentName.value -and
        $identityId -eq $outputs.managedIdentityResourceId.value -and
        $vnetId -eq $outputs.vnetId.value -and $workspaceId -eq $outputs.logAnalyticsWorkspaceId.value)
    Add-Check 'bootstrap_outputs_match_inventory' $outputMatch @{ storage = $storageId; registry = $registryId; environment = $environmentId; identity = $identityId; vnet = $vnetId; workspace = $workspaceId }

    $storage = Read-Arm ($storageId + '?api-version=2025-01-01') 'storage'
    $observed = @{ publicNetworkAccess = $storage.properties.publicNetworkAccess; allowSharedKeyAccess = $storage.properties.allowSharedKeyAccess; minimumTlsVersion = $storage.properties.minimumTlsVersion; sku = $storage.sku.name; allowBlobPublicAccess = $storage.properties.allowBlobPublicAccess }
    Add-Check 'storage_private_tls_zrs' ($observed.publicNetworkAccess -eq 'Disabled' -and (Test-BooleanValue $observed.allowSharedKeyAccess $false) -and $observed.minimumTlsVersion -eq 'TLS1_2' -and $observed.sku -eq 'Standard_ZRS' -and (Test-BooleanValue $observed.allowBlobPublicAccess $false)) $observed

    $registry = Read-Arm ($registryId + '?api-version=2025-11-01') 'registry'
    $observed = @{ publicNetworkAccess = $registry.properties.publicNetworkAccess; adminUserEnabled = $registry.properties.adminUserEnabled; anonymousPullEnabled = $registry.properties.anonymousPullEnabled; sku = $registry.sku.name }
    Add-Check 'registry_private_no_local_auth' ($observed.publicNetworkAccess -eq 'Disabled' -and (Test-BooleanValue $observed.adminUserEnabled $false) -and (Test-BooleanValue $observed.anonymousPullEnabled $false) -and $observed.sku -eq 'Premium') $observed

    $environment = Read-Arm ($environmentId + '?api-version=2025-07-01') 'environment'
    $profiles = @($environment.properties.workloadProfiles)
    $observed = @{ internal = $environment.properties.vnetConfiguration.internal; publicNetworkAccess = $environment.properties.publicNetworkAccess; workloadProfiles = @($profiles | Select-Object name, workloadProfileType); subnet = $environment.properties.vnetConfiguration.infrastructureSubnetId }
    Add-Check 'environment_internal_consumption_profile' ((Test-BooleanValue $observed.internal $true) -and $observed.publicNetworkAccess -eq 'Disabled' -and $profiles.Count -eq 1 -and $profiles[0].name -eq 'Consumption' -and $profiles[0].workloadProfileType -eq 'Consumption' -and $observed.subnet -eq ($vnetId + '/subnets/snet-environment')) $observed

    $identity = Read-Arm ($identityId + '?api-version=2024-11-30') 'managed_identity'
    $principalId = [string] $identity.properties.principalId
    if ($principalId -notmatch '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$') { Stop-Verification 'invalid_managed_identity_principal' }
    # This filter includes direct assignments at, above and below the subscription;
    # no Graph lookup or group-membership inference is performed.
    $rolePath = $subscriptionPath + '/providers/Microsoft.Authorization/roleAssignments?api-version=2022-04-01&$filter=' + [uri]::EscapeDataString("principalId eq '$principalId'")
    $roles = @(Read-ArmCollection $rolePath 'managed_identity_roles')
    $expectedRoles = @{
        (($storageId + '/blobServices/default/containers/inputs|2a2b9908-6ea1-4ae2-8e65-a410df84e7d1').ToLowerInvariant()) = $true
        (($storageId + '/blobServices/default/containers/outputs|ba92f5b4-2d11-453d-a403-e96b0029c9fe').ToLowerInvariant()) = $true
        (($registryId + '|7f951dda-4ed3-4680-a7ca-43fe172d538d').ToLowerInvariant()) = $true
    }
    $roleRecords = @($roles | Select-Object -First 20 | ForEach-Object { @{ scope = $_.properties.scope; role_definition_id = $_.properties.roleDefinitionId; principal_id = $_.properties.principalId } })
    $actualRoleKeys = @($roles | ForEach-Object { ($_.properties.scope.TrimEnd('/') + '|' + $_.properties.roleDefinitionId.Split('/')[-1]).ToLowerInvariant() })
    $rolesMatch = ($roles.Count -eq 3 -and @($actualRoleKeys | Select-Object -Unique).Count -eq 3 -and
        @($actualRoleKeys | Where-Object { -not $expectedRoles.ContainsKey($_) }).Count -eq 0 -and
        @($roles | Where-Object { $_.properties.principalId -ne $principalId }).Count -eq 0 -and
        $identity.properties.clientId -eq $outputs.managedIdentityClientId.value)
    Add-Check 'managed_identity_three_exact_scoped_roles' $rolesMatch @{ count = $roles.Count; first_twenty = $roleRecords }

    $endpoints = @($inventory | Where-Object { $_.type -eq 'Microsoft.Network/privateEndpoints' })
    if ($endpoints.Count -ne 3) { Stop-Verification 'unexpected_private_endpoint_count' }
    $expectedTargets = @($storageId, $registryId, $monitorScopeId)
    $actualTargets = @()
    foreach ($endpointItem in $endpoints) {
        $endpoint = Read-Arm ($endpointItem.id + '?api-version=2024-07-01') 'private_endpoint'
        $connections = @($endpoint.properties.privateLinkServiceConnections)
        $targets = @($connections | ForEach-Object { $_.properties.privateLinkServiceId })
        $actualTargets += $targets
        $statuses = @($connections | ForEach-Object { $_.properties.privateLinkServiceConnectionState.status })
        Add-Check ('private_endpoint_approved:' + $endpointItem.name) ($endpoint.properties.provisioningState -eq 'Succeeded' -and $connections.Count -eq 1 -and $statuses[0] -eq 'Approved' -and $endpoint.properties.subnet.id -eq ($vnetId + '/subnets/snet-private-endpoints')) @{ provisioningState = $endpoint.properties.provisioningState; connectionStatuses = $statuses; targets = $targets }
    }
    Add-Check 'three_expected_private_endpoints' ($endpoints.Count -eq 3 -and $actualTargets.Count -eq 3 -and @($actualTargets | Select-Object -Unique).Count -eq 3 -and @($actualTargets | Where-Object { $_ -notin $expectedTargets }).Count -eq 0) $actualTargets

    $expectedZones = @('privatelink.azurecr.io', 'privatelink.blob.core.windows.net', 'privatelink.monitor.azure.com', 'privatelink.oms.opinsights.azure.com', 'privatelink.ods.opinsights.azure.com', 'privatelink.agentsvc.azure-automation.net')
    $zones = @($inventory | Where-Object { $_.type -eq 'Microsoft.Network/privateDnsZones' })
    Add-Check 'six_expected_private_dns_zones' ($zones.Count -eq 6 -and @($zones.name | Select-Object -Unique).Count -eq 6 -and @($zones | Where-Object { $_.name -notin $expectedZones }).Count -eq 0) @($zones.name)
    if ($zones.Count -ne 6) { Stop-Verification 'unexpected_private_dns_zone_count' }
    $operatorGroupPath = $subscriptionPath + '/resourceGroups/' + $OperatorResourceGroup
    $operatorVnetId = $operatorGroupPath + '/providers/Microsoft.Network/virtualNetworks/vnet-aicg-operator'
    $expectedLinkCount = if ($OperatorPresent) { 2 } else { 1 }
    $totalLinkCount = 0
    foreach ($zone in $zones) {
        $links = @(Read-ArmCollection ($zone.id + '/virtualNetworkLinks?api-version=2024-06-01') 'private_dns_links')
        $totalLinkCount += $links.Count
        $linkRecords = @($links | Select-Object -First 20 | ForEach-Object { @{ name = $_.name; vnet = $_.properties.virtualNetwork.id; provisioningState = $_.properties.provisioningState; registrationEnabled = $_.properties.registrationEnabled } })
        $foundationLinks = @($links | Where-Object { $_.properties.virtualNetwork.id -eq $vnetId })
        $operatorLinks = @($links | Where-Object { $_.properties.virtualNetwork.id -eq $operatorVnetId -and $_.name -eq 'link-aicg-operator' })
        $validStates = @($links | Where-Object { $_.properties.provisioningState -ne 'Succeeded' -or -not (Test-BooleanValue $_.properties.registrationEnabled $false) }).Count -eq 0
        $linksMatch = ($links.Count -eq $expectedLinkCount -and $foundationLinks.Count -eq 1 -and $validStates -and
            ((-not $OperatorPresent -and $operatorLinks.Count -eq 0) -or ($OperatorPresent -and $operatorLinks.Count -eq 1)))
        Add-Check ('private_dns_vnet_link:' + $zone.name) $linksMatch @{ count = $links.Count; first_twenty = $linkRecords }
    }
    Add-Check 'exact_private_dns_link_count' ($totalLinkCount -eq (6 * $expectedLinkCount)) @{ expected = 6 * $expectedLinkCount; actual = $totalLinkCount }

    $workspace = Read-Arm ($workspaceId + '?api-version=2025-02-01') 'monitor_workspace'
    $observed = @{ publicNetworkAccessForIngestion = $workspace.properties.publicNetworkAccessForIngestion; publicNetworkAccessForQuery = $workspace.properties.publicNetworkAccessForQuery; disableLocalAuth = $workspace.properties.features.disableLocalAuth }
    Add-Check 'monitor_workspace_private_no_local_auth' ($observed.publicNetworkAccessForIngestion -eq 'Disabled' -and $observed.publicNetworkAccessForQuery -eq 'Disabled' -and (Test-BooleanValue $observed.disableLocalAuth $true)) $observed
    $monitorScope = Read-Arm ($monitorScopeId + '?api-version=2021-07-01-preview') 'monitor_scope'
    $modes = $monitorScope.properties.accessModeSettings
    $exclusionProperty = $modes.PSObject.Properties['exclusions']
    $exclusionsSchemaValid = ($null -eq $exclusionProperty -or $null -eq $exclusionProperty.Value -or $exclusionProperty.Value -is [array])
    $exclusions = @()
    if ($null -ne $exclusionProperty -and $null -ne $exclusionProperty.Value) { $exclusions = @($exclusionProperty.Value) }
    Add-Check 'monitor_scope_private_only' ($modes.ingestionAccessMode -eq 'PrivateOnly' -and $modes.queryAccessMode -eq 'PrivateOnly' -and $exclusionsSchemaValid -and @($exclusions).Count -eq 0) @{ ingestionAccessMode = $modes.ingestionAccessMode; queryAccessMode = $modes.queryAccessMode; exclusions_schema_valid = $exclusionsSchemaValid; exclusions_count = @($exclusions).Count }
    $scopedResources = @(Read-ArmCollection ($monitorScopeId + '/scopedResources?api-version=2021-07-01-preview') 'monitor_scoped_resources')
    Add-Check 'monitor_scope_links_workspace' ($scopedResources.Count -eq 1 -and $scopedResources[0].properties.linkedResourceId -eq $workspaceId) @($scopedResources | ForEach-Object { $_.properties.linkedResourceId })
    $jobs = @(Read-ArmCollection ($groupPath + '/providers/Microsoft.App/jobs?api-version=2025-01-01') 'pilot_jobs')
    $expectedJobId = $groupPath + '/providers/Microsoft.App/jobs/' + $outputs.jobName.value
    $oneExpectedJob = $jobs.Count -eq 1 -and $jobs[0].id -eq $expectedJobId
    Add-Check 'one_expected_pilot_job' $oneExpectedJob @{ count = $jobs.Count; expected_id = $expectedJobId }
    if (-not $oneExpectedJob) { Stop-Verification 'unexpected_pilot_job_count_or_id' }
    $job = Read-Arm ($expectedJobId + '?api-version=2025-01-01') 'pilot_job'
    $jobIdentityNames = @($job.identity.userAssignedIdentities.PSObject.Properties.Name)
    Add-Check 'job_environment_and_identity' ($job.properties.provisioningState -eq 'Succeeded' -and $job.properties.environmentId -eq $environmentId -and
        $job.properties.workloadProfileName -eq 'Consumption' -and $job.identity.type -eq 'UserAssigned' -and $jobIdentityNames.Count -eq 1 -and $jobIdentityNames[0] -eq $identityId) @{
        provisioning_state = $job.properties.provisioningState; environment_id = $job.properties.environmentId; workload_profile = $job.properties.workloadProfileName;
        identity_type = $job.identity.type; identity_count = $jobIdentityNames.Count
    }
    $config = $job.properties.configuration
    Add-Check 'job_manual_bounded_execution' ($config.triggerType -eq 'Manual' -and (Test-IntegerValue $config.replicaTimeout 1800) -and (Test-IntegerValue $config.replicaRetryLimit 0) -and
        (Test-IntegerValue $config.manualTriggerConfig.parallelism 1) -and (Test-IntegerValue $config.manualTriggerConfig.replicaCompletionCount 1)) @{
        trigger = $config.triggerType; timeout = $config.replicaTimeout; retries = $config.replicaRetryLimit;
        parallelism = $config.manualTriggerConfig.parallelism; completion_count = $config.manualTriggerConfig.replicaCompletionCount
    }
    $registries = @($config.registries)
    $identitySettings = @($config.identitySettings)
    $secrets = @(Get-OptionalArray $config 'secrets' 'job_secrets')
    $noRegistryCredentials = $true
    foreach ($entry in $registries) {
        foreach ($fieldName in @('username', 'passwordSecretRef')) {
            $credentialField = $entry.PSObject.Properties[$fieldName]
            if ($null -ne $credentialField -and $credentialField.Value) { $noRegistryCredentials = $false }
        }
    }
    Add-Check 'job_registry_identity_without_secrets' ($registries.Count -eq 1 -and $registries[0].server -eq $outputs.registryLoginServer.value -and
        $registries[0].identity -eq $identityId -and $identitySettings.Count -eq 1 -and $identitySettings[0].identity -eq $identityId -and
        $identitySettings[0].lifecycle -eq 'Main' -and $secrets.Count -eq 0 -and $noRegistryCredentials) @{ registry_count = $registries.Count; identity_setting_count = $identitySettings.Count; secret_count = $secrets.Count; no_registry_credentials = $noRegistryCredentials }
    $containers = @($job.properties.template.containers)
    $initContainers = @(Get-OptionalArray $job.properties.template 'initContainers' 'job_init_containers')
    $volumes = @(Get-OptionalArray $job.properties.template 'volumes' 'job_volumes')
    $oneContainer = $containers.Count -eq 1 -and $containers[0].name -eq 'gateway' -and $initContainers.Count -eq 0 -and $volumes.Count -eq 0
    Add-Check 'job_one_gateway_container' $oneContainer @{ count = $containers.Count; init_count = $initContainers.Count; volume_count = $volumes.Count }
    if (-not $oneContainer) { Stop-Verification 'unexpected_pilot_containers' }
    $container = $containers[0]
    $expectedImage = $outputs.registryLoginServer.value + '/ai-command-gateway@' + $ExpectedImageDigest
    Add-Check 'job_reviewed_image_digest' ($container.image -ceq $expectedImage) @{ expected_digest = $ExpectedImageDigest; matches = $container.image -ceq $expectedImage }
    $arguments = @(Get-OptionalArray $container 'args' 'job_args')
    $commands = @($container.command)
    Add-Check 'job_command_and_resources' ($commands.Count -eq 3 -and ($commands -join '|') -ceq 'python|-m|ai_command_gateway.azure_job' -and $arguments.Count -eq 0 -and
        $container.resources.cpu -is [ValueType] -and $container.resources.cpu -eq 1 -and $container.resources.memory -ceq '2Gi') @{ command_matches = ($commands -join '|') -ceq 'python|-m|ai_command_gateway.azure_job'; argument_count = $arguments.Count; cpu = $container.resources.cpu; memory = $container.resources.memory }
    $expectedEnv = @{
        AZURE_CLIENT_ID = $identity.properties.clientId
        AZURE_STORAGE_ACCOUNT_URL = $outputs.storageAccountUrl.value
        AZURE_INPUT_CONTAINER = 'inputs'
        AZURE_OUTPUT_CONTAINER = 'outputs'
        AI_GATEWAY_JOB_MODE = $ExpectedJobMode
        AI_GATEWAY_WORKSPACE = '/tmp/ai-command-gateway'
    }
    $envItems = @($container.env)
    $envMatch = $envItems.Count -eq 6 -and @($envItems.name | Select-Object -Unique).Count -eq 6
    foreach ($item in $envItems) {
        if (-not $expectedEnv.ContainsKey([string] $item.name)) { $envMatch = $false; continue }
        $valueField = $item.PSObject.Properties['value']
        $secretField = $item.PSObject.Properties['secretRef']
        if ($null -eq $valueField -or [string] $valueField.Value -cne [string] $expectedEnv[$item.name] -or ($null -ne $secretField -and $secretField.Value)) { $envMatch = $false }
    }
    Add-Check 'job_six_exact_environment_values' $envMatch @{ count = $envItems.Count; expected_mode = $ExpectedJobMode; values_match = $envMatch }

    $foundationPeerings = @(Read-ArmCollection ($vnetId + '/virtualNetworkPeerings?api-version=2024-07-01') 'foundation_peerings')
    if ($OperatorPresent) {
        $operatorPeerings = @(Read-ArmCollection ($operatorVnetId + '/virtualNetworkPeerings?api-version=2024-07-01') 'operator_peerings')
        Add-Check 'operator_reciprocal_peerings' ($foundationPeerings.Count -eq 1 -and $operatorPeerings.Count -eq 1 -and
            (Test-Peering $foundationPeerings[0] 'to-aicg-operator' $operatorVnetId) -and (Test-Peering $operatorPeerings[0] 'to-aicg-foundation' $vnetId)) @{ foundation_count = $foundationPeerings.Count; operator_count = $operatorPeerings.Count }
        $operatorIdentityId = $operatorGroupPath + '/providers/Microsoft.ManagedIdentity/userAssignedIdentities/id-aicg-operator'
        $operatorIdentity = Read-Arm ($operatorIdentityId + '?api-version=2024-11-30') 'operator_identity'
        $operatorPrincipalId = [string] $operatorIdentity.properties.principalId
        if ($operatorPrincipalId -notmatch '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$' -or $operatorPrincipalId -eq $principalId) { Stop-Verification 'invalid_operator_identity_principal' }
        $operatorRolePath = $subscriptionPath + '/providers/Microsoft.Authorization/roleAssignments?api-version=2022-04-01&$filter=' + [uri]::EscapeDataString("principalId eq '$operatorPrincipalId'")
        $operatorRoles = @(Read-ArmCollection $operatorRolePath 'operator_identity_roles')
        $expectedOperatorRoles = @{
            (($storageId + '/blobServices/default/containers/inputs|ba92f5b4-2d11-453d-a403-e96b0029c9fe').ToLowerInvariant()) = $true
            (($storageId + '/blobServices/default/containers/outputs|2a2b9908-6ea1-4ae2-8e65-a410df84e7d1').ToLowerInvariant()) = $true
            (($registryId + '|8311e382-0749-4cb8-b61a-304f252e45ec').ToLowerInvariant()) = $true
            (($workspaceId + '|73c42c96-874c-492b-b04d-ab87d138a893').ToLowerInvariant()) = $true
        }
        $actualOperatorKeys = @($operatorRoles | ForEach-Object { ($_.properties.scope.TrimEnd('/') + '|' + $_.properties.roleDefinitionId.Split('/')[-1]).ToLowerInvariant() })
        $operatorRolesMatch = $operatorRoles.Count -eq 4 -and @($actualOperatorKeys | Select-Object -Unique).Count -eq 4 -and
            @($actualOperatorKeys | Where-Object { -not $expectedOperatorRoles.ContainsKey($_) }).Count -eq 0 -and
            @($operatorRoles | Where-Object { $_.properties.principalId -ne $operatorPrincipalId }).Count -eq 0
        Add-Check 'operator_four_exact_scoped_roles' $operatorRolesMatch @{ count = $operatorRoles.Count; scopes_and_roles_match = $operatorRolesMatch }
    } else {
        Add-Check 'foundation_has_no_operator_peering' ($foundationPeerings.Count -eq 0) @{ count = $foundationPeerings.Count }
        $groups = @(Read-ArmCollection ($subscriptionPath + '/resourcegroups?api-version=2024-03-01') 'subscription_groups')
        Add-Check 'temporary_operator_group_removed' (@($groups | Where-Object { $_.id -eq $operatorGroupPath }).Count -eq 0) @{ expected_absent = $operatorGroupPath }
    }
    $report.passed = @($checks | Where-Object { -not $_.passed }).Count -eq 0
    if (-not $report.passed) { $report.error_code = 'configuration_checks_failed' }
} catch {
    $report.error_code = if ($script:pilotFailureCode) { $script:pilotFailureCode } else { 'verification_read_or_response_failed' }
} finally {
    $report.checks = @($checks.ToArray())
    $report.arm_get_requests = $script:pilotReadCount
    $report.verifier_sha256 = (Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $json = $report | ConvertTo-Json -Depth 12
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText((Join-Path $runRoot 'summary.json'), $json, $utf8)
    [System.IO.File]::WriteAllText((Join-Path $outputRoot 'summary.json'), $json, $utf8)
}
$report | ConvertTo-Json -Depth 12
if (-not $report.passed) { throw ('Pilot verification failed: ' + $report.error_code) }
