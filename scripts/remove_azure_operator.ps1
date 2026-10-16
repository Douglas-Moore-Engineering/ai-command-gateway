[CmdletBinding()]
param(
    [switch]$Delete,
    [string]$OutputDirectory = 'outputs/azure-operator-cleanup'
)

# Project-specific by design: this must never become an arbitrary RG-delete helper.
$ErrorActionPreference = 'Stop'
$subscriptionId = 'b31e9bd1-6179-4504-819b-f212ed36f609'
$operatorGroup = 'rg-ai-command-gateway-operator'
$foundationGroup = 'rg-ai-command-gateway-dev'
$operatorPrefix = "/subscriptions/$subscriptionId/resourceGroups/$operatorGroup"
$foundationPrefix = "/subscriptions/$subscriptionId/resourceGroups/$foundationGroup"
$operatorVnetId = "$operatorPrefix/providers/Microsoft.Network/virtualNetworks/vnet-aicg-operator"
$identityId = "$operatorPrefix/providers/Microsoft.ManagedIdentity/userAssignedIdentities/id-aicg-operator"
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$reportPath = Join-Path $OutputDirectory 'summary.json'
$report = [ordered]@{
    schemaVersion = '1.0'
    startedAtUtc = [DateTime]::UtcNow.ToString('o')
    subscriptionId = $subscriptionId
    operatorResourceGroup = $operatorGroup
    deleteRequested = [bool]$Delete
    status = 'checking'
    checkedFoundationIds = @()
    deletedFoundationIds = @()
    operatorGroupDeleted = $false
}

function Save-Report {
    $report | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $reportPath -Encoding UTF8
}
function Invoke-AzJson {
    param([string[]]$Arguments)
    $output = & az @Arguments --subscription $subscriptionId --output json --only-show-errors 2>&1
    if ($LASTEXITCODE -ne 0) { throw "Azure read failed: $($Arguments -join ' '): $($output -join [Environment]::NewLine)" }
    try { return ($output -join [Environment]::NewLine | ConvertFrom-Json) }
    catch { throw "Azure returned invalid JSON for $($Arguments -join ' ')" }
}
function Read-Resource {
    param([string]$Id, [string]$ApiVersion)
    Invoke-AzJson -Arguments @('rest', '--method', 'get', '--url', "https://management.azure.com${Id}?api-version=$ApiVersion")
}
function Read-CheckedOperatorInventory {
    $resources = @(Invoke-AzJson -Arguments @('resource', 'list', '--resource-group', $operatorGroup))
    # A successful, empty/incomplete list is not permission to delete a group.
    # The identity was just read successfully and must also appear here.
    if ($resources.Count -eq 0 -or @($resources | Where-Object { $_.id -ieq $identityId }).Count -ne 1) {
        throw 'Temporary group inventory is empty or inconsistent with its existing identity; refusing deletion.'
    }
    foreach ($resource in $resources) {
        if ($allowedGroupResources -inotcontains $resource.id) {
            throw "Unexpected resource in temporary group; refusing group deletion: $($resource.id)"
        }
    }
    return $resources
}

