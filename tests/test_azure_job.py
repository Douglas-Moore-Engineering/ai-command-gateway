"""Azure job contract tests with in-memory Blob doubles and no Azure calls."""

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
from types import SimpleNamespace
import uuid

import pytest

from ai_command_gateway import azure_job


ACCOUNT = "https://example123.blob.core.windows.net"
CLIENT_ID = "11111111-2222-3333-4444-555555555555"


class FakeBlob:
    def __init__(self, service, container, name):
        self.service, self.container, self.name = service, container, name

    def get_blob_properties(self, **kwargs):
        assert self.container == "inputs"
        return SimpleNamespace(size=self.service.sizes.get(self.name, len(self.service.inputs[self.name])))

    def download_blob(self, **kwargs):
        self.service.downloads.append((self.name, kwargs))
        if self.name in self.service.download_failures:
            raise RuntimeError("secret download error")
        payload = self.service.inputs[self.name]
        chunks = self.service.chunks.get(self.name, [payload])
        return SimpleNamespace(chunks=lambda: iter(chunks))

    def upload_blob(self, data, **kwargs):
        assert self.container == "outputs"
        self.service.upload_attempts.append(self.name)
        if self.name.endswith(self.service.fail_suffix) and self.service.fail_suffix:
            raise RuntimeError("secret upload error")
        assert kwargs["overwrite"] is False
        assert self.name not in self.service.uploads
        assert kwargs["length"] == len(data)
        self.service.uploads[self.name] = bytes(data)
        self.service.upload_options[self.name] = kwargs


class FakeBlobService:
    def __init__(self, inputs=None, fail_suffix=""):
        self.inputs = inputs or {}
        self.fail_suffix = fail_suffix
        self.sizes, self.chunks = {}, {}
        self.download_failures = set()
        self.downloads, self.upload_attempts, self.client_requests = [], [], []
        self.uploads, self.upload_options = {}, {}
        self.closed = False

    def get_blob_client(self, container, blob):
        self.client_requests.append((container, blob))
        return FakeBlob(self, container, blob)

    def close(self):
        self.closed = True


@pytest.fixture
def cloud_config(tmp_path):
    return azure_job.JobConfig(account_url=ACCOUNT, client_id=CLIENT_ID, workspace=tmp_path / "work")


@pytest.fixture
def small_sources(monkeypatch):
    originals, _ = azure_job._source_inventory()
    payloads = {item["filename"]: ("fixture-" + item["filename"]).encode() for item in originals}
    sources = []
    for item in originals:
        digest = hashlib.sha256(payloads[item["filename"]]).hexdigest()
        sources.append({**item, "size_bytes": len(payloads[item["filename"]]), "sha256": digest,
                        "source_version": "sha256:" + digest})
    monkeypatch.setattr(azure_job, "_source_inventory", lambda: (sources, "a" * 64))
    return sources, payloads


def completion(service, result):
    return json.loads(service.uploads[f"runs/{result['run_id']}/completion.json"])


@pytest.mark.parametrize("url", [None, "http://example123.blob.core.windows.net", "https://localhost",
                                  "https://example123.blob.core.windows.net//", "https://example123.blob.core.windows.net/path",
                                  "https://example123.blob.core.windows.net?sig=secret", "https://example123.blob.core.windows.net#fragment",
                                  "https://example123.blob.core.windows.net:443", "https://user:secret@example123.blob.core.windows.net",
                                  "https://example123.blob.core.windows.net.evil.example", "https://ab.blob.core.windows.net",
                                  "https://Example123.blob.core.windows.net", "https://foo-bar.blob.core.windows.net"])
def test_only_fixed_public_azure_account_url_shape_is_accepted(tmp_path, url):
    with pytest.raises(azure_job.JobFailure, match="configuration_invalid"):
        azure_job.JobConfig(account_url=url, client_id=CLIENT_ID, workspace=tmp_path)


@pytest.mark.parametrize("suffix", ["", "/"])
def test_azure_primary_endpoint_optional_root_slash_is_normalized(tmp_path, suffix):
    config = azure_job.JobConfig(account_url=ACCOUNT + suffix, client_id=CLIENT_ID, workspace=tmp_path)
    assert config.account_url == ACCOUNT


