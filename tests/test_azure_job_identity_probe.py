"""The permission probe must distinguish RBAC denial from infrastructure failure."""

from enum import Enum
import hashlib
import importlib.util
import json
from pathlib import Path
import socket
from types import SimpleNamespace
import uuid

from azure.core.exceptions import HttpResponseError
import pytest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("probe_azure_job_identity", ROOT / "scripts/probe_azure_job_identity.py")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)
PROBE_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")


def provider_error(status=403, code="AuthorizationPermissionMismatch"):
    error = HttpResponseError("sensitive-provider-message-must-not-appear")
    error.status_code, error.error_code = status, code
    return error


def private_dns(hostname, port, **kwargs):
    assert hostname in {probe.BLOB_HOST, probe.REGISTRY_HOST} and port == 443
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.42.2.4", port))]


class FakeStorage:
    def __init__(self):
        self.input_error = provider_error()
        self.inputs = {name: size for name, (_, _, size, _) in probe.PINNED_SOURCES.items()}
        self.outputs, self.uploads, self.reads = {}, [], []
        self.input_read_error, self.report_error = None, None
        self.oversize_read = False
        self.closed = False

    def close(self):
        self.closed = True

    def get_blob_client(self, *, container, blob):
        assert container in {"inputs", "outputs"}
        owner = self

        class Blob:
            def get_blob_properties(self, **kwargs):
                if owner.input_read_error:
                    raise owner.input_read_error
                return SimpleNamespace(size=owner.inputs[blob])

            def download_blob(self, *, offset, length, max_concurrency, timeout):
                assert offset == 0 and max_concurrency == 1 and timeout == 15
                owner.reads.append((container, blob, length))
                data = b"x" if container == "inputs" else owner.outputs[blob]
                if owner.oversize_read:
                    data = b"too many bytes"
                return SimpleNamespace(chunks=lambda: iter([data]))

            def upload_blob(self, *, data, overwrite, length, max_concurrency, timeout):
                assert overwrite is False and length == len(data) and max_concurrency == 1 and timeout == 15
                owner.uploads.append((container, blob, data))
                if container == "inputs" and owner.input_error:
                    raise owner.input_error
                if blob.endswith("identity-probe.json") and owner.report_error:
                    raise owner.report_error
                if container == "outputs":
                    owner.outputs[blob] = data

        return Blob()


def run(storage, **kwargs):
    return probe.run_probe(service=storage, resolver=private_dns, uuid_factory=lambda: PROBE_ID, **kwargs)


def test_expected_permissions_and_private_dns_produce_persisted_report():
    storage = FakeStorage()
    result = run(storage)
    assert result["status"] == "passed" and result["report_published"] is True
    report = result["report"]
    assert len(report["checks"]) == 9 and all(check["passed"] for check in report["checks"])
    inputs = [read for read in storage.reads if read[0] == "inputs"]
    assert {read[1] for read in inputs} == set(probe.PINNED_SOURCES) and all(read[2] == 1 for read in inputs)
    assert len(storage.outputs) == 2
    raw = storage.outputs[f"validation/{PROBE_ID}/identity-probe.json"]
    assert hashlib.sha256(raw).hexdigest() == result["report_sha256"]
    assert json.loads(raw) == report
    assert "sensitive-provider-message" not in json.dumps(result)
    assert report["full_source_hashes_verified"] is False
    assert report["registry_data_plane_authenticated"] is False
    assert report["unexpected_input_blob_created"] is None


@pytest.mark.parametrize("error", [provider_error(401), provider_error(404, "BlobNotFound"),
                                    provider_error(403, "AuthorizationFailure"),
                                    provider_error(403, "secret-provider-code"),
                                    OSError("sensitive-network-message-must-not-appear")])
def test_nonpermission_failures_cannot_count_as_successful_denial(error):
    storage = FakeStorage()
    storage.input_error = error
    result = run(storage)
    assert result["status"] == "failed" and result["report_published"] is True
    denial = next(check for check in result["report"]["checks"] if check["name"] == "input_create_denied_by_permission")
    assert denial["passed"] is False and denial["error_code"] == "input_write_denial_not_proven"
    serialized = json.dumps(result)
    assert "sensitive-" not in serialized and "secret-provider-code" not in serialized


