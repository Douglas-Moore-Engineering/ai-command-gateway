#Requires -Version 5.1
<#
.SYNOPSIS
Exercise the pilot-start helper with an in-process CLI double, without Azure.
.DESCRIPTION
Stages the helper and reviewed probe under ignored outputs. Get-Command is
shadowed only in this test scope; every CLI invocation is intercepted and logged
by a local PowerShell double. These are contract tests, not cloud validation.
#>
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$workspaceRoot = Split-Path -Parent $PSScriptRoot
$testRoot = Join-Path $workspaceRoot ('outputs/azure-pilot-start-tests/' + [guid]::NewGuid().ToString())
$stagedScripts = Join-Path $testRoot 'workspace/scripts'
New-Item -ItemType Directory -Path $stagedScripts -Force | Out-Null
$utf8 = New-Object System.Text.UTF8Encoding($false)
foreach ($name in @('start_azure_pilot_test.ps1', 'probe_azure_job_identity.py')) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot $name) -Destination (Join-Path $stagedScripts $name)
}
$helper = Join-Path $stagedScripts 'start_azure_pilot_test.ps1'
$fakeAz = Join-Path $testRoot 'fake-az.ps1'
$statePath = Join-Path $testRoot 'fixture.json'
$callsPath = Join-Path $testRoot 'calls.jsonl'
$jobId = '/subscriptions/b31e9bd1-6179-4504-819b-f212ed36f609/resourceGroups/rg-ai-command-gateway-dev/providers/Microsoft.App/jobs/job-aicg-sn5edmznrgh7s'
$groupId = $jobId.Substring(0, $jobId.IndexOf('/providers/'))
$identityId = $groupId + '/providers/Microsoft.ManagedIdentity/userAssignedIdentities/id-aicg-sn5edmznrgh7s'
$digest = 'sha256:99ae6d8dd7962dfc517a09cce6f46b979af78fd0f5c149bf01e0132b4a2aabad'
$checks = New-Object System.Collections.Generic.List[object]
$originalProbeBytes = [IO.File]::ReadAllBytes((Join-Path $stagedScripts 'probe_azure_job_identity.py'))
$savedState = $env:AICG_START_TEST_STATE
$savedCalls = $env:AICG_START_TEST_CALLS

# This function is deliberately local to the test harness. The production helper
# has no test mode, executable-path override, or configurable subscription/job.
function Get-Command {
    param([string] $Name, [string] $CommandType)
    if ($Name -cne 'az' -or $CommandType -cne 'Application') { throw 'Unexpected command discovery in test.' }
    [pscustomobject]@{ Source = $fakeAz }
}

$stub = @'
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$arguments = @($args)
$utf8 = New-Object System.Text.UTF8Encoding($false)
[IO.File]::AppendAllText($env:AICG_START_TEST_CALLS, (ConvertTo-Json -InputObject $arguments -Compress) + "`n", $utf8)
$fixture = Get-Content -LiteralPath $env:AICG_START_TEST_STATE -Raw | ConvertFrom-Json
$methodIndex = [array]::IndexOf($arguments, '--method')
$urlIndex = [array]::IndexOf($arguments, '--url')
if ($arguments[0] -cne 'rest' -or $methodIndex -lt 0 -or $urlIndex -lt 0) { throw 'Unexpected mocked CLI arguments.' }
$method = $arguments[$methodIndex + 1]
$url = $arguments[$urlIndex + 1]
$global:LASTEXITCODE = 0
if ($method -ceq 'post') {
    if (-not $url.EndsWith('/start?api-version=2025-01-01')) { throw 'Unexpected mocked POST.' }
    if ($fixture.postExit -ne 0) { $global:LASTEXITCODE = [int] $fixture.postExit; return }
    if ($fixture.postRaw -ne $null) { $fixture.postRaw; return }
    $fixture.response | ConvertTo-Json -Depth 40
    return
}
if ($method -cne 'get') { throw 'Unexpected mocked method.' }
if ($fixture.getExit -ne 0) { $global:LASTEXITCODE = [int] $fixture.getExit; return }
$previous = @(Get-Content -LiteralPath $env:AICG_START_TEST_CALLS | ForEach-Object { ,($_ | ConvertFrom-Json) })
if ($url.Contains('/executions?')) {
    $executionCalls = @($previous | Where-Object { @($_ | Where-Object { $_ -is [string] -and $_.Contains('/executions?') }).Count -gt 0 }).Count
    if ($fixture.executionPages.Count -gt 0) {
        $index = [Math]::Min($executionCalls - 1, $fixture.executionPages.Count - 1)
        $fixture.executionPages[$index] | ConvertTo-Json -Depth 40
    } else { $fixture.executions | ConvertTo-Json -Depth 40 }
    return
}
$jobCalls = @($previous | Where-Object { @($_ | Where-Object { $_ -is [string] -and $_.Contains('/jobs/') -and -not $_.Contains('/executions?') -and -not $_.Contains('/start?') }).Count -gt 0 }).Count
if ($jobCalls -gt 1 -and $null -ne $fixture.secondJob) { $fixture.secondJob | ConvertTo-Json -Depth 40 }
else { $fixture.job | ConvertTo-Json -Depth 40 }
'@
[IO.File]::WriteAllText($fakeAz, $stub, $utf8)

