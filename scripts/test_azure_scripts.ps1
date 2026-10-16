#Requires -Version 5.1
<#
.SYNOPSIS
Exercise deployment gates with a real Bicep compiler and a fake Azure CLI.
.DESCRIPTION
Copies only IaC and deployment helpers into an isolated workspace beneath outputs.
All Azure commands are intercepted by a local stub. No Azure login or resource
operation occurs. Results are simulated CLI-contract evidence, not Azure validation.
#>
[CmdletBinding()]
param([string] $BicepPath)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$workspaceRoot = Split-Path -Parent $PSScriptRoot
if (-not $BicepPath) { $BicepPath = Join-Path $workspaceRoot '.cache/azure-cli/bin/bicep.exe' }
$compilerPath = (Resolve-Path -LiteralPath $BicepPath).ProviderPath
$testRoot = Join-Path $workspaceRoot 'outputs/azure-script-verification'
$stagedRoot = Join-Path $testRoot 'workspace'
$stagedScripts = Join-Path $stagedRoot 'scripts'
$fakeBin = Join-Path $testRoot 'fake-bin'
$utf8 = New-Object System.Text.UTF8Encoding($false)
New-Item -ItemType Directory -Path $stagedScripts, $fakeBin -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $workspaceRoot 'infra') -Destination $stagedRoot -Recurse -Force
foreach ($name in @('azure_preflight.ps1', 'deploy_azure.ps1')) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot $name) -Destination (Join-Path $stagedScripts $name) -Force
}
$fakeAz = @'
@echo off
echo %*>>"%AICG_TEST_CALLS%"
if "%1 %2"=="account show" goto account
if "%1 %2"=="group show" goto group
if "%1 %2 %3"=="deployment group what-if" goto whatif
if "%1 %2 %3"=="deployment group create" goto create
exit /b 91
:account
echo {"id":"00000000-0000-0000-0000-000000000001","state":"Enabled"}
exit /b 0
:group
echo {"id":"/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/test-aicg"}
exit /b 0
:whatif
type "%AICG_TEST_WHATIF%"
exit /b %AICG_TEST_EXIT%
:create
echo {"properties":{"provisioningState":"Succeeded","outputs":{"jobName":{"value":"simulated-job"}}}}
exit /b 0
'@
[System.IO.File]::WriteAllText((Join-Path $fakeBin 'az.cmd'), $fakeAz, $utf8)
$callLog = Join-Path $testRoot 'fake-az-calls.log'
$fixturePath = Join-Path $testRoot 'what-if-fixture.json'
$oldPath = $env:PATH
$oldCalls = $env:AICG_TEST_CALLS
$oldFixture = $env:AICG_TEST_WHATIF
$oldExit = $env:AICG_TEST_EXIT
$checks = New-Object System.Collections.Generic.List[object]
$common = @{
    SubscriptionId = '00000000-0000-0000-0000-000000000001'
    ResourceGroup = 'test-aicg'
    Location = 'eastus'
    BicepPath = $compilerPath
}
$preflightScript = Join-Path $stagedScripts 'azure_preflight.ps1'
$deployScript = Join-Path $stagedScripts 'deploy_azure.ps1'

function Reset-Fixture {
    param([string[]] $ChangeTypes = @('Create'), [string] $Status = 'Succeeded', [int] $ExitCode = 0)
    [System.IO.File]::WriteAllText($callLog, '', $utf8)
    $changes = @($ChangeTypes | ForEach-Object { @{ changeType = $_; resourceId = '/simulated/resource' } })
    $fixture = @{ status = $Status; changes = $changes }
    [System.IO.File]::WriteAllText($fixturePath, ($fixture | ConvertTo-Json -Depth 8), $utf8)
    $env:AICG_TEST_EXIT = [string] $ExitCode
}
function Assert-Condition {
    param([bool] $Condition, [string] $Message)
    if (-not $Condition) { throw $Message }
}
function Assert-NoCreate {
    $calls = [System.IO.File]::ReadAllText($callLog)
    Assert-Condition (-not $calls.Contains('deployment group create')) 'Unexpected simulated resource creation.'
}
function Expect-Failure {
    param([scriptblock] $Operation)
    $failed = $false
    try { & $Operation | Out-Null } catch { $failed = $true }
    Assert-Condition $failed 'Expected the operation to fail closed.'
    Assert-NoCreate
}
function Run-Check {
    param([string] $Name, [scriptblock] $Operation)
    try {
        & $Operation
        $checks.Add([pscustomobject]@{ name = $Name; passed = $true })
    } catch {
        $checks.Add([pscustomobject]@{ name = $Name; passed = $false; error = $_.Exception.Message })
    }
}

