#Requires -Version 5.1
<#
.SYNOPSIS
Prepare one fixed-target pilot execution; -Run sends at most one start request.
.DESCRIPTION
Reads and validates the deployed job and existing executions. The default is
read-only. Run modes override an in-memory copy of the complete live template,
never the deployed job. No polling, retry, job update, or secret lookup occurs.
Execution completion must be checked separately, including the expected nonzero
exit for configuration-failure. Concurrent operators must coordinate: ARM offers
no atomic compare-and-start guard across these reads and the final POST.

REST contract:
https://learn.microsoft.com/en-us/rest/api/resource-manager/containerapps/jobs/start?view=rest-resource-manager-containerapps-2025-01-01
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('demo', 'dataset-analysis', 'identity-probe', 'configuration-failure')]
    [string] $Mode,
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^sha256:[0-9a-f]{64}$')]
    [string] $ExpectedImageDigest,
    [switch] $Run
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$workspaceRoot = Split-Path -Parent $PSScriptRoot
$subscriptionId = 'b31e9bd1-6179-4504-819b-f212ed36f609'
$groupPath = '/subscriptions/' + $subscriptionId + '/resourceGroups/rg-ai-command-gateway-dev'
$jobId = $groupPath + '/providers/Microsoft.App/jobs/job-aicg-sn5edmznrgh7s'
$environmentId = $groupPath + '/providers/Microsoft.App/managedEnvironments/cae-aicg-sn5edmznrgh7s'
$identityId = $groupPath + '/providers/Microsoft.ManagedIdentity/userAssignedIdentities/id-aicg-sn5edmznrgh7s'
$clientId = '9ff8b26e-c113-4fe3-80ef-bd0d3273d2c7'
$reviewedDigest = 'sha256:99ae6d8dd7962dfc517a09cce6f46b979af78fd0f5c149bf01e0132b4a2aabad'
$registry = 'craicgsn5edmznrgh7s.azurecr.io'
$image = $registry + '/ai-command-gateway@' + $reviewedDigest
$reviewedProbeSha = '2f9143c2cd6222f9cdee88fa1b67aa2b32302c38687add1c5eb70de3ffdd32ef'
$apiQuery = '?api-version=2025-01-01'
$jobUrl = 'https://management.azure.com' + $jobId + $apiQuery
$executionsPath = $jobId + '/executions'
$executionsUrl = 'https://management.azure.com' + $executionsPath + $apiQuery
$startUrl = 'https://management.azure.com' + $jobId + '/start' + $apiQuery
$runRoot = Join-Path $workspaceRoot ('outputs/azure-pilot-execution/' + [guid]::NewGuid().ToString())
$utf8 = New-Object System.Text.UTF8Encoding($false)
$script:failureCode = $null
$script:readCount = 0
$report = [ordered]@{
    schema_version = '1.0.0'
    recorded_at_utc = [DateTime]::UtcNow.ToString('o')
    job_id = $jobId
    image_digest = $reviewedDigest
    mode = $Mode
    run_requested = [bool] $Run
    expected_exit = $(if ($Mode -eq 'configuration-failure') { 'nonzero' } else { 'zero' })
    status = 'preparing'
    error_code = $null
    prepared = $false
    arm_get_requests = 0
    start_post_attempts = 0
    execution_id = $null
    execution_name = $null
    completion_verified = $false
    deployed_job_modified = $false
    probe_sha256 = $null
    template_sha256 = $null
    request_sha256 = $null
    evidence_directory = $runRoot
    concurrency_limit = 'Non-atomic pre-start checks; coordinate operators; never retry an ambiguous start automatically.'
}

function Stop-Preparation {
    param([string] $Code)
    $script:failureCode = $Code
    throw 'Pilot execution stopped; see the bounded error code in summary.json.'
}

function Save-Json {
    param([string] $Name, $Document)
    $path = Join-Path $runRoot $Name
    [IO.File]::WriteAllText($path, ($Document | ConvertTo-Json -Depth 40), $utf8)
    return $path
}

