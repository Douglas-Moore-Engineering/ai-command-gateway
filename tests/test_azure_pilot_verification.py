"""Control-plane verifier tests; the Azure CLI executable is replaced entirely."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_azure_pilot.ps1"
POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")
pytestmark = pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is required")
SUB = "b31e9bd1-6179-4504-819b-f212ed36f609"
SUBPATH = f"/subscriptions/{SUB}"
GROUP = "rg-ai-command-gateway-dev"
BASE = f"{SUBPATH}/resourceGroups/{GROUP}"
OPGROUP = f"{SUBPATH}/resourceGroups/rg-ai-command-gateway-operator"
PRINCIPAL = "11111111-2222-4333-8444-555555555555"
OPPRINCIPAL = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
CLIENT = "66666666-7777-4888-8999-000000000000"
DIGEST = "sha256:" + "a" * 64
ZONES = (
    "privatelink.azurecr.io", "privatelink.blob.core.windows.net",
    "privatelink.monitor.azure.com", "privatelink.oms.opinsights.azure.com",
    "privatelink.ods.opinsights.azure.com", "privatelink.agentsvc.azure-automation.net",
)
NAMES = {
    "storage": ("Microsoft.Storage/storageAccounts", "staicgsn5edmznrgh7s"),
    "registry": ("Microsoft.ContainerRegistry/registries", "craicgsn5edmznrgh7s"),
    "environment": ("Microsoft.App/managedEnvironments", "cae-aicg-sn5edmznrgh7s"),
    "identity": ("Microsoft.ManagedIdentity/userAssignedIdentities", "id-aicg-sn5edmznrgh7s"),
    "vnet": ("Microsoft.Network/virtualNetworks", "vnet-aicg-sn5edmznrgh7s"),
    "workspace": ("Microsoft.OperationalInsights/workspaces", "log-aicg-sn5edmznrgh7s"),
    "monitor": ("Microsoft.Insights/privateLinkScopes", "ampls-aicg-sn5edmznrgh7s"),
    "job": ("Microsoft.App/jobs", "job-aicg-sn5edmznrgh7s"),
}
IDS = {key: f"{BASE}/providers/{typ}/{name}" for key, (typ, name) in NAMES.items()}
OPVNET = f"{OPGROUP}/providers/Microsoft.Network/virtualNetworks/vnet-aicg-operator"
OPIDENTITY = f"{OPGROUP}/providers/Microsoft.ManagedIdentity/userAssignedIdentities/id-aicg-operator"
ROLEPATH = f"{SUBPATH}/providers/Microsoft.Authorization/roleAssignments"


def role(scope, role_id, principal=PRINCIPAL):
    return {"properties": {"scope": scope, "principalId": principal,
            "roleDefinitionId": f"{SUBPATH}/providers/Microsoft.Authorization/roleDefinitions/{role_id}"}}


def peering(name, target):
    return {"name": name, "properties": {
        "remoteVirtualNetwork": {"id": target}, "provisioningState": "Succeeded",
        "peeringState": "Connected", "allowVirtualNetworkAccess": True,
        "allowForwardedTraffic": False, "allowGatewayTransit": False, "useRemoteGateways": False}}


@pytest.fixture
def state():
    inventory = [{"id": IDS[key], "type": typ, "name": name} for key, (typ, name) in NAMES.items()]
    outputs = {
        "storageAccountName": NAMES["storage"][1], "registryName": NAMES["registry"][1],
        "environmentName": NAMES["environment"][1], "managedIdentityResourceId": IDS["identity"],
        "vnetId": IDS["vnet"], "logAnalyticsWorkspaceId": IDS["workspace"],
        "managedIdentityClientId": CLIENT, "jobName": NAMES["job"][1],
        "registryLoginServer": NAMES["registry"][1] + ".azurecr.io",
        "storageAccountUrl": "https://" + NAMES["storage"][1] + ".blob.core.windows.net",
    }
    documents = {
        BASE + "/providers/Microsoft.Resources/deployments/aicg-bootstrap": {
            "properties": {"provisioningState": "Succeeded", "outputs": {key: {"value": val} for key, val in outputs.items()}}},
        BASE + "/resources": {"value": inventory},
        IDS["storage"]: {"sku": {"name": "Standard_ZRS"}, "properties": {
            "publicNetworkAccess": "Disabled", "allowSharedKeyAccess": False,
            "minimumTlsVersion": "TLS1_2", "allowBlobPublicAccess": False}},
        IDS["registry"]: {"sku": {"name": "Premium"}, "properties": {
            "publicNetworkAccess": "Disabled", "adminUserEnabled": False, "anonymousPullEnabled": False}},
        IDS["environment"]: {"properties": {
            "vnetConfiguration": {"internal": True, "infrastructureSubnetId": IDS["vnet"] + "/subnets/snet-environment"},
            "publicNetworkAccess": "Disabled", "workloadProfiles": [{"name": "Consumption", "workloadProfileType": "Consumption"}]}},
        IDS["identity"]: {"properties": {"principalId": PRINCIPAL, "clientId": CLIENT}},
        IDS["workspace"]: {"properties": {
            "publicNetworkAccessForIngestion": "Disabled", "publicNetworkAccessForQuery": "Disabled", "features": {"disableLocalAuth": True}}},
        IDS["monitor"]: {"properties": {"accessModeSettings": {
            "ingestionAccessMode": "PrivateOnly", "queryAccessMode": "PrivateOnly", "exclusions": []}}},
        IDS["monitor"] + "/scopedResources": {"value": [{"properties": {"linkedResourceId": IDS["workspace"]}}]},
        BASE + "/providers/Microsoft.App/jobs": {"value": [{"id": IDS["job"]}]},
        IDS["vnet"] + "/virtualNetworkPeerings": {"value": []},
        SUBPATH + "/resourcegroups": {"value": [{"id": BASE}]},
    }
    for service in ("storage", "registry", "monitor"):
        name = "pep-" + service
        rid = BASE + "/providers/Microsoft.Network/privateEndpoints/" + name
        inventory.append({"id": rid, "type": "Microsoft.Network/privateEndpoints", "name": name})
        documents[rid] = {"properties": {"provisioningState": "Succeeded", "subnet": {"id": IDS["vnet"] + "/subnets/snet-private-endpoints"},
            "privateLinkServiceConnections": [{"properties": {
                "privateLinkServiceId": IDS[service], "privateLinkServiceConnectionState": {"status": "Approved"}}}]}}
    for zone in ZONES:
        rid = BASE + "/providers/Microsoft.Network/privateDnsZones/" + zone
        inventory.append({"id": rid, "type": "Microsoft.Network/privateDnsZones", "name": zone})
        documents[rid + "/virtualNetworkLinks"] = {"value": [{"name": "link-aicg-sn5edmznrgh7s", "properties": {
            "virtualNetwork": {"id": IDS["vnet"]}, "provisioningState": "Succeeded", "registrationEnabled": False}}]}
    documents[IDS["job"]] = {
        "identity": {"type": "UserAssigned", "userAssignedIdentities": {IDS["identity"]: {"clientId": CLIENT, "principalId": PRINCIPAL}}},
        "properties": {
            "provisioningState": "Succeeded", "environmentId": IDS["environment"], "workloadProfileName": "Consumption",
            "configuration": {"triggerType": "Manual", "replicaTimeout": 1800, "replicaRetryLimit": 0,
                "manualTriggerConfig": {"parallelism": 1, "replicaCompletionCount": 1},
                "registries": [{"server": outputs["registryLoginServer"], "identity": IDS["identity"]}],
                "identitySettings": [{"identity": IDS["identity"], "lifecycle": "Main"}], "secrets": []},
            "template": {"containers": [{"name": "gateway", "image": outputs["registryLoginServer"] + "/ai-command-gateway@" + DIGEST,
                "command": ["python", "-m", "ai_command_gateway.azure_job"], "resources": {"cpu": 1, "memory": "2Gi"},
                "env": [{"name": key, "value": value} for key, value in {
                    "AZURE_CLIENT_ID": CLIENT, "AZURE_STORAGE_ACCOUNT_URL": outputs["storageAccountUrl"],
                    "AZURE_INPUT_CONTAINER": "inputs", "AZURE_OUTPUT_CONTAINER": "outputs",
                    "AI_GATEWAY_JOB_MODE": "dataset-analysis", "AI_GATEWAY_WORKSPACE": "/tmp/ai-command-gateway"}.items()]}]}}}
    roles = [role(IDS["storage"] + "/blobServices/default/containers/inputs", "2a2b9908-6ea1-4ae2-8e65-a410df84e7d1"),
             role(IDS["storage"] + "/blobServices/default/containers/outputs", "ba92f5b4-2d11-453d-a403-e96b0029c9fe"),
             role(IDS["registry"], "7f951dda-4ed3-4680-a7ca-43fe172d538d")]
    return {"documents": documents, "roles": {PRINCIPAL: roles}, "readFailure": None, "malformedJson": None,
            "cliErrors": None, "nativeWarning": None}


def with_operator(state):
    for zone in ZONES:
        rid = BASE + "/providers/Microsoft.Network/privateDnsZones/" + zone + "/virtualNetworkLinks"
        state["documents"][rid]["value"].append({"name": "link-aicg-operator", "properties": {
            "virtualNetwork": {"id": OPVNET}, "provisioningState": "Succeeded", "registrationEnabled": False}})
    state["documents"][IDS["vnet"] + "/virtualNetworkPeerings"]["value"] = [peering("to-aicg-operator", OPVNET)]
    state["documents"][OPVNET + "/virtualNetworkPeerings"] = {"value": [peering("to-aicg-foundation", IDS["vnet"])]}
    state["documents"][OPIDENTITY] = {"properties": {"principalId": OPPRINCIPAL}}
    state["roles"][OPPRINCIPAL] = [role(scope, rid, OPPRINCIPAL) for scope, rid in (
        (IDS["storage"] + "/blobServices/default/containers/inputs", "ba92f5b4-2d11-453d-a403-e96b0029c9fe"),
        (IDS["storage"] + "/blobServices/default/containers/outputs", "2a2b9908-6ea1-4ae2-8e65-a410df84e7d1"),
        (IDS["registry"], "8311e382-0749-4cb8-b61a-304f252e45ec"),
        (IDS["workspace"], "73c42c96-874c-492b-b04d-ab87d138a893"))]


FAKE_CLI = r"""
$call = @($args | ForEach-Object { [string]$_ })
ConvertTo-Json -InputObject $call -Compress | Add-Content -LiteralPath $env:AICG_PILOT_CALLS -Encoding UTF8
$global:LASTEXITCODE = 0
if (($call[0..2] -join '|') -ne '-IBm|azure.cli|rest') { throw 'Only direct bundled-Python CLI REST calls are mocked.' }
if ($call[[Array]::IndexOf($call, '--method') + 1] -ne 'get') { throw 'Mutation not permitted in verifier test.' }
$url = [Uri]$call[[Array]::IndexOf($call, '--url') + 1]
$fixture = Get-Content -LiteralPath $env:AICG_PILOT_FIXTURE -Raw | ConvertFrom-Json
$id = $url.AbsolutePath
if ($null -ne $fixture.cliErrors -and $id -eq $fixture.cliErrors.path) {
    $attempt = @(Get-Content -LiteralPath $env:AICG_PILOT_CALLS | Where-Object { $_.Contains($id + '?') }).Count
    if ($attempt -le $fixture.cliErrors.attempts) {
        Write-Error -Message $fixture.cliErrors.text -ErrorAction Continue
        $global:LASTEXITCODE = 1
        return
    }
}
if ($id -eq $fixture.nativeWarning) {
    & $env:AICG_PILOT_TEST_PYTHON -c 'import sys; sys.stderr.write("native diagnostic must remain private\n")'
    $global:LASTEXITCODE = 0
}
if ($id -eq $fixture.readFailure) { $global:LASTEXITCODE = 1; 'Private response must not appear in report'; return }
if ($id -eq $fixture.malformedJson) { '{bad-json'; return }
if ($id.EndsWith('/providers/Microsoft.Authorization/roleAssignments')) {
    $query = [Uri]::UnescapeDataString($url.Query)
    if ($query -notmatch "&\`$filter=principalId eq '([^']+)'$") { throw 'Principal filter was split, omitted or malformed.' }
    $records = $fixture.roles.PSObject.Properties[$Matches[1]].Value
    if ($null -eq $records) { throw 'Unknown mock principal.' }
    @{ value = @($records) } | ConvertTo-Json -Depth 40 -Compress
    return
}
$field = $fixture.documents.PSObject.Properties[$id]
if ($null -eq $field) { throw "Mock does not recognize path: $id" }
$field.Value | ConvertTo-Json -Depth 40 -Compress
"""

HARNESS = r"""
$ErrorActionPreference = 'Stop'
# The production resolver sees az.cmd, takes its bundled-Python branch, and is
# redirected only at that final local executable path to a PowerShell test stub.
function global:Get-Command {
    param($Name, $CommandType, $ErrorAction)
    if ($Name -eq 'az') { return [pscustomobject]@{ Source = $env:AICG_PILOT_FAKE_AZ } }
    throw 'Unexpected command discovery in verifier test.'
}
function global:Join-Path {
    param($Path, $ChildPath)
    if ($Path -eq $env:AICG_PILOT_FAKE_ROOT -and $ChildPath -eq 'python.exe') { return $env:AICG_PILOT_FAKE_CLI }
    Microsoft.PowerShell.Management\Join-Path -Path $Path -ChildPath $ChildPath
}
$parameters = @{
    SubscriptionId = $env:AICG_PILOT_SUB
    ResourceGroup = 'rg-ai-command-gateway-dev'
    ExpectedImageDigest = $env:AICG_PILOT_DIGEST
    ExpectedJobMode = 'dataset-analysis'
    OutputDirectory = $env:AICG_PILOT_OUTPUT
}
if ($env:AICG_PILOT_OPERATOR -eq 'true') { $parameters.OperatorPresent = $true }
& $env:AICG_PILOT_SCRIPT @parameters
"""


def verify(tmp_path: Path, state, *, operator=False, digest=DIGEST):
    fixture = tmp_path / "fixture.json"
    fixture.write_text(json.dumps(state), encoding="utf-8")
    cli = tmp_path / "fake-cli.ps1"
    cli.write_text(FAKE_CLI, encoding="utf-8-sig")
    harness = tmp_path / "harness.ps1"
    harness.write_text(HARNESS, encoding="utf-8-sig")
    calls_file = tmp_path / "calls.jsonl"
    output = tmp_path / "report"
    env = dict(os.environ, AICG_PILOT_SCRIPT=str(SCRIPT), AICG_PILOT_FIXTURE=str(fixture),
               AICG_PILOT_CALLS=str(calls_file), AICG_PILOT_OUTPUT=str(output),
               AICG_PILOT_SUB=SUB, AICG_PILOT_DIGEST=digest, AICG_PILOT_OPERATOR=str(operator).lower(),
               AICG_PILOT_TEST_PYTHON=sys.executable,
               AICG_PILOT_FAKE_CLI=str(cli), AICG_PILOT_FAKE_ROOT=str(tmp_path / "fake-msi"),
               AICG_PILOT_FAKE_AZ=str(tmp_path / "fake-msi" / "wbin" / "az.cmd"))
    result = subprocess.run([POWERSHELL, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(harness)],
                            env=env, capture_output=True, text=True, timeout=60)
    report = json.loads((output / "summary.json").read_text(encoding="utf-8-sig"))
    calls = [json.loads(line) for line in calls_file.read_text(encoding="utf-8-sig").splitlines()]
    assert report["verifier_sha256"] == hashlib.sha256(SCRIPT.read_bytes()).hexdigest()
    for call in calls:
        assert call[:3] == ["-IBm", "azure.cli", "rest"]
        assert call[call.index("--method") + 1] == "get"
        assert call[call.index("--subscription") + 1] == SUB
        assert "listKeys" not in " ".join(call) and "listSecrets" not in " ".join(call)
    return result, report, calls


def check(report, name):
    return next(item for item in report["checks"] if item["name"] == name)


def test_final_pilot_configuration_passes(tmp_path, state):
    result, report, calls = verify(tmp_path, state)
    assert result.returncode == 0, result.stdout + result.stderr
    assert report["passed"] is True
    assert all(item["passed"] for item in report["checks"])
    assert check(report, "exact_private_dns_link_count")["observed"]["actual"] == 6
    assert check(report, "temporary_operator_group_removed")["passed"]
    assert report["arm_get_requests"] == len(calls)
    assert not any(report[name] for name in ("resource_changes_performed", "secrets_requested", "dns_resolution_tested", "data_plane_tested", "job_execution_tested"))


def test_operator_present_configuration_passes(tmp_path, state):
    with_operator(state)
    result, report, _ = verify(tmp_path, state, operator=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert report["passed"]
    assert check(report, "exact_private_dns_link_count")["observed"]["actual"] == 12
    assert check(report, "operator_four_exact_scoped_roles")["passed"]


def test_wrong_image_digest_fails_without_echoing_untrusted_image(tmp_path, state):
    state["documents"][IDS["job"]]["properties"]["template"]["containers"][0]["image"] = "untrusted-registry.example/image:mutable"
    result, report, _ = verify(tmp_path, state)
    assert result.returncode != 0 and not report["passed"]
    assert not check(report, "job_reviewed_image_digest")["passed"]
    assert "untrusted-registry" not in json.dumps(report)


@pytest.mark.parametrize("service", ["storage", "registry", "environment"])
def test_public_service_is_rejected(tmp_path, state, service):
    state["documents"][IDS[service]]["properties"]["publicNetworkAccess"] = "Enabled"
    result, report, _ = verify(tmp_path, state)
    assert result.returncode != 0 and not report["passed"]
    assert report["error_code"] == "configuration_checks_failed"


def test_extra_job_identity_role_is_rejected(tmp_path, state):
    state["roles"][PRINCIPAL].append(role(BASE, "b24988ac-6180-42a0-ab88-20f7382dd24c"))
    result, report, _ = verify(tmp_path, state)
    assert result.returncode != 0 and not report["passed"]
    assert not check(report, "managed_identity_three_exact_scoped_roles")["passed"]


def test_extra_operator_identity_role_is_rejected(tmp_path, state):
    with_operator(state)
    state["roles"][OPPRINCIPAL].append(role(BASE, "b24988ac-6180-42a0-ab88-20f7382dd24c", OPPRINCIPAL))
    result, report, _ = verify(tmp_path, state, operator=True)
    assert result.returncode != 0 and not check(report, "operator_four_exact_scoped_roles")["passed"]


def test_unexpected_dns_link_and_remaining_operator_group_fail(tmp_path, state):
    state["documents"][BASE + "/providers/Microsoft.Network/privateDnsZones/" + ZONES[0] + "/virtualNetworkLinks"]["value"].append(
        {"name": "unexpected", "properties": {"virtualNetwork": {"id": OPVNET}, "provisioningState": "Succeeded", "registrationEnabled": False}})
    state["documents"][SUBPATH + "/resourcegroups"]["value"].append({"id": OPGROUP})
    result, report, _ = verify(tmp_path, state)
    assert result.returncode != 0
    assert not check(report, "exact_private_dns_link_count")["passed"]
    assert not check(report, "temporary_operator_group_removed")["passed"]


def test_wrong_peering_target_fails(tmp_path, state):
    with_operator(state)
    state["documents"][OPVNET + "/virtualNetworkPeerings"]["value"][0]["properties"]["remoteVirtualNetwork"]["id"] = "unrelated-vnet"
    result, report, _ = verify(tmp_path, state, operator=True)
    assert result.returncode != 0 and not check(report, "operator_reciprocal_peerings")["passed"]


@pytest.mark.parametrize("field,value", [("replicaRetryLimit", 2), ("replicaTimeout", 3600), ("triggerType", "Schedule"), ("replicaRetryLimit", "0")])
def test_job_execution_bounds_are_checked(tmp_path, state, field, value):
    state["documents"][IDS["job"]]["properties"]["configuration"][field] = value
    result, report, _ = verify(tmp_path, state)
    assert result.returncode != 0 and not check(report, "job_manual_bounded_execution")["passed"]


def test_extra_env_secret_is_rejected_without_value_in_report(tmp_path, state):
    state["documents"][IDS["job"]]["properties"]["template"]["containers"][0]["env"].append({"name": "TOKEN", "value": "sensitive-do-not-report"})
    result, report, _ = verify(tmp_path, state)
    assert result.returncode != 0 and not check(report, "job_six_exact_environment_values")["passed"]
    assert "sensitive-do-not-report" not in json.dumps(report)


def test_registry_credentials_are_rejected_without_echo(tmp_path, state):
    state["documents"][IDS["job"]]["properties"]["configuration"]["registries"][0]["passwordSecretRef"] = "secret-reference-do-not-report"
    result, report, _ = verify(tmp_path, state)
    assert result.returncode != 0 and not check(report, "job_registry_identity_without_secrets")["passed"]
    assert "secret-reference-do-not-report" not in json.dumps(report)


def test_string_cpu_does_not_pass_numeric_resource_check(tmp_path, state):
    state["documents"][IDS["job"]]["properties"]["template"]["containers"][0]["resources"]["cpu"] = "1"
    result, report, _ = verify(tmp_path, state)
    assert result.returncode != 0 and not check(report, "job_command_and_resources")["passed"]


@pytest.mark.parametrize("failure", ["readFailure", "malformedJson"])
def test_read_errors_are_bounded(tmp_path, state, failure):
    state[failure] = IDS["storage"]
    result, report, _ = verify(tmp_path, state)
    assert result.returncode != 0 and not report["passed"]
    assert report["error_code"] in ("arm_read_failed:storage", "invalid_arm_json:storage")
    assert "Private response" not in json.dumps(report)


def test_foreign_pagination_url_is_never_called(tmp_path, state):
    state["documents"][BASE + "/resources"]["nextLink"] = "https://untrusted.example/steal"
    result, report, calls = verify(tmp_path, state)
    assert result.returncode != 0
    assert report["error_code"] == "unexpected_arm_url:resource_inventory"
    assert "untrusted.example" not in " ".join(" ".join(call) for call in calls)


@pytest.mark.parametrize("text,kind", [
    ("ERROR: Connection aborted: RemoteDisconnected; private detail", "transient_transport"),
    ("ERROR: (TooManyRequests) private detail", "transient_http"),
])
def test_recognized_transient_get_retries_and_reports_attempt(tmp_path, state, text, kind):
    state["cliErrors"] = {"path": IDS["storage"], "attempts": 1, "text": text}
    result, report, calls = verify(tmp_path, state)
    assert result.returncode == 0 and report["passed"]
    assert report["arm_get_requests"] == len(calls)
    assert report["arm_read_diagnostics"] == [
        {"step": "storage", "attempt": 1, "exit_code": 1, "code": kind, "retry": True}]
    storage_calls = [call for call in calls if IDS["storage"] + "?" in call[call.index("--url") + 1]]
    assert len(storage_calls) == 2 and storage_calls[0] == storage_calls[1]
    assert "private detail" not in json.dumps(report) + result.stdout + result.stderr


def test_transient_get_stops_after_three_failed_attempts(tmp_path, state):
    state["cliErrors"] = {"path": IDS["storage"], "attempts": 9, "text": "ERROR: ReadTimeout: private detail"}
    result, report, calls = verify(tmp_path, state)
    assert result.returncode != 0 and not report["passed"]
    assert report["error_code"] == "arm_read_failed:storage"
    assert [event["retry"] for event in report["arm_read_diagnostics"]] == [True, True, False]
    assert report["arm_get_requests"] == len(calls) == 5


@pytest.mark.parametrize("text", [
    "ERROR: (AuthorizationFailed) private detail",
    "ERROR: certificate verify failed; ReadTimeout private detail",
    "ERROR: unrecognized failure private detail",
])
def test_permanent_or_unknown_error_never_retries(tmp_path, state, text):
    state["cliErrors"] = {"path": IDS["storage"], "attempts": 1, "text": text}
    result, report, calls = verify(tmp_path, state)
    assert result.returncode != 0 and not report["passed"]
    assert len(calls) == 3
    assert report["arm_read_diagnostics"] == [
        {"step": "storage", "attempt": 1, "exit_code": 1, "code": "cli_failure", "retry": False}]


def test_native_stderr_warning_does_not_replace_successful_stdout(tmp_path, state):
    state["nativeWarning"] = IDS["storage"]
    result, report, _ = verify(tmp_path, state)
    assert result.returncode == 0 and report["passed"], result.stdout + result.stderr
    assert report["arm_read_diagnostics"] == [
        {"step": "storage", "attempt": 1, "exit_code": 0, "code": "native_stderr_warning", "retry": False}]
    assert "native diagnostic" not in json.dumps(report) + result.stdout + result.stderr


def test_retry_success_does_not_hide_configuration_failure(tmp_path, state):
    state["cliErrors"] = {"path": IDS["storage"], "attempts": 1, "text": "ERROR: ReadTimeout"}
    state["documents"][IDS["storage"]]["properties"]["publicNetworkAccess"] = "Enabled"
    result, report, _ = verify(tmp_path, state)
    assert result.returncode != 0 and not report["passed"]
    assert report["error_code"] == "configuration_checks_failed"
    assert not check(report, "storage_private_tls_zrs")["passed"]
