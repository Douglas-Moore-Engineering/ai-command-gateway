"""Downloaded artifacts remain untrusted even when a manifest says completed."""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import uuid

import pytest

from ai_command_gateway import azure_job
from ai_command_gateway.advice_evaluation import evaluate_advice
from ai_command_gateway.evidence import build_catalog


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("verify_azure_outputs", ROOT / "scripts/verify_azure_outputs.py")
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


class DownloadedBlobs:
    """Only published bytes reach the verifier; runner work files are excluded."""

    def __init__(self, destination):
        self.destination = destination

    def get_blob_client(self, *, container, blob):
        assert container == "outputs"
        path = self.destination / blob

        class Blob:
            def upload_blob(self, *, data, **kwargs):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)

        return Blob()


@pytest.fixture
def demo(tmp_path):
    service = DownloadedBlobs(tmp_path / "downloaded")
    result = azure_job.run_job(azure_job.JobConfig(
        account_url="https://testdownloads.blob.core.windows.net",
        client_id="00000000-0000-0000-0000-000000000001", workspace=tmp_path / "work"), service)
    assert result["status"] == "completed"
    return service.destination / "runs" / result["run_id"], result["run_id"]


def check(bundle, mode="demo"):
    directory, run_id = bundle
    return verifier.verify(directory, expected_mode=mode, expected_run_id=run_id)


def edit_manifest(directory, mutation):
    path = directory / "completion.json"
    value = json.loads(path.read_bytes())
    mutation(value)
    path.write_text(json.dumps(value), encoding="utf-8")


def edit_artifact(directory, name, mutation):
    path = directory / name
    value = json.loads(path.read_bytes())
    mutation(value)
    raw = json.dumps(value).encode()
    path.write_bytes(raw)

    def rehash(manifest):
        item = next(item for item in manifest["artifacts"] if item["name"] == name)
        item.update(size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())

    edit_manifest(directory, rehash)