function Reset-Fixture {
    $script:fixture = [ordered]@{
        job = [ordered]@{
            id = $jobId
            identity = @{ type = 'UserAssigned'; userAssignedIdentities = @{ $identityId = @{ clientId = '9ff8b26e-c113-4fe3-80ef-bd0d3273d2c7' } } }
            properties = @{
                provisioningState = 'Succeeded'
                environmentId = $groupId + '/providers/Microsoft.App/managedEnvironments/cae-aicg-sn5edmznrgh7s'
                workloadProfileName = 'Consumption'
                configuration = @{
                    triggerType = 'Manual'; replicaTimeout = 1800; replicaRetryLimit = 0
                    manualTriggerConfig = @{ parallelism = 1; replicaCompletionCount = 1 }
                    registries = @(@{ server = 'craicgsn5edmznrgh7s.azurecr.io'; identity = $identityId })
                    identitySettings = @(@{ identity = $identityId; lifecycle = 'Main' })
                    secrets = @()
                }
                template = @{
                    containers = @(@{
                        name = 'gateway'
                        image = 'craicgsn5edmznrgh7s.azurecr.io/ai-command-gateway@' + $digest
                        command = @('python', '-m', 'ai_command_gateway.azure_job')
                        resources = @{ cpu = 1.0; memory = '2Gi'; ephemeralStorage = '4Gi' }
                        args = @(); volumeMounts = @(); probes = @()
                        env = @(
                            @{ name = 'AZURE_CLIENT_ID'; value = '9ff8b26e-c113-4fe3-80ef-bd0d3273d2c7' }
                            @{ name = 'AZURE_STORAGE_ACCOUNT_URL'; value = 'https://staicgsn5edmznrgh7s.blob.core.windows.net/' }
                            @{ name = 'AZURE_INPUT_CONTAINER'; value = 'inputs' }
                            @{ name = 'AZURE_OUTPUT_CONTAINER'; value = 'outputs' }
                            @{ name = 'AI_GATEWAY_JOB_MODE'; value = 'dataset-analysis' }
                            @{ name = 'AI_GATEWAY_WORKSPACE'; value = '/tmp/ai-command-gateway' }
                        )
                    })
                    initContainers = @(); volumes = @()
                }
            }
        }
        secondJob = $null
        executions = @{ value = @(@{ name = 'previous-run'; id = $jobId + '/executions/previous-run'; properties = @{ status = 'Succeeded' } }) }
        executionPages = @()
        response = @{ name = 'new-run'; id = $jobId + '/executions/new-run' }
        postRaw = $null; postExit = 0; getExit = 0
    }
    [IO.File]::WriteAllText($callsPath, '', $utf8)
    [IO.File]::WriteAllBytes((Join-Path $stagedScripts 'probe_azure_job_identity.py'), $originalProbeBytes)
}

function Save-Fixture {
    [IO.File]::WriteAllText($statePath, ($script:fixture | ConvertTo-Json -Depth 40), $utf8)
}

function Assert-Condition {
    param([bool] $Condition, [string] $Message)
    if (-not $Condition) { throw $Message }
}