def test_real_sdk_enum_error_code_is_accepted():
    class Code(str, Enum):
        denied = "AuthorizationPermissionMismatch"

    storage = FakeStorage()
    storage.input_error = provider_error(403, Code.denied)
    assert run(storage)["status"] == "passed"


def test_unexpected_input_creation_records_exact_cleanup_target_without_deleting():
    storage = FakeStorage()
    storage.input_error = None
    result = run(storage)
    assert result["status"] == "failed"
    assert result["report"]["unexpected_input_blob_created"] == f"validation-probe-{PROBE_ID}.txt"
    assert result["report"]["deletions_performed"] is False
    assert [name for container, name, _ in storage.uploads if container == "inputs"] == [f"validation-probe-{PROBE_ID}.txt"]


@pytest.mark.parametrize("addresses", [["20.42.2.4"], ["10.42.2.4", "20.42.2.4"], ["127.0.0.1"], ["::1"], []])
def test_any_nonprivate_or_empty_dns_prevents_all_storage_calls(addresses):
    storage = FakeStorage()

    def resolver(hostname, port, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, port)) for address in addresses]

    result = probe.run_probe(service=storage, resolver=resolver, uuid_factory=lambda: PROBE_ID)
    assert result["status"] == "failed" and result["report_published"] is False
    assert storage.reads == [] and storage.uploads == []


@pytest.mark.parametrize("damage", ["wrong_size", "missing_input", "oversize_range"])
def test_inputs_must_exist_with_exact_size_and_one_byte_read(damage):
    storage = FakeStorage()
    if damage == "wrong_size":
        storage.inputs["logs_dataset.parquet"] += 1
    elif damage == "missing_input":
        storage.input_read_error = provider_error(404, "BlobNotFound")
    else:
        storage.oversize_read = True
    result = run(storage)
    assert result["status"] == "failed" and result["report_published"] is True
    assert any(not check["passed"] for check in result["report"]["checks"]
               if check["name"] == "input_metadata_and_one_byte_read")


def test_report_upload_failure_does_not_claim_success():
    storage = FakeStorage()
    storage.report_error = provider_error(403)
    result = run(storage)
    assert result["report"]["all_probe_checks_passed"] is True
    assert result["status"] == "failed" and result["report_published"] is False
    assert result["report_publish_error"]["error_code"] == "report_upload_failed"


def test_owned_managed_identity_clients_are_closed():
    storage = FakeStorage()
    identity = SimpleNamespace(closed=False)
    identity.close = lambda: setattr(identity, "closed", True)
    result = probe.run_probe(resolver=private_dns, uuid_factory=lambda: PROBE_ID,
                            client_factory=lambda: (storage, identity))
    assert result["status"] == "passed" and storage.closed and identity.closed


def test_production_factory_has_only_the_fixed_managed_identity_and_endpoint(monkeypatch):
    import azure.identity
    import azure.storage.blob

    calls = {}
    identity = SimpleNamespace(close=lambda: None)
    storage = FakeStorage()

    def credential(**kwargs):
        calls["identity"] = kwargs
        return identity

    def client(**kwargs):
        calls["blob"] = kwargs
        return storage

    monkeypatch.setattr(azure.identity, "ManagedIdentityCredential", credential)
    monkeypatch.setattr(azure.storage.blob, "BlobServiceClient", client)
    assert probe._client() == (storage, identity)
    assert calls["identity"] == {"client_id": probe.CLIENT_ID}
    assert calls["blob"]["account_url"] == probe.ACCOUNT_URL and calls["blob"]["credential"] is identity
    assert calls["blob"]["retry_total"] == 0 and calls["blob"]["logging_enable"] is False


def test_cli_never_prints_unexpected_provider_exception(monkeypatch, capsys):
    def failed():
        raise RuntimeError("sensitive-provider-message-must-not-appear")

    monkeypatch.setattr(probe, "run_probe", failed)
    assert probe.main([]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result == {"status": "failed", "report_published": False, "error_code": "probe_internal_failure"}


def test_cli_cannot_redirect_the_fixed_target():
    with pytest.raises(SystemExit) as result:
        probe.main(["--account-url", "https://example.invalid"])
    assert result.value.code == 2