function Get-Field {
    param($Object, [string] $Name)
    if ($null -eq $Object -or $Object -isnot [pscustomobject]) { Stop-Preparation 'invalid_object_schema' }
    $field = $Object.PSObject.Properties[$Name]
    if ($null -eq $field) { return $null }
    if ($field.Value -is [array]) { Stop-Preparation ('unexpected_array_field:' + $Name) }
    return $field.Value
}

function Get-Array {
    param($Object, [string] $Name, [switch] $Required)
    # Do not let the pipeline collapse an empty or one-item JSON array.
    if ($null -eq $Object -or $Object -isnot [pscustomobject]) { Stop-Preparation 'invalid_array_parent' }
    $field = $Object.PSObject.Properties[$Name]
    if ($null -eq $field -or $null -eq $field.Value) {
        if ($Required) { Stop-Preparation ('missing_array:' + $Name) }
        return ,@()
    }
    if ($field.Value -isnot [array]) { Stop-Preparation ('invalid_array:' + $Name) }
    return ,$field.Value
}

function Assert-Fields {
    param($Object, [string[]] $Allowed, [string] $Label)
    if ($Object -isnot [pscustomobject]) { Stop-Preparation ('invalid_object:' + $Label) }
    foreach ($field in $Object.PSObject.Properties) {
        if ($Allowed -cnotcontains $field.Name) { Stop-Preparation ('unexpected_field:' + $Label) }
    }
}

function Test-Integer {
    param($Value, [int] $Expected)
    return (($Value -is [int] -or $Value -is [long]) -and $Value -eq $Expected)
}

function Read-Arm {
    param([string] $Url, [string] $Label)
    $script:readCount++
    try {
        $json = & $az @azArgumentPrefix rest --subscription $subscriptionId --method get --url $Url --output json --only-show-errors 2>$null
        if ($LASTEXITCODE -ne 0) { Stop-Preparation ('arm_read_failed:' + $Label) }
    } catch { Stop-Preparation ('arm_read_failed:' + $Label) }
    try { $document = ($json -join [Environment]::NewLine) | ConvertFrom-Json } catch {
        Stop-Preparation ('invalid_arm_json:' + $Label)
    }
    if ($document -isnot [pscustomobject]) { Stop-Preparation ('invalid_arm_document:' + $Label) }
    return $document
}