@pytest.mark.parametrize("field,value", [("input_container", "../inputs"), ("output_container", "inputs"),
                                         ("input_container", "other"), ("output_container", "outputs/path"),
                                         ("mode", "execute"), ("mode", {}), ("client_id", "secret"),
                                         ("client_id", ""), ("client_id", None),
                                         ("workspace", "not-a-Path"), ("workspace", Path("parent/../other"))])
def test_configuration_rejects_unsafe_or_unregistered_values(cloud_config, field, value):
    with pytest.raises(azure_job.JobFailure, match="configuration_invalid"):
        replace(cloud_config, **{field: value})


def test_environment_interface_has_no_secret_or_credential_chain_fields(tmp_path):
    config = azure_job.JobConfig.from_env({
        "AZURE_STORAGE_ACCOUNT_URL": ACCOUNT, "AZURE_CLIENT_ID": CLIENT_ID,
        "AI_GATEWAY_JOB_MODE": "dataset-analysis", "AZURE_INPUT_CONTAINER": "inputs",
        "AZURE_OUTPUT_CONTAINER": "outputs", "AI_GATEWAY_WORKSPACE": str(tmp_path),
        "AZURE_CLIENT_SECRET": "must-not-be-used", "AZURE_STORAGE_CONNECTION_STRING": "must-not-be-used",
    })
    assert config.mode == "dataset-analysis" and config.workspace == tmp_path
    assert "secret" not in repr(config) and "CONNECTION_STRING" not in repr(config)


def test_managed_identity_is_the_only_created_credential(cloud_config, monkeypatch):
    calls = {}
    credential = SimpleNamespace(close=lambda: calls.update(credential_closed=True))
    service = FakeBlobService()
    def identity(**kwargs):
        calls["identity"] = kwargs
        return credential
    def blob(**kwargs):
        calls["blob"] = kwargs
        return service
    monkeypatch.setitem(sys.modules, "azure.identity", SimpleNamespace(ManagedIdentityCredential=identity))
    monkeypatch.setitem(sys.modules, "azure.storage.blob", SimpleNamespace(BlobServiceClient=blob))
    returned_service, returned_credential = azure_job._storage_client(cloud_config)
    assert returned_service is service and returned_credential is credential
    assert calls["identity"] == {"client_id": CLIENT_ID}
    assert calls["blob"]["account_url"] == ACCOUNT
    assert calls["blob"]["credential"] is credential
    assert calls["blob"]["max_single_get_size"] == azure_job.DOWNLOAD_CHUNK_BYTES
    assert not {"account_key", "connection_string", "sas_token"} & calls["blob"].keys()


def test_default_cloud_demo_uploads_only_synthetic_artifacts_and_manifest(cloud_config):
    service = FakeBlobService()
    result = azure_job.run_job(cloud_config, service)
    assert result["status"] == "completed" and result["completion_published"] is True
    assert result["artifact_count"] == 2 and service.downloads == []
    uuid.UUID(result["run_id"])
    names = [name.removeprefix(result["output_prefix"]) for name in service.uploads]
    assert names == [*azure_job.ARTIFACTS["demo"], "completion.json"]
    report = json.loads(service.uploads[result["output_prefix"] + "demo/demo-report.json"])
    assert all(report["checks"].values()) and report["audit_db"] == "demo/audit.sqlite3"
    manifest = completion(service, result)
    assert manifest["status"] == "completed" and manifest["models"]["calls"] == 0
    assert manifest["source_inputs_downloaded_and_verified"] is False
    assert manifest["authority"]["physical_commands_executed"] is False
    assert manifest["raw_dataset_records_uploaded"] is False
    for item in manifest["artifacts"]:
        raw = service.uploads[result["output_prefix"] + item["name"]]
        assert item["sha256"] == hashlib.sha256(raw).hexdigest()
        assert item["size_bytes"] == len(raw)
    serialized = b"".join(data for name, data in service.uploads.items() if name.endswith(".json"))
    assert str(cloud_config.workspace).encode() not in serialized
    assert not service.closed  # Caller owns injected clients.


