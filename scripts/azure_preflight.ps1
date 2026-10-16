#Requires -Version 5.1
<#
.SYNOPSIS
Compile the Azure template locally; optionally request a read-only ARM what-if.
.DESCRIPTION
No login, subscription selection, resource creation, image push or dataset upload
is performed. Online checks require explicit identifiers and an existing login.
Use a preinstalled Bicep executable; this script never installs one implicitly.
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
    [ValidatePattern('^[a-z0-9]+$')]
    [string] $Location,
    [ValidatePattern('^[a-z][a-z0-9]{2,11}$')]
    [string] $WorkloadName = 'aicg',
    [ValidateSet('Bootstrap', 'Job')]
    [string] $Stage = 'Bootstrap',
    [string] $ImageDigest = '',
    [ValidateSet('demo', 'dataset-analysis')]
    [string] $JobMode = 'demo',
    [ValidateRange(7, 90)] [int] $ArtifactRetentionDays = 30,
    [ValidateRange(30, 90)] [int] $LogRetentionDays = 30,
    [string] $VnetAddressPrefix = '10.42.0.0/16',
    [string] $EnvironmentSubnetPrefix = '10.42.0.0/23',
    [string] $PrivateEndpointSubnetPrefix = '10.42.2.0/24',
    [string] $BicepPath,
    [switch] $Online,
    [switch] $AllowModify
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$workspaceRoot = Split-Path -Parent $PSScriptRoot
$templatePath = Join-Path $workspaceRoot 'infra/main.bicep'
$outputRoot = Join-Path $workspaceRoot 'outputs/azure'
$stageName = $Stage.ToLowerInvariant()
$compiledPath = Join-Path $outputRoot 'main.json'
$parametersPath = Join-Path $outputRoot ($stageName + '.parameters.json')
$whatIfPath = Join-Path $outputRoot ($stageName + '.what-if.json')

function ConvertTo-Ipv4Network {
    param([string] $Value, [string] $ParameterName)

    # Parse dotted decimal ourselves: IPAddress.Parse also accepts noncanonical
    # short, hexadecimal and octal forms. UInt64 arithmetic avoids signed shifts.
    $octet = '(?:0|[1-9][0-9]{0,2})'
    if ($Value -cnotmatch ('\A(' + $octet + '\.' + $octet + '\.' + $octet + '\.' + $octet + ')/(0|[1-9][0-9]?)\z')) {
        throw "$ParameterName must be a canonical IPv4 network CIDR, for example 10.42.0.0/16."
    }
    $addressText = $Matches[1]
    $prefixLength = [int] $Matches[2]
    if ($prefixLength -gt 32) { throw "$ParameterName has an IPv4 prefix outside 0-32." }
    [uint64] $addressNumber = 0
    foreach ($component in $addressText.Split('.')) {
        $number = [int] $component
        if ($number -gt 255) { throw "$ParameterName contains an IPv4 octet outside 0-255." }
        $addressNumber = $addressNumber * 256 + $number
    }
    [uint64] $blockSize = [math]::Pow(2, (32 - $prefixLength))
    if (($addressNumber % $blockSize) -ne 0) {
        throw "$ParameterName must use the network address with all host bits zero."
    }
    [pscustomobject]@{
        PrefixLength = $prefixLength
        FirstAddress = $addressNumber
        LastAddress = $addressNumber + $blockSize - 1
    }
}

# These are local structural checks. Target inventory, provider-reserved ranges,
# peered-network conflicts and service capacity still require Azure review.
$vnetNetwork = ConvertTo-Ipv4Network $VnetAddressPrefix 'VnetAddressPrefix'
$environmentNetwork = ConvertTo-Ipv4Network $EnvironmentSubnetPrefix 'EnvironmentSubnetPrefix'
$endpointNetwork = ConvertTo-Ipv4Network $PrivateEndpointSubnetPrefix 'PrivateEndpointSubnetPrefix'
if ($vnetNetwork.PrefixLength -lt 2 -or $vnetNetwork.PrefixLength -gt 29) {
    throw 'VnetAddressPrefix must use an Azure IPv4 VNet prefix between /2 and /29.'
}
# Workload-profile environments allow /27 or larger (the template uses one):
# https://learn.microsoft.com/azure/container-apps/custom-virtual-networks
if ($environmentNetwork.PrefixLength -gt 27) {
    throw 'EnvironmentSubnetPrefix must be /27 or larger for the Container Apps workload-profile environment.'
}
# This subnet includes Azure Monitor Private Link, which needs /27 or larger:
# https://learn.microsoft.com/azure/azure-monitor/fundamentals/private-link-configure
if ($endpointNetwork.PrefixLength -gt 27) {
    throw 'PrivateEndpointSubnetPrefix must be /27 or larger for Azure Monitor Private Link.'
}
foreach ($subnet in @($environmentNetwork, $endpointNetwork)) {
    if ($subnet.FirstAddress -lt $vnetNetwork.FirstAddress -or $subnet.LastAddress -gt $vnetNetwork.LastAddress) {
        throw 'Both subnet prefixes must be fully contained within VnetAddressPrefix.'
    }
}
if ($environmentNetwork.FirstAddress -le $endpointNetwork.LastAddress -and $endpointNetwork.FirstAddress -le $environmentNetwork.LastAddress) {
    throw 'EnvironmentSubnetPrefix and PrivateEndpointSubnetPrefix must not overlap.'
}

