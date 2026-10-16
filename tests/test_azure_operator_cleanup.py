"""Exercise the real PowerShell cleanup with a function that replaces Azure CLI.

The mock has no fall-through to any executable. Every command is logged, and an
unrecognized command fails. These tests must never contact Azure.
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "remove_azure_operator.ps1"
POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")
pytestmark = pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is required")
SUB = "b31e9bd1-6179-4504-819b-f212ed36f609"
OPERATOR = f"/subscriptions/{SUB}/resourceGroups/rg-ai-command-gateway-operator"
FOUNDATION = f"/subscriptions/{SUB}/resourceGroups/rg-ai-command-gateway-dev"
VNET = f"{OPERATOR}/providers/Microsoft.Network/virtualNetworks/vnet-aicg-operator"
IDENTITY = f"{OPERATOR}/providers/Microsoft.ManagedIdentity/userAssignedIdentities/id-aicg-operator"
PRINCIPAL = "11111111-2222-4333-8444-555555555555"
PEERING = (
    f"{FOUNDATION}/providers/Microsoft.Network/virtualNetworks/"
    "vnet-aicg-sn5edmznrgh7s/virtualNetworkPeerings/to-aicg-operator"
)
ZONES = (
    "privatelink.azurecr.io", "privatelink.blob.core.windows.net",
    "privatelink.monitor.azure.com", "privatelink.oms.opinsights.azure.com",
    "privatelink.ods.opinsights.azure.com", "privatelink.agentsvc.azure-automation.net",
)
LINKS = [
    f"{FOUNDATION}/providers/Microsoft.Network/privateDnsZones/{zone}/"
    "virtualNetworkLinks/link-aicg-operator" for zone in ZONES
]
ROLES = (
    ("Microsoft.ContainerRegistry/registries/craicgsn5edmznrgh7s",
     "df710df2-53f7-5387-a766-6d2dbcd9def4", "8311e382-0749-4cb8-b61a-304f252e45ec"),
    ("Microsoft.Storage/storageAccounts/staicgsn5edmznrgh7s/blobServices/default/containers/inputs",
     "bb1f2a9c-9f8a-5e64-a3fd-04973464d836", "ba92f5b4-2d11-453d-a403-e96b0029c9fe"),
    ("Microsoft.Storage/storageAccounts/staicgsn5edmznrgh7s/blobServices/default/containers/outputs",
     "4d9bc1de-c9aa-5c68-80bf-266e84251f87", "2a2b9908-6ea1-4ae2-8e65-a410df84e7d1"),
    ("Microsoft.OperationalInsights/workspaces/log-aicg-sn5edmznrgh7s",
     "bf72e770-d088-516b-bdc2-f4395324ecef", "73c42c96-874c-492b-b04d-ab87d138a893"),
)
ROLE_IDS = [f"{FOUNDATION}/providers/{scope}/providers/Microsoft.Authorization/roleAssignments/{assignment}"
            for scope, assignment, _ in ROLES]
TARGETS = [PEERING, *LINKS, *ROLE_IDS]


@pytest.fixture
def state():
    resources = {
        IDENTITY: {"id": IDENTITY, "properties": {"principalId": PRINCIPAL}},
        PEERING: {"id": PEERING, "properties": {"remoteVirtualNetwork": {"id": VNET}}},
    }
    resources.update({link: {"id": link, "properties": {"virtualNetwork": {"id": VNET}}}
                      for link in LINKS})
    for rid, (scope, _, role) in zip(ROLE_IDS, ROLES):
        resources[rid] = {"id": rid, "properties": {
            "principalId": PRINCIPAL,
            "scope": f"{FOUNDATION}/providers/{scope}",
            "roleDefinitionId": f"/subscriptions/{SUB}/providers/Microsoft.Authorization/roleDefinitions/{role}",
        }}
    group_ids = [IDENTITY, VNET] + [f"{OPERATOR}/providers/{suffix}" for suffix in (
        "Microsoft.Compute/virtualMachines/vm-aicg-operator",
        "Microsoft.Compute/disks/osdisk-aicg-operator",
        "Microsoft.Network/bastionHosts/bas-aicg-operator",
        "Microsoft.Network/networkInterfaces/nic-aicg-operator",
        "Microsoft.Network/networkSecurityGroups/nsg-aicg-operator",
        "Microsoft.Network/networkSecurityGroups/nsg-aicg-operator-bastion",
        "Microsoft.Network/publicIPAddresses/pip-aicg-operator-bastion",
    )]
    return {
        "group": {"id": OPERATOR, "tags": {
            "purpose": "temporary-private-operator", "workload": "ai-command-gateway"}},
        "inventory": [{"id": rid} for rid in group_ids],
        "resources": resources,
        "failDeleteId": None,
        "groupDeleteFails": False,
        "groupStillExists": False,
        "malformedReadId": None,
        "failedReadId": None,
        "lateUnexpectedResource": None,
    }


MOCK = r"""
$ErrorActionPreference = 'Stop'
$global:fixture = Get-Content -LiteralPath $env:AICG_CLEANUP_FIXTURE -Raw | ConvertFrom-Json
$global:inventoryReads = 0
function global:az {
    $call = @($args | ForEach-Object { [string]$_ })
    ConvertTo-Json -InputObject $call -Compress | Add-Content -LiteralPath $env:AICG_CLEANUP_CALLS -Encoding UTF8
    $global:LASTEXITCODE = 0
    $kind = $call[0] + ' ' + $call[1]
    if ($kind -eq 'group show') { return ($global:fixture.group | ConvertTo-Json -Depth 20 -Compress) }
    if ($kind -eq 'resource list') {
        $global:inventoryReads += 1
        $items = @($global:fixture.inventory)
        if ($global:inventoryReads -gt 1 -and $global:fixture.lateUnexpectedResource) {
            $items += @{ id = $global:fixture.lateUnexpectedResource }
        }
        return (ConvertTo-Json -InputObject $items -Depth 20 -Compress)
    }
    if ($call[0] -eq 'rest') {
        $url = $call[[Array]::IndexOf($call, '--url') + 1]
        $id = ([Uri]$url).AbsolutePath
        if ($global:fixture.failedReadId -eq $id) { $global:LASTEXITCODE = 1; return 'Mock read failed' }
        if ($global:fixture.malformedReadId -eq $id) { return '{broken-json' }
        $property = $global:fixture.resources.PSObject.Properties[$id]
        if ($null -eq $property) { throw "Mock does not recognize resource: $id" }
        return ($property.Value | ConvertTo-Json -Depth 20 -Compress)
    }
    if ($kind -eq 'resource delete') {
        $id = $call[[Array]::IndexOf($call, '--ids') + 1]
        if ($id -eq $global:fixture.failDeleteId) { $global:LASTEXITCODE = 1; return 'Mock delete failed' }
        return
    }
    if ($kind -eq 'group delete') {
        if ($global:fixture.groupDeleteFails) { $global:LASTEXITCODE = 1; return 'Mock group deletion failed' }
        return
    }
    if ($kind -eq 'group exists') {
        if ($global:fixture.groupStillExists) { return 'true' }
        return 'false'
    }
    throw "No real Azure commands allowed. Unrecognized mock command: $kind"
}
if ($env:AICG_CLEANUP_DELETE -eq 'true') {
    & $env:AICG_CLEANUP_SCRIPT -OutputDirectory $env:AICG_CLEANUP_OUTPUT -Delete
} else {
    & $env:AICG_CLEANUP_SCRIPT -OutputDirectory $env:AICG_CLEANUP_OUTPUT
}
"""


def run_cleanup(tmp_path: Path, state, *, delete=True):
    import os

    fixture = tmp_path / "fixture.json"
    fixture.write_text(json.dumps(state), encoding="utf-8")
    harness = tmp_path / "harness.ps1"
    harness.write_text(MOCK, encoding="utf-8-sig")
    calls_path = tmp_path / "calls.jsonl"
    output_dir = tmp_path / "report"
    env = dict(os.environ, AICG_CLEANUP_FIXTURE=str(fixture),
               AICG_CLEANUP_CALLS=str(calls_path), AICG_CLEANUP_SCRIPT=str(SCRIPT),
               AICG_CLEANUP_OUTPUT=str(output_dir), AICG_CLEANUP_DELETE=str(delete).lower())
    result = subprocess.run(
        [POWERSHELL, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(harness)],
        capture_output=True, text=True, env=env, timeout=45,
    )
    calls = [json.loads(line) for line in calls_path.read_text(encoding="utf-8-sig").splitlines()]
    report = json.loads((output_dir / "summary.json").read_text(encoding="utf-8-sig"))
    for call in calls:
        assert call[call.index("--subscription") + 1] == SUB
    return result, calls, report


def mutations(calls):
    return [call for call in calls if call[:2] in (["resource", "delete"], ["group", "delete"])]


def assert_closed(result, calls, report):
    assert result.returncode != 0
    assert report["status"] == "failed"
    assert report["operatorGroupDeleted"] is False
    assert mutations(calls) == []


def test_default_is_read_only(tmp_path, state):
    result, calls, report = run_cleanup(tmp_path, state, delete=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert report["status"] == "reviewed"
    assert report["deleteRequested"] is False
    assert report["checkedFoundationIds"] == TARGETS
    assert report["deletedFoundationIds"] == []
    assert mutations(calls) == []


def test_exact_successful_deletions(tmp_path, state):
    result, calls, report = run_cleanup(tmp_path, state)
    assert result.returncode == 0, result.stdout + result.stderr
    deletes = mutations(calls)
    assert [call[call.index("--ids") + 1] for call in deletes[:-1]] == TARGETS
    assert deletes[-1][:2] == ["group", "delete"]
    assert deletes[-1][deletes[-1].index("--name") + 1] == "rg-ai-command-gateway-operator"
    assert len(deletes) == 12
    assert report["status"] == "deleted"
    assert report["deletedFoundationIds"] == TARGETS
    assert report["operatorGroupDeleted"] is True


@pytest.mark.parametrize("field,value", [
    ("id", FOUNDATION),
    ("purpose", "production"),
    ("workload", "another-project"),
])
def test_wrong_group_identity_or_tags_refused(tmp_path, state, field, value):
    if field == "id":
        state["group"][field] = value
    else:
        state["group"]["tags"][field] = value
    assert_closed(*run_cleanup(tmp_path, state))


def test_unexpected_group_resource_refused(tmp_path, state):
    state["inventory"].append({"id": f"{OPERATOR}/providers/Microsoft.Storage/storageAccounts/unrelated"})
    assert_closed(*run_cleanup(tmp_path, state))


@pytest.mark.parametrize("field,value", [
    ("principalId", "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"),
    ("scope", FOUNDATION),
    ("roleDefinitionId", f"/subscriptions/{SUB}/providers/Microsoft.Authorization/roleDefinitions/owner"),
])
def test_wrong_role_principal_scope_or_definition_refused(tmp_path, state, field, value):
    state["resources"][ROLE_IDS[2]]["properties"][field] = value
    assert_closed(*run_cleanup(tmp_path, state))


@pytest.mark.parametrize("resource,property_name", [(PEERING, "remoteVirtualNetwork"), (LINKS[4], "virtualNetwork")])
def test_wrong_network_target_refused(tmp_path, state, resource, property_name):
    state["resources"][resource]["properties"][property_name]["id"] = f"{FOUNDATION}/providers/Microsoft.Network/virtualNetworks/other"
    assert_closed(*run_cleanup(tmp_path, state))


@pytest.mark.parametrize("failure", ["failedReadId", "malformedReadId"])
def test_failed_or_malformed_json_read_is_closed(tmp_path, state, failure):
    state[failure] = LINKS[2]
    assert_closed(*run_cleanup(tmp_path, state))


def test_partial_child_delete_failure_preserves_evidence_and_group(tmp_path, state):
    state["failDeleteId"] = TARGETS[3]
    result, calls, report = run_cleanup(tmp_path, state)
    assert result.returncode != 0
    deletes = mutations(calls)
    assert [call[call.index("--ids") + 1] for call in deletes] == TARGETS[:4]
    assert report["deletedFoundationIds"] == TARGETS[:3]
    assert report["operatorGroupDeleted"] is False
    assert report["status"] == "failed"


@pytest.mark.parametrize("failure", ["groupDeleteFails", "groupStillExists"])
def test_group_delete_failure_is_not_reported_as_success(tmp_path, state, failure):
    state[failure] = True
    result, calls, report = run_cleanup(tmp_path, state)
    assert result.returncode != 0
    assert len(mutations(calls)) == 12
    assert report["deletedFoundationIds"] == TARGETS
    assert report["operatorGroupDeleted"] is False
    assert report["status"] == "failed"


def test_empty_inventory_is_not_permission_to_delete_group(tmp_path, state):
    state["inventory"] = []
    assert_closed(*run_cleanup(tmp_path, state))


def test_resource_added_during_child_cleanup_prevents_group_delete(tmp_path, state):
    state["lateUnexpectedResource"] = f"{OPERATOR}/providers/Microsoft.Storage/storageAccounts/new-unrelated"
    result, calls, report = run_cleanup(tmp_path, state)
    assert result.returncode != 0
    assert [call[call.index("--ids") + 1] for call in mutations(calls)] == TARGETS
    assert report["operatorGroupDeleted"] is False
    assert report["deletedFoundationIds"] == TARGETS
    assert report["status"] == "failed"