function Get-Calls {
    foreach ($line in (Get-Content -LiteralPath $callsPath)) { ,($line | ConvertFrom-Json) }
}

function Assert-NoStart {
    foreach ($call in (Get-Calls)) { Assert-Condition ($call -cnotcontains 'post') 'Unexpected start POST.' }
}

function Invoke-Helper {
    param([string] $Mode = 'dataset-analysis', [switch] $Run, [string] $Expected = $digest)
    Save-Fixture
    & $helper -Mode $Mode -ExpectedImageDigest $Expected -Run:$Run
}

function Assert-Blocked {
    param([string] $Code, [string] $Mode = 'dataset-analysis')
    $failed = $false
    try { Invoke-Helper -Mode $Mode -Run | Out-Null } catch {
        $failed = $true
        Assert-Condition ($_.Exception.Message.Contains($Code)) ('Unexpected failure: ' + $_.Exception.Message)
    }
    Assert-Condition $failed 'Expected the start to be blocked.'
    Assert-NoStart
}

function Run-Check {
    param([string] $Name, [scriptblock] $Operation)
    Reset-Fixture
    try {
        & $Operation
        $checks.Add([pscustomobject]@{ name = $Name; passed = $true })
    } catch { $checks.Add([pscustomobject]@{ name = $Name; passed = $false; error = $_.Exception.Message }) }
}