if ($Stage -eq 'Job' -and $ImageDigest -cnotmatch '^sha256:[0-9a-f]{64}$') {
    throw 'Job stage requires -ImageDigest sha256:<64 lowercase hexadecimal characters>.'
}
if ($Stage -eq 'Bootstrap' -and $ImageDigest) {
    throw 'Bootstrap stage does not consume an image digest. Use -Stage Job after pushing the image.'
}
if ($Stage -eq 'Bootstrap' -and $JobMode -ne 'demo') {
    throw 'Select dataset-analysis only for the Job stage after reviewing dataset upload scope.'
}
if (-not (Test-Path -LiteralPath $templatePath -PathType Leaf)) {
    throw 'The repository Azure template is missing.'
}
if ($BicepPath) {
    $compiler = (Resolve-Path -LiteralPath $BicepPath).ProviderPath
    if (-not (Test-Path -LiteralPath $compiler -PathType Leaf)) {
        throw 'BicepPath must identify an installed executable.'
    }
} else {
    $workspaceCompiler = Join-Path $workspaceRoot '.cache/azure-cli/bin/bicep.exe'
    if (Test-Path -LiteralPath $workspaceCompiler -PathType Leaf) {
        $compiler = $workspaceCompiler
    } else {
        $compilerCommand = Get-Command bicep -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if (-not $compilerCommand) {
            throw 'Install Bicep separately or provide -BicepPath. No tools were downloaded.'
        }
        $compiler = $compilerCommand.Source
    }
}
New-Item -ItemType Directory -Path $outputRoot -Force | Out-Null
$compileOutput = & $compiler build $templatePath --outfile $compiledPath
if ($LASTEXITCODE -ne 0) { throw "Bicep compilation failed with exit code $LASTEXITCODE." }
if ($compileOutput) { Write-Host ($compileOutput -join [Environment]::NewLine) }

$parameterValues = [ordered]@{
    location = @{ value = $Location }
    workloadName = @{ value = $WorkloadName }
    provisionJob = @{ value = ($Stage -eq 'Job') }
    imageDigest = @{ value = $ImageDigest }
    jobMode = @{ value = $JobMode }
    artifactRetentionDays = @{ value = $ArtifactRetentionDays }
    logRetentionDays = @{ value = $LogRetentionDays }
    vnetAddressPrefix = @{ value = $VnetAddressPrefix }
    environmentSubnetPrefix = @{ value = $EnvironmentSubnetPrefix }
    privateEndpointSubnetPrefix = @{ value = $PrivateEndpointSubnetPrefix }
}
$parameterDocument = [ordered]@{
    '$schema' = 'https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#'
    contentVersion = '1.0.0.0'
    parameters = $parameterValues
}
$utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($parametersPath, ($parameterDocument | ConvertTo-Json -Depth 8), $utf8)

if ($Online) {
    $azCommand = Get-Command az -CommandType Application -ErrorAction Stop | Select-Object -First 1
    $accountJson = & $azCommand.Source account show --subscription $SubscriptionId --output json --only-show-errors
    if ($LASTEXITCODE -ne 0) { throw 'Cannot read the explicitly selected subscription; sign in separately.' }
    $account = $accountJson | ConvertFrom-Json
    if ($account.id -ne $SubscriptionId -or $account.state -ne 'Enabled') {
        throw 'The selected subscription is unavailable or disabled.'
    }
    $groupJson = & $azCommand.Source group show --subscription $SubscriptionId --name $ResourceGroup --output json --only-show-errors
    if ($LASTEXITCODE -ne 0) { throw 'The target resource group must already exist; this script does not create it.' }
    $group = $groupJson | ConvertFrom-Json
    if (-not $group.id.StartsWith('/subscriptions/' + $SubscriptionId + '/resourceGroups/', [System.StringComparison]::OrdinalIgnoreCase)) {
        throw 'Resource-group identity does not match the explicit subscription.'
    }
    $whatIfArguments = @(
        'deployment', 'group', 'what-if', '--subscription', $SubscriptionId,
        '--resource-group', $ResourceGroup, '--name', ('aicg-' + $stageName),
        '--template-file', $compiledPath, '--parameters', ('@' + $parametersPath),
        '--mode', 'Incremental', '--validation-level', 'Provider',
        '--no-pretty-print', '--output', 'json', '--only-show-errors'
    )
    $whatIfJson = & $azCommand.Source @whatIfArguments
    if ($LASTEXITCODE -ne 0) { throw 'Azure what-if failed; no deployment was attempted.' }
    $whatIf = $whatIfJson | ConvertFrom-Json
    [System.IO.File]::WriteAllText($whatIfPath, ($whatIf | ConvertTo-Json -Depth 100), $utf8)
    if ($whatIf.status -ne 'Succeeded') { throw 'Azure what-if did not return Succeeded; inspect the saved result.' }
    foreach ($change in @($whatIf.changes)) {
        if ($change.changeType -notin @('Create', 'NoChange', 'Ignore', 'Modify')) {
            throw 'What-if includes deletion, an unsupported result or an unknown change type. Deployment is blocked.'
        }
        if ($change.changeType -eq 'Modify' -and -not $AllowModify) {
            throw 'What-if includes existing-resource modifications. Review the saved result, then explicitly use -AllowModify if intended.'
        }
    }
    Write-Host "Read-only Azure what-if saved to $whatIfPath. No resources were changed."
}

[pscustomobject]@{
    stage = $Stage
    subscriptionId = $SubscriptionId
    resourceGroup = $ResourceGroup
    location = $Location
    vnetAddressPrefix = $VnetAddressPrefix
    environmentSubnetPrefix = $EnvironmentSubnetPrefix
    privateEndpointSubnetPrefix = $PrivateEndpointSubnetPrefix
    templatePath = $compiledPath
    parametersPath = $parametersPath
    onlineChecksPassed = [bool] $Online
    modificationsExplicitlyAllowed = [bool] $AllowModify
    whatIfPath = $(if ($Online) { $whatIfPath } else { $null })
    deployed = $false
}
