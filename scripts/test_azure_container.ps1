#Requires -Version 5.1
<#
.SYNOPSIS
Verify the five supplied datasets in an existing local Linux image at 1 CPU/2 GiB.
.DESCRIPTION
Uses a fixed local image ID, five read-only input mounts, no container network,
and a read-only root filesystem. Builds/pulls no image and calls no Azure service.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string] $InputDir,
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._:/@-]*$')]
    [string] $Image = 'ai-command-gateway:0.4.0-reviewed'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$workspaceRoot = Split-Path -Parent $PSScriptRoot
$inputRoot = (Resolve-Path -LiteralPath $InputDir).ProviderPath
if (-not (Test-Path -LiteralPath $inputRoot -PathType Container)) { throw 'InputDir must be a directory.' }
$inputNames = @(
    'doi-10.34810-data2936.zip', 'logs_dataset.parquet', 'n76t439f65-1.zip',
    'packets_dataset.parquet', 'process_dataset.parquet'
)
$scriptNames = @('verify_azure_container.py', 'verify_azure_local.py')
$inputPaths = @($inputNames | ForEach-Object { Join-Path $inputRoot $_ })
$scriptPaths = @($scriptNames | ForEach-Object { Join-Path $PSScriptRoot $_ })
foreach ($path in @($inputPaths) + @($scriptPaths)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Required file is missing: $path" }
}
foreach ($path in @($inputRoot, $workspaceRoot, $PSScriptRoot)) {
    if ($path -match '[,"\r\n]') { throw 'Mount paths cannot contain commas, quotes or newlines.' }
}
$docker = (Get-Command docker -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
$dockerConfig = Join-Path $workspaceRoot '.cache/docker'
New-Item -ItemType Directory -Path $dockerConfig -Force | Out-Null
$inspectArguments = @('--config', $dockerConfig, 'image', 'inspect', $Image)
$inspectJson = & $docker @inspectArguments
if ($LASTEXITCODE -ne 0) { throw 'The requested local image could not be inspected. No image was pulled.' }
$images = @($inspectJson | ConvertFrom-Json)
if ($images.Count -ne 1) { throw 'Expected exactly one inspected local image.' }
$imageInfo = $images[0]
$imageId = [string] $imageInfo.Id
if ($imageId -cnotmatch '^sha256:[0-9a-f]{64}$' -or $imageInfo.Os -ne 'linux' -or $imageInfo.Architecture -ne 'amd64') {
    throw 'Verification requires a local linux/amd64 image with an immutable SHA-256 image ID.'
}

$outputRoot = Join-Path $workspaceRoot 'outputs/azure-container-resources-reviewed'
$runId = [guid]::NewGuid().ToString()
$runRoot = Join-Path $outputRoot $runId
New-Item -ItemType Directory -Path $runRoot | Out-Null
$utf8 = New-Object System.Text.UTF8Encoding($false)
$inspectPath = Join-Path $runRoot 'image-inspect.json'
[System.IO.File]::WriteAllText($inspectPath, ($inspectJson -join [Environment]::NewLine), $utf8)
$containerLog = Join-Path $runRoot 'container-output.log'
$resourcePath = Join-Path $runRoot 'resource-summary.json'
$datasetPath = Join-Path $runRoot 'dataset-analysis/summary.json'
$runArguments = @(
    '--config', $dockerConfig, 'run', '--rm', '--pull', 'never', '--network', 'none',
    '--read-only', '--memory', '2g', '--memory-swap', '2g', '--cpus', '1',
    '--tmpfs', '/tmp:rw,nosuid,nodev,size=128m', '--entrypoint', 'python',
    '--mount', "type=bind,source=$runRoot,target=/app/outputs"
)
for ($index = 0; $index -lt $inputNames.Count; $index++) {
    $runArguments += @('--mount', "type=bind,source=$($inputPaths[$index]),target=/inputs/$($inputNames[$index]),readonly")
}
for ($index = 0; $index -lt $scriptNames.Count; $index++) {
    $runArguments += @('--mount', "type=bind,source=$($scriptPaths[$index]),target=/app/scripts/$($scriptNames[$index]),readonly")
}
$runArguments += @($imageId, '/app/scripts/verify_azure_container.py')
$report = [ordered]@{
    schema_version = '1.0.0'
    scope = 'Existing local Linux image, resource-bounded filesystem Blob simulation; no Azure service validation'
    recorded_at_utc = [DateTime]::UtcNow.ToString('o')
    run_id = $runId
    requested_image = $Image
    image_id = $imageId
    image_os = $imageInfo.Os
    image_architecture = $imageInfo.Architecture
    command = @{ executable = $docker; arguments = $runArguments }
    run_directory = $runRoot
    input_files = $inputPaths
    image_build_performed = $false
    image_pull_performed = $false
    azure_service_validation_performed = $false
    docker_exit_code = $null
    passed = $false
    dataset_check_count = 0
    uid = $null
    error = $null
    evidence = @()
}
try {
    Write-Host "Verifying local image $imageId; evidence directory: $runRoot"
    & $docker @runArguments *> $containerLog
    $report.docker_exit_code = $LASTEXITCODE
    if ($LASTEXITCODE -ne 0) { throw "Container exited with code $LASTEXITCODE. Inspect container-output.log." }
    $resource = Get-Content -LiteralPath $resourcePath -Raw | ConvertFrom-Json
    $dataset = Get-Content -LiteralPath $datasetPath -Raw | ConvertFrom-Json
    $checks = @($dataset.checks)
    $report.dataset_check_count = $checks.Count
    $report.uid = $resource.uid
    if ($resource.uid -ne 10001 -or $resource.exit_code -ne 0 -or $resource.all_checks_passed -ne $true) {
        throw 'Resource verification did not confirm UID 10001 and successful completion.'
    }
    if ($resource.network -ne 'none' -or $resource.root_filesystem -ne 'read-only' -or
        $resource.cgroup_limits.'memory.max' -ne '2147483648' -or
        $resource.cgroup_limits.'memory.swap.max' -ne '0' -or
        $resource.cgroup_limits.'cpu.max' -ne '100000 100000') {
        throw 'The resource report does not match the required isolation and resource limits.'
    }
    if ($checks.Count -ne 16 -or $dataset.all_checks_passed -ne $true -or
        @($checks | Where-Object { $_.passed -ne $true }).Count -ne 0) {
        throw 'Dataset verification did not pass all 16 expected checks.'
    }
    $report.passed = $true
} catch {
    $report.error = $_.Exception.Message
} finally {
    foreach ($path in @($inspectPath, $containerLog, $resourcePath, $datasetPath, $PSCommandPath) + $scriptPaths) {
        if (Test-Path -LiteralPath $path -PathType Leaf) {
            $report.evidence += @{ path = $path; sha256 = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() }
        }
    }
    $json = $report | ConvertTo-Json -Depth 10
    [System.IO.File]::WriteAllText((Join-Path $runRoot 'run-summary.json'), $json, $utf8)
    [System.IO.File]::WriteAllText((Join-Path $outputRoot 'summary.json'), $json, $utf8)
}
$report | ConvertTo-Json -Depth 10
if (-not $report.passed) { throw $report.error }
