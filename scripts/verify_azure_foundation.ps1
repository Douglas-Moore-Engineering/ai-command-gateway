#Requires -Version 5.1
<#
.SYNOPSIS
Read deployed foundation configuration from Azure Resource Manager and verify it.
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
    [string] $ResourceGroup
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$workspaceRoot = Split-Path -Parent $PSScriptRoot
$subscriptionPath = '/subscriptions/' + $SubscriptionId
$groupPath = $subscriptionPath + '/resourceGroups/' + $ResourceGroup
$outputRoot = Join-Path $workspaceRoot 'outputs/azure-foundation-verification'
$runId = [guid]::NewGuid().ToString()
$runRoot = Join-Path $outputRoot $runId
New-Item -ItemType Directory -Path $runRoot -Force | Out-Null
$checks = New-Object System.Collections.Generic.List[object]
$script:foundationFailureCode = $null
$script:foundationReadCount = 0
$report = [ordered]@{
    schema_version = '1.0.0'
    recorded_at_utc = [DateTime]::UtcNow.ToString('o')
    scope = 'Azure control-plane configuration only; no private DNS, connectivity, data-plane or job execution test'
    subscription_id = $SubscriptionId
    resource_group = $ResourceGroup
    bootstrap_deployment = 'aicg-bootstrap'
    run_id = $runId
    passed = $false
    error_code = $null
    checks = @()
    arm_get_requests = 0
    last_read_step = $null
    resource_changes_performed = $false
    secrets_requested = $false
    dns_resolution_tested = $false
    data_plane_tested = $false
    job_execution_tested = $false
}

function Stop-Verification {
    param([string] $Code)
    $script:foundationFailureCode = $Code
    throw 'Foundation verification stopped; see the bounded error code in the report.'
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
    $script:foundationReadCount++
    $report.last_read_step = $Label
    try {
        # CLI errors can contain service response bodies; discard them and expose
        # only a controlled step code. Never request listKeys/listCredentials.
        $json = & $az @azArgumentPrefix rest --subscription $SubscriptionId --method get --url $url --output json --only-show-errors 2>$null
        if ($LASTEXITCODE -ne 0) { Stop-Verification ('arm_read_failed:' + $Label) }
    } catch {
        Stop-Verification ('arm_read_failed:' + $Label)
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
        foreach ($item in $document.value) { $items.Add($item) }
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

function Find-Resource {
    param([string] $Type, [string] $Label)
    $foundResources = @($inventory | Where-Object { $_.type -eq $Type })
    if ($foundResources.Count -ne 1) { Stop-Verification ('unexpected_resource_count:' + $Label) }
    return [string] $foundResources[0].id
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
    $roleRecords = @($roles | ForEach-Object { @{ scope = $_.properties.scope; role_definition_id = $_.properties.roleDefinitionId; principal_id = $_.properties.principalId } })
    $actualRoleKeys = @($roles | ForEach-Object { ($_.properties.scope.TrimEnd('/') + '|' + $_.properties.roleDefinitionId.Split('/')[-1]).ToLowerInvariant() })
    $rolesMatch = ($roles.Count -eq 3 -and @($actualRoleKeys | Select-Object -Unique).Count -eq 3 -and
        @($actualRoleKeys | Where-Object { -not $expectedRoles.ContainsKey($_) }).Count -eq 0 -and
        @($roles | Where-Object { $_.properties.principalId -ne $principalId }).Count -eq 0 -and
        $identity.properties.clientId -eq $outputs.managedIdentityClientId.value)
    Add-Check 'managed_identity_three_exact_scoped_roles' $rolesMatch $roleRecords

    $endpoints = @($inventory | Where-Object { $_.type -eq 'Microsoft.Network/privateEndpoints' })
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
    Add-Check 'six_expected_private_dns_zones' ($zones.Count -eq 6 -and @($zones | Where-Object { $_.name -notin $expectedZones }).Count -eq 0) @($zones.name)
    foreach ($zone in $zones) {
        $links = @(Read-ArmCollection ($zone.id + '/virtualNetworkLinks?api-version=2024-06-01') 'private_dns_links')
        $linkRecords = @($links | ForEach-Object { @{ vnet = $_.properties.virtualNetwork.id; provisioningState = $_.properties.provisioningState; registrationEnabled = $_.properties.registrationEnabled } })
        Add-Check ('private_dns_vnet_link:' + $zone.name) ($links.Count -eq 1 -and $links[0].properties.virtualNetwork.id -eq $vnetId -and $links[0].properties.provisioningState -eq 'Succeeded' -and (Test-BooleanValue $links[0].properties.registrationEnabled $false)) $linkRecords
    }

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
    $jobs = @(Read-ArmCollection ($groupPath + '/providers/Microsoft.App/jobs?api-version=2025-01-01') 'foundation_jobs')
    Add-Check 'foundation_has_no_jobs' ($jobs.Count -eq 0) @{ count = $jobs.Count }
    $report.passed = @($checks | Where-Object { -not $_.passed }).Count -eq 0
    if (-not $report.passed) { $report.error_code = 'configuration_checks_failed' }
} catch {
    $report.error_code = if ($script:foundationFailureCode) { $script:foundationFailureCode } else { 'verification_read_or_response_failed' }
} finally {
    $report.checks = @($checks.ToArray())
    $report.arm_get_requests = $script:foundationReadCount
    $report.verifier_sha256 = (Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $json = $report | ConvertTo-Json -Depth 12
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText((Join-Path $runRoot 'summary.json'), $json, $utf8)
    [System.IO.File]::WriteAllText((Join-Path $outputRoot 'summary.json'), $json, $utf8)
}
$report | ConvertTo-Json -Depth 12
if (-not $report.passed) { throw ('Foundation verification failed: ' + $report.error_code) }