def test_actual_demo_published_bytes_pass_without_opening_sqlite(demo, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Downloaded SQLite must not be opened")

    monkeypatch.setattr(azure_job.sqlite3, "connect", forbidden)
    result = check(demo)
    assert result["all_checks_passed"] is True
    assert len(result["artifact_evidence"]) == 3
    assert result["azure_provenance_verified"] is False
    assert result["arm_execution_success_verified"] is False
    assert result["sqlite_contents_evaluated"] is False
    assert result["source_sha256"]["src/ai_command_gateway/azure_job.py"]


@pytest.mark.parametrize("damage", ["missing_completion", "missing_artifact", "extra_raw_file", "tampered_bytes"])
def test_incomplete_or_altered_downloads_fail(demo, damage):
    directory, _ = demo
    if damage == "missing_completion":
        (directory / "completion.json").unlink()
    elif damage == "missing_artifact":
        (directory / "demo/audit.sqlite3").unlink()
    elif damage == "extra_raw_file":
        (directory / "unexpected.parquet").write_bytes(b"raw")
    else:
        with (directory / "demo/audit.sqlite3").open("ab") as output:
            output.write(b"changed")
    assert check(demo)["all_checks_passed"] is False


@pytest.mark.parametrize("mutation", [
    lambda m: m.update(mode="dataset-analysis"),
    lambda m: m.update(run_id=str(uuid.uuid4())),
    lambda m: m.update(status="failed", error_code="artifact_upload_failed"),
    lambda m: m.update(runner_sha256="0" * 64),
    lambda m: m["artifacts"][0].update(name="../outside.json"),
    lambda m: m["artifacts"].__setitem__(1, m["artifacts"][0]),
    lambda m: m["sources"][0].update(sha256="0" * 64),
    lambda m: m["models"].update(calls=False),
    lambda m: m["authority"].update(physical_commands_executed=True),
])
def test_manifest_cannot_rebind_or_expand_trust(demo, mutation):
    edit_manifest(demo[0], mutation)
    assert check(demo)["all_checks_passed"] is False


def test_rehashing_bad_demo_does_not_make_it_pass(demo):
    edit_artifact(demo[0], "demo/demo-report.json", lambda value: value["execution"].update(decision="block"))
    result = check(demo)
    assert result["all_checks_passed"] is False and result["error_code"] == "demo_result_mismatch"


@pytest.mark.parametrize("raw", [b'{"status":"failed","status":"completed"}', b'{"value":NaN}',
                                  b'{"value":1e999}', b'{"value":' + b'[' * 40 + b'0' + b']' * 40 + b'}'])
def test_ambiguous_or_unbounded_json_fails(demo, raw):
    (demo[0] / "completion.json").write_bytes(raw)
    assert check(demo)["all_checks_passed"] is False


def test_manifest_limit_is_checked_before_json_parsing(demo):
    (demo[0] / "completion.json").write_bytes(b" " * (verifier.MAX_MANIFEST_BYTES + 1))
    assert check(demo)["error_code"] == "artifact_size_invalid"


def test_symlink_is_not_followed(demo, tmp_path):
    artifact = demo[0] / "demo/audit.sqlite3"
    outside = tmp_path / "outside.sqlite3"
    artifact.replace(outside)
    try:
        artifact.symlink_to(outside)
    except OSError:
        pytest.skip("Platform does not permit unprivileged symlinks")
    assert check(demo)["error_code"] == "linked_path_rejected"


def test_hardlink_to_another_location_is_rejected(demo, tmp_path):
    artifact = demo[0] / "demo/audit.sqlite3"
    os.link(artifact, tmp_path / "outside.sqlite3")
    assert check(demo)["error_code"] == "linked_path_rejected"


def test_wrong_expected_mode_and_invalid_run_id_fail(demo):
    assert check(demo, "dataset-analysis")["all_checks_passed"] is False
    assert verifier.verify(demo[0], expected_mode="demo", expected_run_id="../escape")["all_checks_passed"] is False


def test_cli_exit_status_reports_invalid_download(demo, capsys):
    (demo[0] / "completion.json").unlink()
    code = verifier.main(["--run-dir", str(demo[0]), "--expected-mode", "demo", "--expected-run-id", demo[1]])
    assert code == 1 and json.loads(capsys.readouterr().out)["all_checks_passed"] is False


@pytest.fixture
def dataset(demo, tmp_path):
    """Small typed fixture; catalog and advice reports use their real producers."""
    run_id = str(uuid.uuid4())
    directory = tmp_path / "dataset" / run_id
    manifest = json.loads((demo[0] / "completion.json").read_bytes())
    manifest.update(mode="dataset-analysis", run_id=run_id, source_inputs_downloaded_and_verified=True)
    profile_path = ROOT / "tests/fixtures/evidence-source-profile.json"
    inventory = ROOT / "data/lineage/source-inventory.json"
    build_catalog(profile_path, inventory, directory / "advice")
    evaluate_advice(directory / "advice/evidence-catalog.json", ROOT / "data/evaluation/advice-cases-v1.json",
                    directory / "advice-evaluation")
    source_profile = json.loads(profile_path.read_bytes())
    files = [{key: item[key] for key in ("filename", "format", "source_id", "size_bytes", "sha256", "status")}
             for item in source_profile["files"]]
    documents = {
        "profiles/profile-summary.json": {
            "files": files, "raw_records_included": False, "archive_text_included": False,
            "qualification_status": "unresolved", "inspection_summary": {"status": "complete",
                "expected_file_count": 5, "profiled_file_count": 5, "fully_inspected_file_count": 5}},
        "qualification/source-qualification.json": {
            "inventory": {"status": "loaded", "sha256": manifest["source_inventory_sha256"]},
            "inspection_summary": {"status": "complete", "matched_file_count": 5, "analyzed_parquet_count": 3},
            "qualification": {"status": "unresolved", "raw_rows_included": False,
                              "physical_limits_learned": False, "physical_validity_labels_available": False},
            "files": [{"filename": item["filename"], "source_id": item["source_id"], "format": item["format"],
                       "identity": {"matches": True, "expected_sha256": item["sha256"], "observed_sha256": item["sha256"],
                                    "expected_size_bytes": item["size_bytes"], "observed_size_bytes": item["size_bytes"]}}
                      for item in files]},
        "replay/replay-summary.json": {
            "rows_replayed": 20, "decisions": {"escalate": 20}, "reason_counts": {"policy_unqualified": 20},
            "durable_qualification_events": 20, "qualification_gate_exercised": True, "raw_rows_included": False,
            "physical_command_validity_evaluated": False, "ground_truth_used": False, "source_id": "S1",
            "source_file": "process_dataset.parquet", "total_source_rows": 13912,
            "sha256": next(item["sha256"] for item in files if item["filename"] == "process_dataset.parquet")},
    }
    for name, document in documents.items():
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(document), encoding="utf-8")
    manifest["artifacts"] = []
    for name in azure_job.ARTIFACTS["dataset-analysis"]:
        raw = (directory / name).read_bytes()
        manifest["artifacts"].append({"name": name, "size_bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
    (directory / "completion.json").write_text(json.dumps(manifest), encoding="utf-8")
    return directory, run_id


def test_real_catalog_and_evaluation_producers_are_compatible(dataset):
    assert check(dataset, "dataset-analysis")["all_checks_passed"] is True


@pytest.mark.parametrize("name,mutation,code", [
    ("qualification/source-qualification.json", lambda d: d["files"][0]["identity"].update(observed_sha256="0" * 64),
     "qualification_source_identity_mismatch"),
    ("advice-evaluation/advice-evaluation.json", lambda d: d["cases"][0]["response"].update(can_execute=True),
     "evaluation_failed"),
    ("replay/replay-summary.json", lambda d: d.update(decisions={"allow": 20}), "replay_failed"),
])
def test_rehashed_dataset_results_do_not_override_expected_behavior(dataset, name, mutation, code):
    edit_artifact(dataset[0], name, mutation)
    result = check(dataset, "dataset-analysis")
    assert result["all_checks_passed"] is False and result["error_code"] == code