try {
    $group = Invoke-AzJson -Arguments @('group', 'show', '--name', $operatorGroup)
    if ($group.id -ine $operatorPrefix -or $group.tags.purpose -ne 'temporary-private-operator' -or $group.tags.workload -ne 'ai-command-gateway') {
        throw 'Operator group identity/tags do not match the narrowly approved cleanup target.'
    }
    $identity = Read-Resource -Id $identityId -ApiVersion '2024-11-30'
    if (-not $identity.properties.principalId) { throw 'Temporary identity principal is missing.' }
    $principalId = $identity.properties.principalId
    $allowedGroupResources = @(
        "$operatorPrefix/providers/Microsoft.Compute/virtualMachines/vm-aicg-operator",
        "$operatorPrefix/providers/Microsoft.Compute/disks/osdisk-aicg-operator",
        $identityId,
        "$operatorPrefix/providers/Microsoft.Network/bastionHosts/bas-aicg-operator",
        "$operatorPrefix/providers/Microsoft.Network/networkInterfaces/nic-aicg-operator",
        "$operatorPrefix/providers/Microsoft.Network/networkSecurityGroups/nsg-aicg-operator",
        "$operatorPrefix/providers/Microsoft.Network/networkSecurityGroups/nsg-aicg-operator-bastion",
        "$operatorPrefix/providers/Microsoft.Network/publicIPAddresses/pip-aicg-operator-bastion",
        $operatorVnetId
    )
    $inventory = @(Read-CheckedOperatorInventory)
    $targets = @()
    $peeringId = "$foundationPrefix/providers/Microsoft.Network/virtualNetworks/vnet-aicg-sn5edmznrgh7s/virtualNetworkPeerings/to-aicg-operator"
    $peering = Read-Resource -Id $peeringId -ApiVersion '2024-07-01'
    if ($peering.properties.remoteVirtualNetwork.id -ine $operatorVnetId) { throw 'Foundation peering points to a different VNet.' }
    $targets += @{ id = $peeringId; apiVersion = '2024-07-01' }
    foreach ($zone in @('privatelink.azurecr.io', 'privatelink.blob.core.windows.net', 'privatelink.monitor.azure.com', 'privatelink.oms.opinsights.azure.com', 'privatelink.ods.opinsights.azure.com', 'privatelink.agentsvc.azure-automation.net')) {
        $linkId = "$foundationPrefix/providers/Microsoft.Network/privateDnsZones/$zone/virtualNetworkLinks/link-aicg-operator"
        $link = Read-Resource -Id $linkId -ApiVersion '2024-06-01'
        if ($link.properties.virtualNetwork.id -ine $operatorVnetId) { throw "DNS link points to a different VNet: $linkId" }
        $targets += @{ id = $linkId; apiVersion = '2024-06-01' }
    }
    $roles = @(
        @{ scope = 'Microsoft.ContainerRegistry/registries/craicgsn5edmznrgh7s'; assignment = 'df710df2-53f7-5387-a766-6d2dbcd9def4'; role = '8311e382-0749-4cb8-b61a-304f252e45ec' },
        @{ scope = 'Microsoft.Storage/storageAccounts/staicgsn5edmznrgh7s/blobServices/default/containers/inputs'; assignment = 'bb1f2a9c-9f8a-5e64-a3fd-04973464d836'; role = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe' },
        @{ scope = 'Microsoft.Storage/storageAccounts/staicgsn5edmznrgh7s/blobServices/default/containers/outputs'; assignment = '4d9bc1de-c9aa-5c68-80bf-266e84251f87'; role = '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1' },
        @{ scope = 'Microsoft.OperationalInsights/workspaces/log-aicg-sn5edmznrgh7s'; assignment = 'bf72e770-d088-516b-bdc2-f4395324ecef'; role = '73c42c96-874c-492b-b04d-ab87d138a893' }
    )
    foreach ($role in $roles) {
        $scope = "$foundationPrefix/providers/$($role.scope)"
        $roleId = "$scope/providers/Microsoft.Authorization/roleAssignments/$($role.assignment)"
        $assignment = Read-Resource -Id $roleId -ApiVersion '2022-04-01'
        if ($assignment.properties.principalId -ine $principalId -or $assignment.properties.scope -ine $scope -or
            $assignment.properties.roleDefinitionId -ine "/subscriptions/$subscriptionId/providers/Microsoft.Authorization/roleDefinitions/$($role.role)") {
            throw "Role identity/scope/definition differs from the approved temporary assignment: $roleId"
        }
        $targets += @{ id = $roleId; apiVersion = '2022-04-01' }
    }
    if ($targets.Count -ne 11) { throw 'Cleanup must contain exactly the eleven approved foundation children.' }
    $report.checkedFoundationIds = @($targets | ForEach-Object { $_.id })
    $report.checkedOperatorResourceIds = @($inventory | ForEach-Object { $_.id })
    $report.status = 'reviewed'
    Save-Report
    if (-not $Delete) {
        Write-Output "Read-only cleanup review passed: 11 foundation children and only approved resources in $operatorGroup. No deletion requested."
        exit 0
    }
    foreach ($target in $targets) {
        & az resource delete --subscription $subscriptionId --ids $target.id --api-version $target.apiVersion --only-show-errors
        if ($LASTEXITCODE -ne 0) { throw "Deletion failed for $($target.id). Earlier deletions are recorded; group remains." }
        $report.deletedFoundationIds += $target.id
        Save-Report
    }
    # Do not delete a group based only on an inventory captured before eleven
    # child deletions. Refuse resources added by another writer during cleanup.
    $finalInventory = @(Read-CheckedOperatorInventory)
    $report.finalOperatorResourceIds = @($finalInventory | ForEach-Object { $_.id })
    Save-Report
    # Exact literal target; the foundation resource group is never deleted.
    & az group delete --subscription $subscriptionId --name rg-ai-command-gateway-operator --yes --only-show-errors
    if ($LASTEXITCODE -ne 0) { throw 'Temporary group deletion failed; some billable resources may remain.' }
    $exists = & az group exists --subscription $subscriptionId --name rg-ai-command-gateway-operator --output tsv --only-show-errors
    if ($LASTEXITCODE -ne 0 -or $exists.Trim() -ne 'false') { throw 'Temporary group absence was not confirmed.' }
    $report.operatorGroupDeleted = $true
    $report.status = 'deleted'
    $report.completedAtUtc = [DateTime]::UtcNow.ToString('o')
    Save-Report
    Write-Output 'Removed exactly the 11 temporary foundation children and the disposable operator group. Foundation services, data, image and job retained.'
} catch {
    $report.status = 'failed'
    $report.error = $_.Exception.Message
    Save-Report
    throw
}