function Assert-Job {
    param($Job)
    if ((Get-Field $Job 'id') -ine $jobId) { Stop-Preparation 'unexpected_job_id' }
    $identity = Get-Field $Job 'identity'
    $identities = Get-Field $identity 'userAssignedIdentities'
    if ((Get-Field $identity 'type') -cne 'UserAssigned' -or $identities -isnot [pscustomobject]) { Stop-Preparation 'unexpected_job_identity' }
    $names = @($identities.PSObject.Properties.Name)
    if ($names.Count -ne 1 -or $names[0] -ine $identityId) { Stop-Preparation 'unexpected_job_identity' }
    $assigned = Get-Field $identities $names[0]
    $assignedClient = Get-Field $assigned 'clientId'
    if ($null -ne $assignedClient -and $assignedClient -cne $clientId) { Stop-Preparation 'unexpected_identity_client' }
    $properties = Get-Field $Job 'properties'
    if ((Get-Field $properties 'provisioningState') -cne 'Succeeded' -or
        (Get-Field $properties 'environmentId') -ine $environmentId -or
        (Get-Field $properties 'workloadProfileName') -cne 'Consumption') { Stop-Preparation 'unexpected_job_environment_or_state' }
    $config = Get-Field $properties 'configuration'
    $manual = Get-Field $config 'manualTriggerConfig'
    if ((Get-Field $config 'triggerType') -cne 'Manual' -or
        -not (Test-Integer (Get-Field $config 'replicaTimeout') 1800) -or
        -not (Test-Integer (Get-Field $config 'replicaRetryLimit') 0) -or
        -not (Test-Integer (Get-Field $manual 'parallelism') 1) -or
        -not (Test-Integer (Get-Field $manual 'replicaCompletionCount') 1)) { Stop-Preparation 'unexpected_job_execution_limits' }
    if ((Get-Array $config 'secrets').Count -ne 0) { Stop-Preparation 'unexpected_job_secrets' }
    $registries = Get-Array $config 'registries' -Required
    $settings = Get-Array $config 'identitySettings' -Required
    if ($registries.Count -ne 1 -or $settings.Count -ne 1) { Stop-Preparation 'unexpected_registry_identity' }
    Assert-Fields $registries[0] @('server', 'identity', 'username', 'passwordSecretRef') 'registry'
    if ((Get-Field $registries[0] 'server') -cne $registry -or
        (Get-Field $registries[0] 'identity') -ine $identityId -or
        (Get-Field $registries[0] 'username') -or (Get-Field $registries[0] 'passwordSecretRef') -or
        (Get-Field $settings[0] 'identity') -ine $identityId -or
        (Get-Field $settings[0] 'lifecycle') -cne 'Main') { Stop-Preparation 'unexpected_registry_identity' }

    $template = Get-Field $properties 'template'
    Assert-Fields $template @('containers', 'initContainers', 'volumes') 'template'
    $containers = Get-Array $template 'containers' -Required
    if ($containers.Count -ne 1 -or (Get-Array $template 'initContainers').Count -ne 0 -or
        (Get-Array $template 'volumes').Count -ne 0) { Stop-Preparation 'unexpected_containers_or_volumes' }
    $container = $containers[0]
    Assert-Fields $container @('name', 'image', 'command', 'args', 'env', 'resources', 'volumeMounts', 'probes') 'container'
    if ((Get-Field $container 'name') -cne 'gateway' -or (Get-Field $container 'image') -cne $image) { Stop-Preparation 'unexpected_container_or_image' }
    $commands = Get-Array $container 'command' -Required
    if ($commands.Count -ne 3 -or $commands[0] -cne 'python' -or $commands[1] -cne '-m' -or
        $commands[2] -cne 'ai_command_gateway.azure_job' -or (Get-Array $container 'args').Count -ne 0 -or
        (Get-Array $container 'volumeMounts').Count -ne 0 -or (Get-Array $container 'probes').Count -ne 0) { Stop-Preparation 'unexpected_command_or_container_behavior' }
    $resources = Get-Field $container 'resources'
    Assert-Fields $resources @('cpu', 'memory', 'ephemeralStorage') 'resources'
    $cpu = Get-Field $resources 'cpu'
    $ephemeral = Get-Field $resources 'ephemeralStorage'
    if (($cpu -isnot [int] -and $cpu -isnot [long] -and $cpu -isnot [double] -and $cpu -isnot [decimal]) -or
        $cpu -ne 1 -or (Get-Field $resources 'memory') -cne '2Gi' -or
        ($null -ne $ephemeral -and ($ephemeral -isnot [string] -or
            ($ephemeral -cne '' -and $ephemeral -cne '4Gi')))) { Stop-Preparation 'unexpected_container_resources' }
    $expectedEnv = @{
        AZURE_CLIENT_ID = $clientId
        AZURE_STORAGE_ACCOUNT_URL = 'https://staicgsn5edmznrgh7s.blob.core.windows.net/'
        AZURE_INPUT_CONTAINER = 'inputs'
        AZURE_OUTPUT_CONTAINER = 'outputs'
        AI_GATEWAY_JOB_MODE = 'dataset-analysis'
        AI_GATEWAY_WORKSPACE = '/tmp/ai-command-gateway'
    }
    $envItems = Get-Array $container 'env' -Required
    if ($envItems.Count -ne 6) { Stop-Preparation 'unexpected_environment_count' }
    $seen = @{}
    foreach ($entry in $envItems) {
        Assert-Fields $entry @('name', 'value', 'secretRef') 'environment'
        $name = Get-Field $entry 'name'
        $value = Get-Field $entry 'value'
        if ($name -isnot [string] -or $expectedEnv.Keys -cnotcontains $name -or $seen.ContainsKey($name)) { Stop-Preparation 'unexpected_or_duplicate_environment' }
        if ($value -isnot [string] -or $value -cne $expectedEnv[$name] -or (Get-Field $entry 'secretRef')) { Stop-Preparation 'unexpected_environment_value_or_secret' }
        $seen[$name] = $true
    }
    # Preserve the complete validated template, including harmless ARM defaults.
    return $template
}

