#Requires -Version 5.1
<#
.SYNOPSIS
Review an Azure deployment, or apply it only with explicit -Online -Deploy.
.DESCRIPTION
Bootstrap provisions the private foundation with no job. Push a reviewed image
from a network-connected builder, then use Job with an immutable image digest.
This script never builds/pushes images, uploads datasets, or starts job execution.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string] $SubscriptionId,
    [Parameter(Mandatory = $true)] [string] $ResourceGroup,
    [Parameter(Mandatory = $true)] [string] $Location,
    [string] $WorkloadName = 'aicg',
    [ValidateSet('Bootstrap', 'Job')] [string] $Stage = 'Bootstrap',
    [string] $ImageDigest = '',
    [ValidateSet('demo', 'dataset-analysis')] [string] $JobMode = 'demo',
    [ValidateRange(7, 90)] [int] $ArtifactRetentionDays = 30,
    [ValidateRange(30, 90)] [int] $LogRetentionDays = 30,
    [string] $VnetAddressPrefix = '10.42.0.0/16',
    [string] $EnvironmentSubnetPrefix = '10.42.0.0/23',
    [string] $PrivateEndpointSubnetPrefix = '10.42.2.0/24',
    [string] $BicepPath,
    [switch] $Online,
    [switch] $AllowModify,
    [switch] $Deploy
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if ($Deploy -and -not $Online) {
    throw '-Deploy requires explicit -Online so current Azure what-if checks run before applying.'
}
$preflightArguments = @{
    SubscriptionId = $SubscriptionId
    ResourceGroup = $ResourceGroup
    Location = $Location
    WorkloadName = $WorkloadName
    Stage = $Stage
    ImageDigest = $ImageDigest
    JobMode = $JobMode
    ArtifactRetentionDays = $ArtifactRetentionDays
    LogRetentionDays = $LogRetentionDays
    VnetAddressPrefix = $VnetAddressPrefix
    EnvironmentSubnetPrefix = $EnvironmentSubnetPrefix
    PrivateEndpointSubnetPrefix = $PrivateEndpointSubnetPrefix
    Online = $Online
    AllowModify = $AllowModify
}
if ($BicepPath) { $preflightArguments.BicepPath = $BicepPath }
$preflight = & (Join-Path $PSScriptRoot 'azure_preflight.ps1') @preflightArguments
if (-not $Deploy) {
    Write-Host 'Review only. Add -Online -Deploy for an intentional resource deployment after reviewing what-if and cost.'
    $preflight
    return
}
if (-not $preflight.onlineChecksPassed) { throw 'Online preflight did not complete; deployment refused.' }
$azCommand = Get-Command az -CommandType Application -ErrorAction Stop | Select-Object -First 1
$arguments = @(
    'deployment', 'group', 'create', '--subscription', $SubscriptionId,
    '--resource-group', $ResourceGroup, '--name', ('aicg-' + $Stage.ToLowerInvariant()),
    '--template-file', $preflight.templatePath,
    '--parameters', ('@' + $preflight.parametersPath), '--mode', 'Incremental',
    '--output', 'json', '--only-show-errors'
)
$deploymentJson = & $azCommand.Source @arguments
if ($LASTEXITCODE -ne 0) { throw 'Azure deployment failed. Inspect its state before retrying; no rollback was attempted.' }
$deployment = $deploymentJson | ConvertFrom-Json
if ($deployment.properties.provisioningState -ne 'Succeeded') {
    throw 'Azure deployment did not report Succeeded. Inspect the deployment operations.'
}
$workspaceRoot = Split-Path -Parent $PSScriptRoot
$resultPath = Join-Path $workspaceRoot ('outputs/azure/' + $Stage.ToLowerInvariant() + '.deployment.json')
$utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($resultPath, ($deployment | ConvertTo-Json -Depth 100), $utf8)
Write-Host "Deployment result saved to $resultPath. No image push, dataset upload or job start was performed."
$deployment.properties.outputs