try {
    $env:AICG_START_TEST_STATE = $statePath
    $env:AICG_START_TEST_CALLS = $callsPath
    Assert-Condition ((Get-Command az -CommandType Application).Source -eq $fakeAz) 'CLI double is not active; refusing tests.'
    Run-Check 'default prepares unchanged complete template without a POST' {
        $result = Invoke-Helper
        Assert-NoStart
        Assert-Condition ($result.prepared -and $result.status -eq 'prepared_read_only' -and $result.arm_get_requests -eq 2) 'Unexpected prepare result.'
        $before = Get-Content -LiteralPath (Join-Path $result.evidence_directory 'template-before.json') -Raw
        $after = Get-Content -LiteralPath (Join-Path $result.evidence_directory 'template-execution.json') -Raw
        Assert-Condition ($before -ceq $after) 'Dataset mode altered the live template copy.'
        $request = Get-Content -LiteralPath (Join-Path $result.evidence_directory 'execution-request.json') -Raw | ConvertFrom-Json
        Assert-Condition ($request.containers[0].resources.ephemeralStorage -ceq '4Gi') 'ARM default resource field was lost.'
        Assert-Condition (@($request.PSObject.Properties.Name).Count -eq 1) 'Unexpected request wrapper.'
    }
    Run-Check 'demo changes only the mode environment value' {
        $result = Invoke-Helper -Mode demo
        $template = Get-Content -LiteralPath (Join-Path $result.evidence_directory 'template-execution.json') -Raw | ConvertFrom-Json
        $before = Get-Content -LiteralPath (Join-Path $result.evidence_directory 'template-before.json') -Raw | ConvertFrom-Json
        @($template.containers[0].env | Where-Object name -eq 'AI_GATEWAY_JOB_MODE')[0].value = 'dataset-analysis'
        Assert-Condition (($template | ConvertTo-Json -Depth 40 -Compress) -ceq ($before | ConvertTo-Json -Depth 40 -Compress)) 'Demo changed more than one environment value.'
        Assert-NoStart
    }
    Run-Check 'Azure unspecified empty ephemeral storage survives an otherwise exact start request' {
        $script:fixture.job.properties.template.containers[0].resources.ephemeralStorage = ''
        $result = Invoke-Helper -Mode demo -Run
        $request = Get-Content -LiteralPath (Join-Path $result.evidence_directory 'execution-request.json') -Raw | ConvertFrom-Json
        $resources = $request.containers[0].resources
        Assert-Condition ($result.start_post_attempts -eq 1 -and $resources.cpu -eq 1 -and $resources.memory -ceq '2Gi' -and $resources.ephemeralStorage -ceq '') 'Azure empty storage default was changed or resource bounds were lost.'
    }
    Run-Check 'configuration failure prepares invalid mode and records expected nonzero' {
        $result = Invoke-Helper -Mode configuration-failure
        $request = Get-Content -LiteralPath (Join-Path $result.evidence_directory 'execution-request.json') -Raw | ConvertFrom-Json
        Assert-Condition ($result.expected_exit -ceq 'nonzero' -and @($request.containers[0].env | Where-Object name -eq 'AI_GATEWAY_JOB_MODE')[0].value -ceq 'invalid-validation-probe') 'Configuration failure override missing.'
        Assert-NoStart
    }
    Run-Check 'identity probe injects exactly the reviewed bytes with empty args' {
        $result = Invoke-Helper -Mode identity-probe
        $request = Get-Content -LiteralPath (Join-Path $result.evidence_directory 'execution-request.json') -Raw | ConvertFrom-Json
        $command = $request.containers[0].command
        Assert-Condition ($command.Count -eq 3 -and $command[0] -ceq 'python' -and $command[1] -ceq '-c' -and $request.containers[0].args.Count -eq 0) 'Unexpected identity probe command.'
        Assert-Condition ($command[2] -cmatch "base64\.b64decode\('([A-Za-z0-9+/=]+)'\)") 'Missing base64 probe.'
        $decoded = [Convert]::FromBase64String($Matches[1])
        Assert-Condition ([Convert]::ToBase64String($decoded) -ceq [Convert]::ToBase64String($originalProbeBytes)) 'Injected probe bytes differ.'
        Assert-Condition ($result.probe_sha256 -ceq '2f9143c2cd6222f9cdee88fa1b67aa2b32302c38687add1c5eb70de3ffdd32ef') 'Probe SHA missing.'
        Assert-NoStart
    }
    Run-Check 'Run rechecks job and executions then posts the exact prepared body once' {
        $result = Invoke-Helper -Run
        $calls = @(Get-Calls)
        Assert-Condition ($calls.Count -eq 5 -and $calls[4] -contains 'post' -and $result.start_post_attempts -eq 1) 'Unexpected CLI sequence.'
        $post = $calls[4]
        $body = $post[[array]::IndexOf($post, '--body') + 1]
        Assert-Condition ($body -ceq ('@' + (Join-Path $result.evidence_directory 'execution-request.json'))) 'POST did not use prepared request file.'
        Assert-Condition ($result.execution_id -ceq ($jobId + '/executions/new-run') -and -not $result.completion_verified) 'Execution identity or completion claim incorrect.'
        Assert-Condition ($result.status -ceq 'start_accepted_completion_pending' -and $result.arm_get_requests -eq 4) 'Unexpected start status.'
    }
    Run-Check 'empty successful 202 body is accepted without retry or completion claim' {
        $script:fixture.postRaw = ''
        $result = Invoke-Helper -Run
        Assert-Condition ($result.status -ceq 'start_accepted_execution_identifier_pending' -and $null -eq $result.execution_id -and $result.start_post_attempts -eq 1 -and -not $result.completion_verified) 'Empty response was misclassified.'
        Assert-Condition (@(Get-Calls).Count -eq 5) 'Unexpected retry or polling.'
    }
    Run-Check 'CLI failure after POST is ambiguous and is never retried' {
        $script:fixture.postExit = 1
        $failed = $false
        try { Invoke-Helper -Run | Out-Null } catch { $failed = $_.Exception.Message.Contains('start_outcome_unknown_do_not_retry') }
        Assert-Condition $failed 'Ambiguous start was not reported.'
        Assert-Condition (@(Get-Calls).Count -eq 5) 'Unexpected POST retry.'
    }
    Run-Check 'malformed start response is not retried' {
        $script:fixture.postRaw = '{invalid'
        $failed = $false
        try { Invoke-Helper -Run | Out-Null } catch { $failed = $_.Exception.Message.Contains('start_response_invalid_do_not_retry') }
        Assert-Condition $failed 'Malformed response was not reported.'
        Assert-Condition (@(Get-Calls).Count -eq 5) 'Unexpected POST retry.'
    }
    Run-Check 'previous execution identifier returned by start is rejected without retry' {
        $script:fixture.response = @{ name = 'previous-run'; id = $jobId + '/executions/previous-run' }
        $failed = $false
        try { Invoke-Helper -Run | Out-Null } catch { $failed = $_.Exception.Message.Contains('start_response_identity_invalid_do_not_retry') }
        Assert-Condition $failed 'Reused execution was accepted.'
        Assert-Condition (@(Get-Calls).Count -eq 5) 'Unexpected POST retry.'
    }
    Run-Check 'wrong reviewed digest fails before any CLI call' {
        $failed = $false
        try { Invoke-Helper -Run -Expected ('sha256:' + ('0' * 64)) | Out-Null } catch { $failed = $_.Exception.Message.Contains('unreviewed_expected_image_digest') }
        Assert-Condition ($failed -and @(Get-Calls).Count -eq 0) 'Unreviewed digest reached Azure CLI.'
    }
    $mutations = @(
        @{ name = 'wrong target job'; code = 'unexpected_job_id'; edit = { $script:fixture.job.id += '-other' } }
        @{ name = 'mutable image tag'; code = 'unexpected_container_or_image'; edit = { $script:fixture.job.properties.template.containers[0].image = 'craicgsn5edmznrgh7s.azurecr.io/ai-command-gateway:latest' } }
        @{ name = 'image string disguised as an array'; code = 'unexpected_array_field:image'; edit = { $script:fixture.job.properties.template.containers[0].image = @($script:fixture.job.properties.template.containers[0].image) } }
        @{ name = 'different assigned identity'; code = 'unexpected_job_identity'; edit = { $script:fixture.job.identity.userAssignedIdentities = @{ '/other/identity' = @{} } } }
        @{ name = 'system assigned identity also enabled'; code = 'unexpected_job_identity'; edit = { $script:fixture.job.identity.type = 'SystemAssigned, UserAssigned' } }
        @{ name = 'wrong identity client'; code = 'unexpected_identity_client'; edit = { $script:fixture.job.identity.userAssignedIdentities[$identityId].clientId = '00000000-0000-0000-0000-000000000000' } }
        @{ name = 'different managed environment'; code = 'unexpected_job_environment_or_state'; edit = { $script:fixture.job.properties.environmentId += '-other' } }
        @{ name = 'automatic trigger'; code = 'unexpected_job_execution_limits'; edit = { $script:fixture.job.properties.configuration.triggerType = 'Schedule' } }
        @{ name = 'replica retries'; code = 'unexpected_job_execution_limits'; edit = { $script:fixture.job.properties.configuration.replicaRetryLimit = 1 } }
        @{ name = 'extra parallelism'; code = 'unexpected_job_execution_limits'; edit = { $script:fixture.job.properties.configuration.manualTriggerConfig.parallelism = 2 } }
        @{ name = 'job secrets'; code = 'unexpected_job_secrets'; edit = { $script:fixture.job.properties.configuration.secrets = @(@{ name = 'unreviewed'; value = 'must-not-appear-in-evidence' }) } }
        @{ name = 'registry credential'; code = 'unexpected_registry_identity'; edit = { $script:fixture.job.properties.configuration.registries[0].passwordSecretRef = 'unreviewed' } }
        @{ name = 'extra container'; code = 'unexpected_containers_or_volumes'; edit = { $script:fixture.job.properties.template.containers += @{ name = 'other' } } }
        @{ name = 'init container'; code = 'unexpected_containers_or_volumes'; edit = { $script:fixture.job.properties.template.initContainers = @(@{ name = 'other' }) } }
        @{ name = 'volume'; code = 'unexpected_containers_or_volumes'; edit = { $script:fixture.job.properties.template.volumes = @(@{ name = 'other' }) } }
        @{ name = 'alternate command'; code = 'unexpected_command_or_container_behavior'; edit = { $script:fixture.job.properties.template.containers[0].command = @('sh', '-c', 'echo') } }
        @{ name = 'nonempty arguments'; code = 'unexpected_command_or_container_behavior'; edit = { $script:fixture.job.properties.template.containers[0].args = @('unreviewed') } }
        @{ name = 'CPU as boolean'; code = 'unexpected_container_resources'; edit = { $script:fixture.job.properties.template.containers[0].resources.cpu = $true } }
        @{ name = 'larger memory'; code = 'unexpected_container_resources'; edit = { $script:fixture.job.properties.template.containers[0].resources.memory = '4Gi' } }
        @{ name = 'unreviewed nonempty ephemeral storage'; code = 'unexpected_container_resources'; edit = { $script:fixture.job.properties.template.containers[0].resources.ephemeralStorage = '8Gi' } }
        @{ name = 'Boolean false disguised as unspecified ephemeral storage'; code = 'unexpected_container_resources'; edit = { $script:fixture.job.properties.template.containers[0].resources.ephemeralStorage = $false } }
        @{ name = 'numeric zero disguised as unspecified ephemeral storage'; code = 'unexpected_container_resources'; edit = { $script:fixture.job.properties.template.containers[0].resources.ephemeralStorage = 0 } }
        @{ name = 'GPU resource'; code = 'unexpected_field:resources'; edit = { $script:fixture.job.properties.template.containers[0].resources.gpu = 1 } }
        @{ name = 'extra environment entry'; code = 'unexpected_environment_count'; edit = { $script:fixture.job.properties.template.containers[0].env += @{ name = 'PYTHONPATH'; value = '/other' } } }
        @{ name = 'duplicate environment entry'; code = 'unexpected_or_duplicate_environment'; edit = { $script:fixture.job.properties.template.containers[0].env[5] = $script:fixture.job.properties.template.containers[0].env[0] } }
        @{ name = 'secret environment entry'; code = 'unexpected_environment_value_or_secret'; edit = { $script:fixture.job.properties.template.containers[0].env[0].secretRef = 'unreviewed' } }
        @{ name = 'existing mode not dataset analysis'; code = 'unexpected_environment_value_or_secret'; edit = { $script:fixture.job.properties.template.containers[0].env[4].value = 'demo' } }
        @{ name = 'wrong storage destination'; code = 'unexpected_environment_value_or_secret'; edit = { $script:fixture.job.properties.template.containers[0].env[1].value = 'https://other.blob.core.windows.net/' } }
        @{ name = 'scalar containers instead of JSON array'; code = 'invalid_array:containers'; edit = { $script:fixture.job.properties.template.containers = $script:fixture.job.properties.template.containers[0] } }
        @{ name = 'unexpected container behavior field'; code = 'unexpected_field:container'; edit = { $script:fixture.job.properties.template.containers[0].securityContext = @{ privileged = $true } } }
    )
    foreach ($mutation in $mutations) {
        Run-Check ('blocks ' + $mutation.name) {
            & $mutation.edit
            Assert-Blocked $mutation.code
        }
    }
    foreach ($status in @('Running', 'Pending', 'Unknown', 'Processing', '', $null)) {
        Run-Check ('blocks nonterminal or unknown execution status: ' + [string] $status) {
            $script:fixture.executions.value[0].properties.status = $status
            Assert-Blocked 'active_or_unknown_execution'
        }
    }
    foreach ($status in @('Failed', 'Stopped')) {
        Run-Check ('accepts terminal execution: ' + $status) {
            $script:fixture.executions.value[0].properties.status = $status
            $result = Invoke-Helper
            Assert-Condition $result.prepared 'Terminal execution blocked preparation.'
            Assert-NoStart
        }
    }
    Run-Check 'empty execution collection is accepted' {
        $script:fixture.executions.value = @()
        $result = Invoke-Helper
        Assert-Condition $result.prepared 'Empty executions blocked preparation.'
        Assert-NoStart
    }
    Run-Check 'active execution on page two blocks starting' {
        $script:fixture.executionPages = @(
            @{ value = @(); nextLink = 'https://management.azure.com' + $jobId + '/executions?api-version=2025-01-01&skipToken=2' }
            @{ value = @(@{ name = 'active'; id = $jobId + '/executions/active'; properties = @{ status = 'Running' } }) }
        )
        Assert-Blocked 'active_or_unknown_execution'
        Assert-Condition (@(Get-Calls).Count -eq 3) 'Did not read second page.'
    }
    Run-Check 'pagination keeps query ampersand in one literal argument' {
        $nextLink = 'https://management.azure.com' + $jobId + '/executions?api-version=2025-01-01&skipToken=2'
        $script:fixture.executionPages = @(@{ value = @(); nextLink = $nextLink }, @{ value = @() })
        $result = Invoke-Helper
        $calls = @(Get-Calls)
        Assert-Condition ($result.prepared -and $calls[2] -ccontains $nextLink) 'Continuation URL was split.'
        Assert-NoStart
    }
    foreach ($nextLink in @('https://attacker.invalid/steal', ('https://management.azure.com' + $jobId + '/executions/other?api-version=2025-01-01'), ('https://management.azure.com' + $jobId + '/executions?api-version=2025-01-01'))) {
        Run-Check ('rejects unsafe or cyclic pagination: ' + $nextLink) {
            $script:fixture.executions.nextLink = $nextLink
            $code = if ($nextLink.EndsWith('/executions?api-version=2025-01-01')) { 'execution_pagination_limit_or_cycle' } else { 'unexpected_execution_url' }
            Assert-Blocked $code
            Assert-Condition (@(Get-Calls).Count -eq 2) 'Followed unsafe pagination.'
        }
    }
    Run-Check 'active execution arriving during preparation blocks final POST' {
        $script:fixture.executionPages = @(
            @{ value = @() }
            @{ value = @(@{ name = 'arrived'; id = $jobId + '/executions/arrived'; properties = @{ status = 'Pending' } }) }
        )
        Assert-Blocked 'active_or_unknown_execution'
        Assert-Condition (@(Get-Calls).Count -eq 4) 'Missing second pre-start read.'
    }
    Run-Check 'changed live template blocks final POST even when both versions are valid' {
        $script:fixture.secondJob = ($script:fixture.job | ConvertTo-Json -Depth 40 | ConvertFrom-Json)
        $script:fixture.secondJob.properties.template.containers[0].PSObject.Properties.Remove('args')
        Assert-Blocked 'job_template_changed_during_preparation'
        Assert-Condition (@(Get-Calls).Count -eq 3) 'Missing template recheck.'
    }
    Run-Check 'altered reviewed probe blocks execution' {
        [IO.File]::AppendAllText((Join-Path $stagedScripts 'probe_azure_job_identity.py'), "`n# changed", $utf8)
        Assert-Blocked 'unreviewed_identity_probe' 'identity-probe'
    }
    Run-Check 'failed control-plane read blocks start' {
        $script:fixture.getExit = 7
        Assert-Blocked 'arm_read_failed:job'
    }
    Run-Check 'Windows CLI batch wrapper requires its bundled Python before any command' {
        $oldFakeAz = $fakeAz
        try {
            $fakeAz = Join-Path $testRoot 'missing-cli/wbin/az.cmd'
            Assert-Blocked 'azure_cli_bundled_python_missing'
            Assert-Condition (@(Get-Calls).Count -eq 0) 'Batch wrapper was invoked without bundled Python.'
        } finally { $fakeAz = $oldFakeAz }
    }
    Run-Check 'unexpected secret content is not persisted in helper evidence' {
        $script:fixture.job.properties.configuration.secrets = @(@{ name = 'secret'; value = 'must-not-appear-in-evidence' })
        Assert-Blocked 'unexpected_job_secrets'
        $evidenceRoot = Join-Path $testRoot 'workspace/outputs/azure-pilot-execution'
        foreach ($file in (Get-ChildItem -LiteralPath $evidenceRoot -Recurse -File -Filter '*.json')) {
            Assert-Condition (-not ([IO.File]::ReadAllText($file.FullName).Contains('must-not-appear-in-evidence'))) 'Unexpected secret was copied into evidence.'
        }
    }
} finally {
    $env:AICG_START_TEST_STATE = $savedState
    $env:AICG_START_TEST_CALLS = $savedCalls
    $summary = [ordered]@{
        schema_version = '1.0.0'
        scope = 'Mocked CLI contract only; no Azure requests or job execution'
        passed = @($checks | Where-Object { -not $_.passed }).Count -eq 0
        check_count = $checks.Count
        checks = @($checks.ToArray())
        script_sha256 = (Get-FileHash -LiteralPath $helper -Algorithm SHA256).Hash.ToLowerInvariant()
        recorded_at_utc = [DateTime]::UtcNow.ToString('o')
        evidence_directory = $testRoot
    }
    [IO.File]::WriteAllText((Join-Path $testRoot 'summary.json'), ($summary | ConvertTo-Json -Depth 12), $utf8)
}
$summary | ConvertTo-Json -Depth 12
if (-not $summary.passed) { throw 'Pilot start contract tests failed; see summary.json.' }
