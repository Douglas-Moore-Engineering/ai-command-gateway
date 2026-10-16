"""Offline operator-transfer tests; no Azure calls or real crane execution."""

import hashlib
import importlib.util
import io
import json
from pathlib import Path
import socket
from types import SimpleNamespace
import time
from urllib.parse import parse_qs

import pytest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("azure_operator_transfer", ROOT / "scripts/azure_operator_transfer.py")
operator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(operator)
CLIENT_ID = operator.OPERATOR_CLIENT_ID
RUN_ID = "00000000-0000-4000-8000-000000000002"


class Response:
    def __init__(self, data=b"", status=200, **headers):
        self.data, self.status, self.closed = io.BytesIO(data), status, False
        self.headers = {"Content-Length": str(len(data)), **headers}
        self.requested_read_sizes = []

    def read(self, size):
        assert size > 0  # Unbounded read() is forbidden.
        self.requested_read_sizes.append(size)
        return self.data.read(size)

    def getheader(self, name):
        return self.headers.get(name)

    def close(self):
        self.closed = True


class FakeBlob:
    def __init__(self):
        self.files, self.calls = {}, []

    def request(self, method, container, name, *, body=None, size=None):
        self.calls.append((method, container, name))
        key = container, name
        if method == "PUT":
            assert hasattr(body, "read")  # Upload remains a file stream, not 203 MB bytes.
            if key in self.files:
                return Response(status=412)
            output = bytearray()
            while chunk := body.read(37):
                output.extend(chunk)
            assert len(output) == size
            self.files[key] = bytes(output)
            return Response(status=201)
        if key not in self.files:
            return Response(status=404, **{"x-ms-error-code": "BlobNotFound"})
        return Response(self.files[key] if method == "GET" else b"",
                        **{"Content-Length": str(len(self.files[key]))})


@pytest.fixture
def inputs(tmp_path, monkeypatch):
    directory = tmp_path / "inputs"
    directory.mkdir()
    records = []
    for name in sorted(operator.SOURCE_NAMES):
        raw = (name + "\n").encode() * 30
        (directory / name).write_bytes(raw)
        records.append({"filename": name, "size_bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
    inventory = tmp_path / "inventory.json"
    raw = json.dumps({"files": records}).encode()
    inventory.write_bytes(raw)
    monkeypatch.setattr(operator, "INVENTORY_SHA256", hashlib.sha256(raw).hexdigest())
    return directory, inventory


def test_all_five_inputs_verified_before_any_network_request(inputs):
    directory, inventory = inputs
    (directory / sorted(operator.SOURCE_NAMES)[-1]).write_bytes(b"changed")
    blob = FakeBlob()
    with pytest.raises(operator.TransferFailure):
        operator.upload_inputs(directory, inventory, blob)
    assert blob.calls == []


def test_uploads_are_streamed_read_back_and_existing_files_are_verified(inputs):
    blob = FakeBlob()
    first = operator.upload_inputs(*inputs, blob)
    assert len(first["inputs"]) == 5 and all(item["operation"] == "created" for item in first["inputs"])
    assert all(item["full_readback_verified"] for item in first["inputs"])
    blob.calls.clear()
    second = operator.upload_inputs(*inputs, blob)
    assert all(item["operation"] == "existing_verified" for item in second["inputs"])
    assert not any(call[0] == "PUT" for call in blob.calls)


def test_existing_mismatched_blob_is_never_overwritten(inputs):
    blob = FakeBlob()
    name = sorted(operator.SOURCE_NAMES)[0]
    raw = (inputs[0] / name).read_bytes()
    blob.files["inputs", name] = b"x" * len(raw)
    with pytest.raises(operator.TransferFailure, match="remote_hash_mismatch"):
        operator.upload_inputs(*inputs, blob)
    assert not any(call[0] == "PUT" for call in blob.calls)


def test_blob_put_is_create_only_fixed_scope_and_token_is_not_in_url():
    calls = []

    def request(*args):
        calls.append(args)
        return Response(status=201)

    blob = operator.Blob(SimpleNamespace(token=lambda resource: "fixture-token"), SimpleNamespace(request=request))
    blob.request("PUT", "inputs", "logs_dataset.parquet", body=io.BytesIO(b"x"), size=1)
    method, host, path, headers, body = calls[0]
    assert host == operator.BLOB_HOST and path == "/inputs/logs_dataset.parquet"
    assert headers["If-None-Match"] == "*" and headers["x-ms-blob-type"] == "BlockBlob"
    assert headers["Authorization"] == "Bearer fixture-token" and "fixture-token" not in path
    with pytest.raises(operator.TransferFailure):
        blob.request("PUT", "outputs", "overwrite.json", body=b"x", size=1)
    with pytest.raises(operator.TransferFailure):
        blob.request("DELETE", "inputs", "logs_dataset.parquet")


def test_imds_is_explicit_identity_scoped_and_cached():
    calls = []

    def request(method, host, path, headers):
        calls.append((method, host, path, headers))
        return Response(json.dumps({"access_token": "fixture-access-token", "resource": operator.STORAGE_RESOURCE,
                                    "token_type": "Bearer", "expires_on": str(int(time.time()) + 3600)}).encode())

    identity = operator.Identity(CLIENT_ID, SimpleNamespace(request=request))
    assert identity.token(operator.STORAGE_RESOURCE) == identity.token(operator.STORAGE_RESOURCE) == "fixture-access-token"
    assert len(calls) == 1 and calls[0][1] == "169.254.169.254" and calls[0][3] == {"Metadata": "true"}
    assert parse_qs(calls[0][2].split("?", 1)[1])["client_id"] == [CLIENT_ID]
    with pytest.raises(operator.TransferFailure):
        identity.token("https://untrusted.invalid")
    with pytest.raises(operator.TransferFailure, match="operator_identity_mismatch"):
        operator.Identity(RUN_ID, SimpleNamespace(request=request))


@pytest.mark.parametrize("addresses", [["10.42.2.4", "8.8.8.8"], ["127.0.0.1"], ["::1"], []])
def test_dns_preflight_rejects_public_mixed_or_missing_answers(addresses):
    def resolver(host, port, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, port)) for address in addresses]

    with pytest.raises(operator.TransferFailure):
        operator.preflight(resolver)