function Read-Executions {
    $items = New-Object System.Collections.Generic.List[object]
    $seen = @{}
    $next = $executionsUrl
    for ($page = 0; $next; $page++) {
        if ($page -ge 20 -or $seen.ContainsKey($next)) { Stop-Preparation 'execution_pagination_limit_or_cycle' }
        $seen[$next] = $true
        try { $uri = [uri] $next } catch { Stop-Preparation 'unexpected_execution_url' }
        if (-not $uri.IsAbsoluteUri -or $uri.Scheme -cne 'https' -or $uri.Host -ine 'management.azure.com' -or
            -not $uri.IsDefaultPort -or $uri.UserInfo -or $uri.Fragment -or $uri.AbsolutePath -ine $executionsPath) { Stop-Preparation 'unexpected_execution_url' }
        $document = Read-Arm $next 'executions'
        foreach ($item in (Get-Array $document 'value' -Required)) {
            if ($items.Count -ge 2000) { Stop-Preparation 'execution_collection_limit' }
            $id = Get-Field $item 'id'
            $name = Get-Field $item 'name'
            if ($name -isnot [string] -or $name -cnotmatch '^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$' -or
                $id -isnot [string] -or $id -ine ($executionsPath + '/' + $name)) { Stop-Preparation 'unexpected_execution_identity' }
            $status = Get-Field (Get-Field $item 'properties') 'status'
            if ($status -isnot [string] -or @('Succeeded', 'Failed', 'Stopped') -cnotcontains $status) { Stop-Preparation 'active_or_unknown_execution' }
            $items.Add([pscustomobject]@{ id = $id; name = $name; status = $status })
        }
        $link = Get-Field $document 'nextLink'
        if ($null -ne $link -and $link -isnot [string]) { Stop-Preparation 'invalid_execution_next_link' }
        $next = $link
    }
    return ,$items.ToArray()
}