def test_uploaded_sqlite_backup_is_standalone_and_contains_durable_mock_audit(cloud_config, tmp_path):
    service = FakeBlobService()
    result = azure_job.run_job(cloud_config, service)
    snapshot = tmp_path / "downloaded.sqlite3"
    snapshot.write_bytes(service.uploads[result["output_prefix"] + "demo/audit.sqlite3"])
    with sqlite3.connect(snapshot) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute("SELECT COUNT(*) FROM audit").fetchone()[0] >= 5
        assert connection.execute("SELECT COUNT(*) FROM approvals WHERE consumed_at IS NOT NULL").fetchone()[0] == 1


def test_local_demo_does_not_read_environment_or_construct_azure_client(tmp_path, monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        raise AssertionError("Azure access forbidden in local demo")
    monkeypatch.setattr(azure_job, "_storage_client", forbidden)
    monkeypatch.setattr(azure_job.JobConfig, "from_env", forbidden)
    assert azure_job.main(["--local-output", str(tmp_path)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["storage"] == "local" and result["completion_published"] is False
    assert (tmp_path / result["run_id"] / "completion.json").is_file()


def test_local_dataset_mode_is_not_an_implicit_cloud_or_directory_upload(tmp_path):
    with pytest.raises(azure_job.JobFailure, match="configuration_invalid"):
        azure_job.JobConfig(local_output=tmp_path, mode="dataset-analysis")


def test_dataset_download_requires_exact_names_sizes_and_hashes(cloud_config, small_sources, tmp_path):
    sources, payloads = small_sources
    service = FakeBlobService(payloads)
    config = replace(cloud_config, mode="dataset-analysis")
    target = tmp_path / "downloaded"
    azure_job._download_sources(service, config, target, sources)
    assert set(path.name for path in target.iterdir()) == set(payloads)
    for name, kwargs in service.downloads:
        assert kwargs == {"offset": 0, "length": len(payloads[name]) + 1, "max_concurrency": 1, "timeout": 60}
        assert (target / name).read_bytes() == payloads[name]
    assert all(container == "inputs" for container, _ in service.client_requests)


@pytest.mark.parametrize("failure,expected", [("hash", "input_hash_mismatch"), ("size", "input_size_mismatch"),
                                             ("overflow", "input_size_mismatch"), ("short", "input_size_mismatch"),
                                             ("chunk_type", "input_stream_invalid"), ("empty_chunk", "input_stream_invalid"),
                                             ("large_chunk", "input_stream_invalid"), ("provider", "input_download_failed")])
def test_any_input_failure_prevents_all_analysis_and_raw_uploads(cloud_config, small_sources, monkeypatch, failure, expected):
    sources, payloads = small_sources
    service = FakeBlobService(payloads.copy())
    name = sources[0]["filename"]
    if failure == "hash":
        service.inputs[name] = b"x" * len(payloads[name])
    elif failure == "size":
        service.sizes[name] = len(payloads[name]) + 1
    elif failure == "overflow":
        service.chunks[name] = [payloads[name], b"x"]
    elif failure == "short":
        service.chunks[name] = [payloads[name][:-1]]
    elif failure == "chunk_type":
        service.chunks[name] = ["not bytes"]
    elif failure == "empty_chunk":
        service.chunks[name] = [b""]
    elif failure == "large_chunk":
        service.chunks[name] = [b"x" * (azure_job.DOWNLOAD_CHUNK_BYTES + 1)]
    else:
        service.download_failures.add(name)
    def forbidden(*args):
        raise AssertionError("Analysis must not begin with any unverified input")
    monkeypatch.setattr(azure_job, "_dataset_analysis", forbidden)
    result = azure_job.run_job(replace(cloud_config, mode="dataset-analysis"), service)
    assert result["status"] == "failed" and result["error_code"] == expected
    assert result["artifact_count"] == 0
    assert list(service.uploads) == [result["output_prefix"] + "completion.json"]
    manifest = completion(service, result)
    assert manifest["status"] == "failed" and manifest["source_inputs_downloaded_and_verified"] is False
    assert "secret" not in json.dumps(result) + json.dumps(manifest)


def test_all_five_inputs_verify_before_dataset_workflow_starts(cloud_config, small_sources, monkeypatch):
    sources, payloads = small_sources
    service = FakeBlobService(payloads)
    called = []
    def analysis(run_dir):
        assert len(service.downloads) == 5
        for item in sources:
            assert hashlib.sha256((run_dir / "inputs" / item["filename"]).read_bytes()).hexdigest() == item["sha256"]
        called.append(run_dir)
        for name in azure_job.ARTIFACTS["dataset-analysis"]:
            azure_job._write_json(run_dir / name, {"aggregate": True})
        (run_dir / "inputs" / ".env").write_text("secret")
        azure_job._write_json(run_dir / "work/replay/observations.jsonl", {"raw_record": "secret"})
    monkeypatch.setattr(azure_job, "_dataset_analysis", analysis)
    result = azure_job.run_job(replace(cloud_config, mode="dataset-analysis"), service)
    assert len(called) == 1 and result["status"] == "completed"
    assert result["artifact_count"] == 7
    assert set(name.removeprefix(result["output_prefix"]) for name in service.uploads) == {
        *azure_job.ARTIFACTS["dataset-analysis"], "completion.json"}
    assert completion(service, result)["source_inputs_downloaded_and_verified"] is True
    assert all(b"secret" not in value for value in service.uploads.values())


def test_dataset_workflow_uses_existing_pipeline_and_strips_raw_text_and_absolute_paths(tmp_path, monkeypatch):
    from ai_command_gateway import advice_evaluation, datasets, evidence, qualification, replay
    calls = []
    def profile(inputs, output):
        calls.append("profile")
        value = {"inspection_summary": {"status": "complete"}, "files": [
            {"source_id": "S1", "filename": f"source-{index}", "format": "parquet", "size_bytes": 1,
             "sha256": "a" * 64, "status": "profiled", "profile": {"raw_text": "secret archive README"}}
            for index in range(5)]}
        azure_job._write_json(output / "dataset-profile.json", value)
        return value
    def qualify(inputs, output, inventory):
        calls.append("qualify")
        value = {"inspection_summary": {"status": "complete"}}
        azure_job._write_json(output / "source-qualification.json", value)
        return value
    def catalog(profile_path, inventory, output):
        calls.append("catalog")
        assert profile_path.name == "dataset-profile.json"
        for filename in ("evidence-catalog.json", "evidence-manifest.json", "evidence-profile.json"):
            azure_job._write_json(output / filename, {"aggregate": True})
    def evaluate(catalog_path, cases, output):
        calls.append("evaluate")
        value = {"all_cases_passed": True}
        azure_job._write_json(output / "advice-evaluation.json", value)
        return value
    def historical(inputs, output, policy, database, limit):
        calls.append("replay")
        assert limit == 20 and policy.name == "unqualified-policy.json"
        azure_job._write_json(output / "observations.jsonl", {"raw_record": "secret"})
        return {"qualification_gate_exercised": True, "observations_file": str(output / "observations.jsonl"),
                "audit_db": str(database), "rows_replayed": 20}
    monkeypatch.setattr(datasets, "profile_sources", profile)
    monkeypatch.setattr(qualification, "qualify_sources", qualify)
    monkeypatch.setattr(evidence, "build_catalog", catalog)
    monkeypatch.setattr(advice_evaluation, "evaluate_advice", evaluate)
    monkeypatch.setattr(replay, "replay_process", historical)
    azure_job._dataset_analysis(tmp_path)
    assert calls == ["profile", "qualify", "catalog", "evaluate", "replay"]
    artifacts = azure_job._artifacts(tmp_path, "dataset-analysis")
    for _, raw, _ in artifacts:
        assert b"secret" not in raw and str(tmp_path).encode() not in raw
    assert "observations_file" not in json.loads((tmp_path / "replay/replay-summary.json").read_text())


@pytest.mark.parametrize("suffix", ["demo/demo-report.json", "demo/audit.sqlite3", "completion.json"])
def test_upload_failure_never_leaves_a_successful_completion_manifest(cloud_config, suffix):
    service = FakeBlobService(fail_suffix=suffix)
    result = azure_job.run_job(cloud_config, service)
    assert result["status"] == "failed"
    assert result["error_code"] == ("completion_upload_failed" if suffix == "completion.json" else "artifact_upload_failed")
    if suffix == "completion.json":
        assert result["completion_published"] is False
        assert result["output_prefix"] + "completion.json" not in service.uploads
    else:
        assert completion(service, result)["status"] == "failed"
    local = json.loads((cloud_config.workspace / result["run_id"] / "completion.json").read_text())
    assert local["status"] == "failed"
    assert "secret" not in json.dumps(result) + json.dumps(local)


def test_consecutive_runs_have_distinct_local_directories_and_never_overwrite_blobs(cloud_config):
    service = FakeBlobService()
    first = azure_job.run_job(cloud_config, service)
    second = azure_job.run_job(cloud_config, service)
    assert first["status"] == second["status"] == "completed"
    assert first["run_id"] != second["run_id"]
    assert len(service.uploads) == 6
    assert (cloud_config.workspace / first["run_id"]).is_dir()
    assert (cloud_config.workspace / second["run_id"]).is_dir()
    assert all(options["overwrite"] is False for options in service.upload_options.values())


@pytest.mark.parametrize("name", ["../escape", "/absolute", "C:/absolute", "safe/../../escape", "a\\b", "a//b", "./file"])
def test_path_traversal_is_rejected(tmp_path, name):
    with pytest.raises(azure_job.JobFailure, match="workspace_invalid"):
        azure_job._safe_child(tmp_path, name)


def test_nonallowlisted_artifact_cannot_be_uploaded(cloud_config):
    service = FakeBlobService()
    with pytest.raises(azure_job.JobFailure, match="artifact_invalid"):
        azure_job._upload(service, cloud_config, str(uuid.uuid4()), "inputs/process_dataset.parquet", b"raw")
    assert service.uploads == {}


def test_missing_or_oversize_allowlisted_artifact_prevents_all_uploads(cloud_config, monkeypatch):
    def wrong_demo(run_dir):
        azure_job._write_json(run_dir / "demo/demo-report.json", {"report": True})
    monkeypatch.setattr(azure_job, "_demo", wrong_demo)
    service = FakeBlobService()
    result = azure_job.run_job(cloud_config, service)
    assert result["error_code"] == "artifact_invalid" and result["artifact_count"] == 0
    assert list(service.uploads) == [result["output_prefix"] + "completion.json"]


def test_artifact_byte_cap_is_enforced_before_upload(cloud_config, monkeypatch):
    monkeypatch.setattr(azure_job, "MAX_ARTIFACT_BYTES", 8)
    service = FakeBlobService()
    result = azure_job.run_job(cloud_config, service)
    assert result["error_code"] == "artifact_invalid" and result["artifact_count"] == 0


def test_owned_cloud_client_and_identity_are_closed(cloud_config, monkeypatch):
    service = FakeBlobService()
    identity = SimpleNamespace(closed=False)
    identity.close = lambda: setattr(identity, "closed", True)
    monkeypatch.setattr(azure_job, "_storage_client", lambda config: (service, identity))
    result = azure_job.run_job(cloud_config)
    assert result["status"] == "completed" and service.closed and identity.closed


def test_invalid_environment_main_returns_small_fixed_error(monkeypatch, capsys):
    monkeypatch.delenv("AZURE_STORAGE_ACCOUNT_URL", raising=False)
    monkeypatch.setenv("AZURE_CLIENT_ID", "secret key must not be echoed")
    assert azure_job.main([]) == 1
    assert json.loads(capsys.readouterr().out) == {"status": "failed", "error_code": "configuration_invalid"}


def test_inventory_is_pinned_and_cannot_add_or_change_sources(tmp_path, monkeypatch):
    source_path = azure_job.INVENTORY_PATH
    sources, digest = azure_job._source_inventory()
    assert len(sources) == 5 and len(digest) == 64
    document = json.loads(source_path.read_text())
    document["files"][0]["filename"] = "../outside"
    changed = tmp_path / "inventory.json"
    changed.write_text(json.dumps(document))
    monkeypatch.setattr(azure_job, "INVENTORY_PATH", changed)
    with pytest.raises(azure_job.JobFailure, match="inventory_invalid"):
        azure_job._source_inventory()