try {
    $env:PATH = $fakeBin + [System.IO.Path]::PathSeparator + $oldPath
    $env:AICG_TEST_CALLS = $callLog
    $env:AICG_TEST_WHATIF = $fixturePath
    $selectedAz = Get-Command az -CommandType Application | Select-Object -First 1
    Assert-Condition ($selectedAz.Source -eq (Join-Path $fakeBin 'az.cmd')) 'Azure CLI stub was not selected; refusing to test.'

    Run-Check 'offline compilation does not invoke Azure' {
        Reset-Fixture
        $result = & $preflightScript @common
        Assert-Condition (-not $result.onlineChecksPassed -and -not $result.deployed) 'Unexpected offline result.'
        Assert-Condition ([System.IO.File]::ReadAllText($callLog).Length -eq 0) 'Offline path invoked Azure.'
        $parameters = (Get-Content -LiteralPath $result.parametersPath -Raw | ConvertFrom-Json).parameters
        Assert-Condition ($parameters.vnetAddressPrefix.value -eq '10.42.0.0/16') 'Default VNet prefix changed.'
        Assert-Condition ($parameters.environmentSubnetPrefix.value -eq '10.42.0.0/23') 'Default environment prefix changed.'
        Assert-Condition ($parameters.privateEndpointSubnetPrefix.value -eq '10.42.2.0/24') 'Default endpoint prefix changed.'
    }
    Run-Check 'custom network prefixes pass through deployment review into Bicep parameters' {
        Reset-Fixture
        $customPrefixes = @{
            VnetAddressPrefix = '172.20.0.0/16'
            EnvironmentSubnetPrefix = '172.20.4.0/23'
            PrivateEndpointSubnetPrefix = '172.20.8.0/24'
        }
        $result = & $deployScript @common @customPrefixes -Online
        $parameters = (Get-Content -LiteralPath $result.parametersPath -Raw | ConvertFrom-Json).parameters
        foreach ($name in $customPrefixes.Keys) {
            Assert-Condition ($parameters.$name.value -eq $customPrefixes[$name]) "Custom $name was not forwarded into the Bicep parameters."
            Assert-Condition ($result.$name -eq $customPrefixes[$name]) "Custom $name is missing from the review result."
        }
        Assert-NoCreate
    }
    Run-Check 'adjacent subnet ranges and minimum local size boundaries are accepted' {
        Reset-Fixture
        $result = & $preflightScript @common -VnetAddressPrefix '10.88.0.0/24' -EnvironmentSubnetPrefix '10.88.0.0/27' -PrivateEndpointSubnetPrefix '10.88.0.32/27'
        Assert-Condition (-not $result.onlineChecksPassed) 'Boundary check unexpectedly contacted Azure.'
        Assert-Condition ([System.IO.File]::ReadAllText($callLog).Length -eq 0) 'Local network boundary check invoked Azure.'
    }
    $invalidNetworks = @(
        @{ Name = 'abbreviated IPv4'; Parameters = @{ VnetAddressPrefix = '10.42/16' } }
        @{ Name = 'octet above 255'; Parameters = @{ VnetAddressPrefix = '10.256.0.0/16' } }
        @{ Name = 'leading-zero octet'; Parameters = @{ VnetAddressPrefix = '010.42.0.0/16' } }
        @{ Name = 'IPv6'; Parameters = @{ VnetAddressPrefix = 'fd00::/16' } }
        @{ Name = 'prefix above 32'; Parameters = @{ VnetAddressPrefix = '10.42.0.0/33' } }
        @{ Name = 'VNet /0'; Parameters = @{ VnetAddressPrefix = '0.0.0.0/0' } }
        @{ Name = 'VNet /1'; Parameters = @{ VnetAddressPrefix = '0.0.0.0/1' } }
        @{ Name = 'VNet smaller than /29'; Parameters = @{ VnetAddressPrefix = '10.42.0.0/30' } }
        @{ Name = 'leading-zero prefix'; Parameters = @{ VnetAddressPrefix = '10.42.0.0/016' } }
        @{ Name = 'trailing newline'; Parameters = @{ VnetAddressPrefix = "10.42.0.0/16`n" } }
        @{ Name = 'VNet host bits'; Parameters = @{ VnetAddressPrefix = '10.42.1.0/16' } }
        @{ Name = 'environment subnet host bits'; Parameters = @{ EnvironmentSubnetPrefix = '10.42.0.1/23' } }
        @{ Name = 'endpoint subnet host bits'; Parameters = @{ PrivateEndpointSubnetPrefix = '10.42.2.1/24' } }
        @{ Name = 'environment smaller than /27'; Parameters = @{ EnvironmentSubnetPrefix = '10.42.0.0/28' } }
        @{ Name = 'endpoint /28'; Parameters = @{ PrivateEndpointSubnetPrefix = '10.42.2.0/28' } }
        @{ Name = 'endpoint /29'; Parameters = @{ PrivateEndpointSubnetPrefix = '10.42.2.0/29' } }
        @{ Name = 'endpoint /30'; Parameters = @{ PrivateEndpointSubnetPrefix = '10.42.2.0/30' } }
        @{ Name = 'endpoint /31'; Parameters = @{ PrivateEndpointSubnetPrefix = '10.42.2.0/31' } }
        @{ Name = 'endpoint /32'; Parameters = @{ PrivateEndpointSubnetPrefix = '10.42.2.0/32' } }
        @{ Name = 'environment outside VNet'; Parameters = @{ EnvironmentSubnetPrefix = '10.43.0.0/23' } }
        @{ Name = 'endpoint outside VNet'; Parameters = @{ PrivateEndpointSubnetPrefix = '10.43.2.0/24' } }
        @{ Name = 'subnet contains VNet'; Parameters = @{ EnvironmentSubnetPrefix = '10.0.0.0/8' } }
        @{ Name = 'overlapping subnets'; Parameters = @{ PrivateEndpointSubnetPrefix = '10.42.1.0/24' } }
        @{ Name = 'identical subnets'; Parameters = @{ PrivateEndpointSubnetPrefix = '10.42.0.0/23' } }
    )
    foreach ($invalidNetwork in $invalidNetworks) {
        Run-Check ('invalid network blocks before Azure: ' + $invalidNetwork.Name) {
            Reset-Fixture
            $invalidParameters = $invalidNetwork.Parameters
            Expect-Failure { & $deployScript @common @invalidParameters -Online -Deploy }
            Assert-Condition ([System.IO.File]::ReadAllText($callLog).Length -eq 0) 'Invalid network input reached Azure.'
        }
    }
    Run-Check 'online review allows Create NoChange Ignore without deployment' {
        Reset-Fixture -ChangeTypes @('Create', 'NoChange', 'Ignore')
        $result = & $deployScript @common -Online
        Assert-Condition $result.onlineChecksPassed 'Online review did not complete.'
        Assert-NoCreate
        $calls = [System.IO.File]::ReadAllLines($callLog)
        Assert-Condition (@($calls | Where-Object { -not $_.Contains('--subscription 00000000-0000-0000-0000-000000000001') }).Count -eq 0) 'An Azure command omitted explicit subscription.'
    }
    Run-Check 'Deploy requires explicit Online' {
        Reset-Fixture
        Expect-Failure { & $deployScript @common -Deploy }
        Assert-Condition ([System.IO.File]::ReadAllText($callLog).Length -eq 0) 'Deploy without Online reached Azure.'
    }
    Run-Check 'Job requires an immutable lowercase digest' {
        Reset-Fixture
        Expect-Failure { & $deployScript @common -Stage Job -ImageDigest 'latest' -Online -Deploy }
        Assert-Condition ([System.IO.File]::ReadAllText($callLog).Length -eq 0) 'Invalid digest reached Azure.'
    }
    foreach ($kind in @('Delete', 'Unsupported', 'Deploy', 'Unexpected', 'Modify')) {
        Run-Check ('default blocks ' + $kind) {
            Reset-Fixture -ChangeTypes @($kind)
            Expect-Failure { & $deployScript @common -Online -Deploy }
        }
    }
    Run-Check 'AllowModify admits reviewed modifications only' {
        Reset-Fixture -ChangeTypes @('Modify')
        & $deployScript @common -Online -Deploy -AllowModify | Out-Null
        $calls = [System.IO.File]::ReadAllText($callLog)
        Assert-Condition ($calls.Contains('deployment group what-if') -and $calls.Contains('deployment group create')) 'Explicit apply did not follow what-if.'
    }
    Run-Check 'AllowModify does not admit deletion' {
        Reset-Fixture -ChangeTypes @('Delete')
        Expect-Failure { & $deployScript @common -Online -Deploy -AllowModify }
    }
    Run-Check 'failed what-if status prevents apply' {
        Reset-Fixture -Status 'Failed'
        Expect-Failure { & $deployScript @common -Online -Deploy }
    }
    Run-Check 'nonzero Azure CLI exit prevents apply' {
        Reset-Fixture -ExitCode 2
        Expect-Failure { & $deployScript @common -Online -Deploy }
    }
    Run-Check 'explicit create applies after successful what-if' {
        Reset-Fixture
        & $deployScript @common -Online -Deploy | Out-Null
        $calls = [System.IO.File]::ReadAllText($callLog)
        Assert-Condition ($calls.IndexOf('deployment group what-if') -lt $calls.IndexOf('deployment group create')) 'Apply did not follow what-if.'
        Assert-Condition ($calls.Contains('--mode Incremental')) 'Incremental deployment mode missing.'
    }
} finally {
    $env:PATH = $oldPath
    $env:AICG_TEST_CALLS = $oldCalls
    $env:AICG_TEST_WHATIF = $oldFixture
    $env:AICG_TEST_EXIT = $oldExit
}
$failedChecks = @($checks | Where-Object { -not $_.passed })
$summary = [ordered]@{
    scope = 'PowerShell contract tests with real local Bicep compilation and simulated Azure CLI; no live Azure calls'
    passed = ($failedChecks.Count -eq 0)
    checks = @($checks.ToArray())
}
$summaryPath = Join-Path $testRoot 'summary.json'
[System.IO.File]::WriteAllText($summaryPath, ($summary | ConvertTo-Json -Depth 8), $utf8)
$summary | ConvertTo-Json -Depth 8
if ($failedChecks.Count -gt 0) { exit 1 }