def test_transport_rejects_public_peer_before_sending_authorization(monkeypatch):
    calls = []

    class Connection:
        sock = SimpleNamespace(getpeername=lambda: ("20.1.1.1", 443))

        def __init__(self, *args, **kwargs):
            pass

        def connect(self):
            pass

        def request(self, *args, **kwargs):
            calls.append("request")

        def close(self):
            calls.append("closed")

    monkeypatch.setattr(operator.http.client, "HTTPSConnection", Connection)
    with pytest.raises(operator.TransferFailure, match="connection_not_private"):
        operator.Transport().request("GET", operator.BLOB_HOST, "/inputs/file", {"Authorization": "Bearer fixture"})
    assert calls == ["closed"]


@pytest.fixture
def downloadable():
    blob = FakeBlob()
    artifacts = []
    for name in sorted(operator.ARTIFACTS["demo"]):
        raw = b"opaque bytes; never execute"
        blob.files["outputs", f"runs/{RUN_ID}/{name}"] = raw
        artifacts.append({"name": name, "size_bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
    manifest = {"schema_version": "1.0.0", "run_id": RUN_ID, "mode": "demo", "status": "completed",
                "error_code": None, "artifacts": artifacts}
    blob.files["outputs", f"runs/{RUN_ID}/completion.json"] = json.dumps(manifest).encode()
    return blob, manifest


def test_download_requires_fresh_directory_and_preserves_exact_manifest(downloadable, tmp_path):
    blob, manifest = downloadable
    destination = tmp_path / "new-run"
    result = operator.download_run(RUN_ID, "demo", destination, blob)
    assert result["status"] == "passed" and result["semantic_results_verified"] is False
    assert json.loads((destination / "completion.json").read_bytes()) == manifest
    assert {p.relative_to(destination).as_posix() for p in destination.rglob("*") if p.is_file()} == {
        "completion.json", *operator.ARTIFACTS["demo"]}
    with pytest.raises(operator.TransferFailure, match="download_directory_must_be_new"):
        operator.download_run(RUN_ID, "demo", destination, blob)


@pytest.mark.parametrize("mutation", [
    lambda m: m.update(run_id=CLIENT_ID), lambda m: m.update(mode="dataset-analysis"),
    lambda m: m["artifacts"][0].update(name="../outside"),
    lambda m: m["artifacts"].__setitem__(1, m["artifacts"][0]),
    lambda m: m["artifacts"][0].update(size_bytes=operator.MAX_ARTIFACT + 1),
])
def test_untrusted_download_manifest_cannot_expand_scope(downloadable, tmp_path, mutation):
    blob, manifest = downloadable
    mutation(manifest)
    blob.files["outputs", f"runs/{RUN_ID}/completion.json"] = json.dumps(manifest).encode()
    destination = tmp_path / "new-run"
    with pytest.raises(operator.TransferFailure):
        operator.download_run(RUN_ID, "demo", destination, blob)
    assert not destination.exists()


def test_failed_download_never_writes_completion_marker(downloadable, tmp_path):
    blob, manifest = downloadable
    blob.files["outputs", f"runs/{RUN_ID}/" + manifest["artifacts"][0]["name"]] = b"corrupt"
    destination = tmp_path / "new-run"
    with pytest.raises(operator.TransferFailure):
        operator.download_run(RUN_ID, "demo", destination, blob)
    assert not (destination / "completion.json").exists()


def test_publish_uses_stdin_ephemeral_config_and_digest_not_tag(tmp_path, monkeypatch):
    executable = tmp_path / "crane"
    executable.write_bytes(b"fixture binary")
    monkeypatch.setattr(operator, "CRANE_SHA256", operator.hash_file(executable))
    monkeypatch.setattr(operator, "verify_layout", lambda *args: {"fixture": "separately tested"})
    calls, configs = [], []

    def runner(command, **kwargs):
        calls.append((command, kwargs.get("input")))
        configs.append(kwargs["env"]["DOCKER_CONFIG"])
        assert Path(configs[-1]).is_dir()
        assert "fixture-refresh-token" not in " ".join(command)
        output = b"v0.22.1" if command[1] == "version" else operator.PLATFORM_DIGEST.encode() if command[1] == "digest" else b""
        return SimpleNamespace(returncode=0, stdout=output, stderr=b"hidden provider text")

    transport = SimpleNamespace(request=lambda *args: Response(b'{"refresh_token":"fixture-refresh-token"}'))
    identity = SimpleNamespace(token=lambda resource: "fixture-access-token")
    result = operator.publish(tmp_path, executable, tmp_path / "identity.json", identity, transport, runner)
    assert result["registry_digest"] == operator.PLATFORM_DIGEST and result["mutable_tag_written"] is False
    assert calls[1][1] == b"fixture-refresh-token\n"
    assert calls[2][0][-1] == operator.ACR_HOST + "/ai-command-gateway@" + operator.PLATFORM_DIGEST
    assert all(not Path(config).exists() for config in configs)


def test_wrong_tool_hash_prevents_authentication(tmp_path, monkeypatch):
    executable = tmp_path / "crane"
    executable.write_bytes(b"untrusted")
    monkeypatch.setattr(operator, "verify_layout", lambda *args: {})
    with pytest.raises(operator.TransferFailure, match="crane_binary_hash_mismatch"):
        operator.publish(tmp_path, executable, tmp_path / "identity.json", None, None)


def test_crane_error_text_and_tokens_are_not_reported():
    def failed(*args, **kwargs):
        return SimpleNamespace(returncode=1, stdout=b"fixture-secret", stderr=b"fixture-secret")

    with pytest.raises(operator.TransferFailure) as error:
        operator.crane_call(Path("crane"), ["version"], {}, runner=failed)
    assert str(error.value) == "crane_command_failed"


@pytest.fixture
def layout(tmp_path, monkeypatch):
    directory = tmp_path / "oci"
    blobs = directory / "blobs/sha256"
    blobs.mkdir(parents=True)
    descriptors = []
    for raw in (b'{"architecture":"amd64","os":"linux"}', b"compressed layer fixture"):
        checksum = hashlib.sha256(raw).hexdigest()
        (blobs / checksum).write_bytes(raw)
        descriptors.append({"digest": "sha256:" + checksum, "size": len(raw)})
    manifest = {"schemaVersion": 2, "config": descriptors[0], "layers": descriptors[1:]}
    raw = json.dumps(manifest).encode()
    checksum = hashlib.sha256(raw).hexdigest()
    (blobs / checksum).write_bytes(raw)
    platform_digest = "sha256:" + checksum
    monkeypatch.setattr(operator, "PLATFORM_DIGEST", platform_digest)
    (directory / "index.json").write_text(json.dumps({"schemaVersion": 2, "manifests": [
        {"digest": platform_digest, "size": len(raw), "mediaType": "application/vnd.oci.image.manifest.v1+json"}]}))
    (directory / "oci-layout").write_text('{"imageLayoutVersion":"1.0.0"}')
    identity = tmp_path / "image-identity.json"
    identity_raw = json.dumps({"platform_manifest_digest": platform_digest,
                              "configuration_digest": descriptors[0]["digest"],
                              "layers": [{"compressed_digest": descriptors[1]["digest"]}]}).encode()
    identity.write_bytes(identity_raw)
    monkeypatch.setattr(operator, "IMAGE_IDENTITY_SHA256", hashlib.sha256(identity_raw).hexdigest())
    return directory, identity, descriptors[1]


def test_layout_verifies_manifest_config_and_each_layer(layout):
    directory, identity, layer = layout
    assert operator.verify_layout(directory, identity)["layer_count"] == 1
    (directory / "blobs/sha256" / layer["digest"].split(":")[1]).write_bytes(b"x" * layer["size"])
    with pytest.raises(operator.TransferFailure, match="oci_blob_hash_mismatch"):
        operator.verify_layout(directory, identity)


def test_changed_image_identity_is_not_a_new_approval(layout):
    directory, identity, _ = layout
    with identity.open("ab") as handle:
        handle.write(b"\n")
    with pytest.raises(operator.TransferFailure, match="image_identity_hash_mismatch"):
        operator.verify_layout(directory, identity)


def test_crane_registry_digest_must_match_reviewed_image(tmp_path, monkeypatch):
    executable = tmp_path / "crane"
    executable.write_bytes(b"fixture binary")
    monkeypatch.setattr(operator, "CRANE_SHA256", operator.hash_file(executable))
    monkeypatch.setattr(operator, "verify_layout", lambda *args: {})

    def runner(command, **kwargs):
        output = b"v0.22.1" if command[1] == "version" else b"sha256:" + b"0" * 64
        return SimpleNamespace(returncode=0, stdout=output, stderr=b"")

    transport = SimpleNamespace(request=lambda *args: Response(b'{"refresh_token":"fixture-token"}'))
    with pytest.raises(operator.TransferFailure, match="published_digest_mismatch"):
        operator.publish(tmp_path, executable, tmp_path / "identity.json",
                         SimpleNamespace(token=lambda _: "fixture-token"), transport, runner)


EXECUTION = "job-aicg-sn5edmznrgh7s-abc1234"


def log_response(rows=None):
    return {"tables": [{"name": "PrimaryResult", "columns": [
        {"name": name, "type": "datetime" if name == "TimeGenerated" else "string"} for name in operator.LOG_COLUMNS],
        "rows": rows if rows is not None else [["2026-10-16T03:00:00Z", "ContainerAppConsoleLogs",
                    EXECUTION + "-replica1", "", EXECUTION, "stdout", '{"status":"completed"}']]}]}


def test_log_query_uses_fixed_tables_execution_filter_and_audience():
    calls, audiences = [], []
    document = log_response()

    def request(method, host, path, headers, body):
        calls.append((method, host, path, headers, json.loads(body)))
        return Response(json.dumps(document).encode())

    identity = SimpleNamespace(token=lambda resource: audiences.append(resource) or "fixture-token")
    result = operator.query_logs(RUN_ID, EXECUTION, identity, SimpleNamespace(request=request))
    assert audiences == ["https://api.loganalytics.io"]
    assert calls[0][:3] == ("POST", "api.loganalytics.io", f"/v1/workspaces/{RUN_ID}/query")
    query = calls[0][4]["query"]
    assert "union isfuzzy=true withsource=SourceTable ContainerAppConsoleLogs, ContainerAppConsoleLogs_CL" in query
    assert "ContainerGroupName_s" in query and "ContainerGroupName_g" in query and "ReplicaName" in query
    assert 'startswith strcat(execution, "-")' in query and "ago(24h)" in query and "take 2000" in query
    assert result["row_count"] == 1 and result["execution_logs_present"] is True
    assert result["arm_execution_success_verified"] is False and result["result"] == document
    assert "fixture-token" not in json.dumps(result)


@pytest.mark.parametrize("table", operator.LOG_TABLES)
def test_explicit_log_table_uses_only_selected_table_and_preserves_bounds(table):
    document = log_response()
    document["tables"][0]["rows"][0][1] = table
    queries = []

    def request(method, host, path, headers, body):
        queries.append(json.loads(body))
        return Response(json.dumps(document).encode())

    result = operator.query_logs(RUN_ID, EXECUTION, SimpleNamespace(token=lambda _: "fixture-token"),
                                 SimpleNamespace(request=request), table=table)
    query = queries[0]["query"]
    assert query.splitlines()[1:3] == [table, f'| extend SourceTable = "{table}"']
    assert "union " not in query and "isfuzzy" not in query
    assert 'startswith strcat(execution, "-")' in query and "ago(24h)" in query and "take 2000" in query
    assert "| project TimeGenerated, SourceTable, ContainerGroupName, ReplicaName, JobName," in query
    assert queries[0]["timespan"] == "P1D" and result["table"] == table and result["row_count"] == 1


@pytest.mark.parametrize("table", ["AzureActivity", "ContainerAppConsoleLogs\n| take 1", "ContainerAppConsoleLogs; search *"])
def test_illegal_log_table_is_rejected_before_token_or_query(table):
    with pytest.raises(operator.TransferFailure, match="log_table_invalid"):
        operator.query_logs(RUN_ID, EXECUTION, None, None, table=table)


def test_explicit_log_table_rejects_a_result_from_another_table():
    with pytest.raises(operator.TransferFailure, match="log_table_binding_mismatch"):
        operator.query_logs(RUN_ID, EXECUTION, SimpleNamespace(token=lambda _: "fixture-token"),
                            SimpleNamespace(request=lambda *args: Response(json.dumps(log_response()).encode())),
                            table="ContainerAppConsoleLogs_CL")


@pytest.mark.parametrize("name", ["other-job-abc", "job-aicg-sn5edmznrgh7s-", EXECUTION + "-another",
                                  EXECUTION + '"; search *', EXECUTION + "\n", "job-aicg-sn5edmznrgh7s-" + "a" * 33])
def test_invalid_execution_name_is_rejected_before_token_or_query(name):
    with pytest.raises(operator.TransferFailure, match="execution_name_invalid"):
        operator.query_logs(RUN_ID, name, None, None)


@pytest.mark.parametrize("workspace", ["../outside", RUN_ID.upper().replace("0", "A", 1), RUN_ID + "?query=all"])
def test_workspace_id_must_be_a_canonical_uuid(workspace):
    with pytest.raises((operator.TransferFailure, ValueError)):
        operator.query_logs(workspace, EXECUTION, None, None)


def test_only_the_requested_log_token_resource_is_supported():
    calls = []

    def request(method, host, path, headers):
        calls.append(path)
        return Response(json.dumps({"access_token": "fixture-token", "resource": operator.LOG_RESOURCE,
                                    "token_type": "Bearer", "expires_on": str(int(time.time()) + 3600)}).encode())

    identity = operator.Identity(CLIENT_ID, SimpleNamespace(request=request))
    assert identity.token(operator.LOG_RESOURCE) == "fixture-token"
    assert parse_qs(calls[0].split("?", 1)[1])["resource"] == ["https://api.loganalytics.io"]
    for resource in ("https://api.loganalytics.azure.com", "https://api.loganalytics.io/", "https://graph.microsoft.com"):
        with pytest.raises(operator.TransferFailure, match="resource_not_allowed"):
            identity.token(resource)
    assert len(calls) == 1


def test_log_response_is_bounded_and_closed(monkeypatch):
    assert operator.MAX_LOG_RESPONSE == 16 * 1024 * 1024
    monkeypatch.setattr(operator, "MAX_LOG_RESPONSE", 32)
    response = Response(b"x" * 33)
    with pytest.raises(operator.TransferFailure, match="response_size_limit"):
        operator.query_logs(RUN_ID, EXECUTION, SimpleNamespace(token=lambda _: "fixture-token"),
                            SimpleNamespace(request=lambda *args: response))
    assert response.requested_read_sizes == [33] and response.closed


@pytest.mark.parametrize("table", [None, *operator.LOG_TABLES])
def test_log_error_bodies_and_partial_results_never_escape(table):
    identity = SimpleNamespace(token=lambda _: "fixture-token")
    failed_response = Response(b"sensitive provider error", status=403)
    with pytest.raises(operator.TransferFailure) as error:
        operator.query_logs(RUN_ID, EXECUTION, identity, SimpleNamespace(request=lambda *args: failed_response), table=table)
    assert str(error.value) == "http_request_failed" and failed_response.requested_read_sizes == []
    partial = {**log_response(), "error": {"code": "PartialError", "message": "sensitive provider error"}}
    with pytest.raises(operator.TransferFailure, match="log_query_result_invalid_or_partial"):
        operator.query_logs(RUN_ID, EXECUTION, identity,
                            SimpleNamespace(request=lambda *args: Response(json.dumps(partial).encode())), table=table)


def test_query_results_must_remain_bound_to_requested_execution():
    document = log_response()
    document["tables"][0]["rows"][0][2:5] = ["other-execution", "", ""]
    with pytest.raises(operator.TransferFailure, match="log_execution_binding_mismatch"):
        operator.query_logs(RUN_ID, EXECUTION, SimpleNamespace(token=lambda _: "fixture-token"),
                            SimpleNamespace(request=lambda *args: Response(json.dumps(document).encode())))


def test_no_rows_reports_query_success_without_log_presence():
    result = operator.query_logs(RUN_ID, EXECUTION, SimpleNamespace(token=lambda _: "fixture-token"),
                                SimpleNamespace(request=lambda *args: Response(json.dumps(log_response([])).encode())))
    assert result["status"] == "passed" and result["row_count"] == 0 and result["execution_logs_present"] is False