try {
    New-Item -ItemType Directory -Path $runRoot -Force | Out-Null
    if ($ExpectedImageDigest -cne $reviewedDigest) { Stop-Preparation 'unreviewed_expected_image_digest' }
    $az = (Get-Command az -CommandType Application | Select-Object -First 1).Source
    $azArgumentPrefix = @()
    if ([IO.Path]::GetExtension($az) -in @('.cmd', '.bat')) {
        # Calling az.cmd with REST query strings can hand '&' to cmd.exe. Invoke
        # the CLI's bundled interpreter directly, with one literal URL argument.
        $cliRoot = Split-Path -Parent (Split-Path -Parent $az)
        $az = Join-Path $cliRoot 'python.exe'
        if (-not (Test-Path -LiteralPath $az -PathType Leaf)) { Stop-Preparation 'azure_cli_bundled_python_missing' }
        $azArgumentPrefix = @('-IBm', 'azure.cli')
    }
    $before = Assert-Job (Read-Arm $jobUrl 'job')
    $executions = Read-Executions
    $beforePath = Save-Json 'template-before.json' $before
    $report.template_sha256 = (Get-FileHash -LiteralPath $beforePath -Algorithm SHA256).Hash.ToLowerInvariant()
    Save-Json 'executions-before.json' @{ value = @($executions) } | Out-Null
    $template = ($before | ConvertTo-Json -Depth 40) | ConvertFrom-Json
    $container = $template.containers[0]
    if ($Mode -in @('demo', 'configuration-failure')) {
        $modeEntry = @($container.env | Where-Object { $_.name -ceq 'AI_GATEWAY_JOB_MODE' })[0]
        $modeEntry.value = if ($Mode -eq 'demo') { 'demo' } else { 'invalid-validation-probe' }
    } elseif ($Mode -eq 'identity-probe') {
        $probePath = Join-Path $PSScriptRoot 'probe_azure_job_identity.py'
        $probeBytes = [IO.File]::ReadAllBytes($probePath)
        $hasher = [Security.Cryptography.SHA256]::Create()
        try { $probeSha = ([BitConverter]::ToString($hasher.ComputeHash($probeBytes))).Replace('-', '').ToLowerInvariant() } finally { $hasher.Dispose() }
        if ($probeBytes.Length -gt 65536 -or $probeSha -cne $reviewedProbeSha) { Stop-Preparation 'unreviewed_identity_probe' }
        $report.probe_sha256 = $reviewedProbeSha
        $encoded = [Convert]::ToBase64String($probeBytes)
        $container.command = @('python', '-c', ("import base64;exec(compile(base64.b64decode('" + $encoded + "'),'<identity-probe>','exec'))"))
        $container | Add-Member -NotePropertyName args -NotePropertyValue @() -Force
    }
    Save-Json 'template-execution.json' $template | Out-Null
    # Job start takes JobExecutionTemplate, not the resource's properties wrapper.
    # All fields of the live container are preserved; empty top-level defaults
    # have been checked and cannot introduce sidecars or mounts.
    $requestPath = Save-Json 'execution-request.json' @{ containers = @($template.containers) }
    $report.request_sha256 = (Get-FileHash -LiteralPath $requestPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $report.prepared = $true
    $report.status = 'prepared_read_only'
    if ($Run) {
        $latest = Assert-Job (Read-Arm $jobUrl 'job_pre_start')
        if (($latest | ConvertTo-Json -Depth 40 -Compress) -cne ($before | ConvertTo-Json -Depth 40 -Compress)) { Stop-Preparation 'job_template_changed_during_preparation' }
        $latestExecutions = Read-Executions
        Save-Json 'executions-pre-start.json' @{ value = @($latestExecutions) } | Out-Null
        # Check that the reviewable request on disk still matches before handing
        # it to the CLI. This does not promise protection from a hostile local OS.
        if ((Get-FileHash -LiteralPath $requestPath -Algorithm SHA256).Hash.ToLowerInvariant() -cne $report.request_sha256) { Stop-Preparation 'execution_request_changed' }
        $report.start_post_attempts = 1
        $report.status = 'start_outcome_unknown_do_not_retry'
        Save-Json 'summary.json' $report | Out-Null
        try {
            $responseText = & $az @azArgumentPrefix rest --subscription $subscriptionId --method post --url $startUrl --body ('@' + $requestPath) --output json --only-show-errors 2>$null
            if ($LASTEXITCODE -ne 0) { Stop-Preparation 'start_outcome_unknown_do_not_retry' }
        } catch { Stop-Preparation 'start_outcome_unknown_do_not_retry' }
        $responseString = ($responseText -join [Environment]::NewLine).Trim()
        if (-not $responseString) {
            # ARM may return 202 with no JSON body. Never treat that as a failed
            # start and retry: the operator must inspect executions separately.
            $report.status = 'start_accepted_execution_identifier_pending'
            Save-Json 'start-response.json' @{ cli_exit_code = 0; body_empty = $true } | Out-Null
        } else {
            try { $response = $responseString | ConvertFrom-Json } catch { Stop-Preparation 'start_response_invalid_do_not_retry' }
            $responseId = Get-Field $response 'id'
            $responseName = Get-Field $response 'name'
            if ($responseName -isnot [string] -or $responseName -cnotmatch '^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$' -or
                $responseId -isnot [string] -or $responseId -ine ($executionsPath + '/' + $responseName) -or
                @($latestExecutions | Where-Object { $_.id -ieq $responseId }).Count -ne 0) { Stop-Preparation 'start_response_identity_invalid_do_not_retry' }
            # Only the fixed ID/name envelope is persisted. Arbitrary provider
            # messages or unexpected response fields are not copied into logs.
            Save-Json 'start-response.json' @{ cli_exit_code = 0; id = $responseId; name = $responseName } | Out-Null
            $report.execution_id = $responseId
            $report.execution_name = $responseName
            $report.status = 'start_accepted_completion_pending'
        }
    }
} catch {
    $report.error_code = if ($script:failureCode) { $script:failureCode } elseif ($report.start_post_attempts) { 'start_outcome_unknown_do_not_retry' } else { 'preparation_failed' }
    if (-not $report.start_post_attempts) { $report.status = 'blocked_no_start' }
} finally {
    $report.arm_get_requests = $script:readCount
    $report.helper_sha256 = (Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant()
    Save-Json 'summary.json' $report | Out-Null
}
[pscustomobject] $report
if ($report.error_code) { throw ('Pilot execution helper failed: ' + $report.error_code + '; evidence: ' + $runRoot) }
