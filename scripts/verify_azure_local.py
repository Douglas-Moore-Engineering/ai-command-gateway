"""Exercise the real dataset job using local files in place of Azure Blob.

This is local Blob simulation evidence, not Azure service validation. The five
source files are read from --input-dir. The production runner downloads them
through this filesystem double, executes its actual analysis pipeline, and
publishes only allowlisted artifacts into a separate simulated Blob directory.
SDK imports and socket operations are blocked during the run.
"""

from __future__ import annotations

import argparse
import builtins
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path, PurePosixPath
import platform
import re
import socket
import sys
import time
from types import SimpleNamespace
from unittest.mock import patch

from ai_command_gateway import __version__
from ai_command_gateway import azure_job


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_ARTIFACTS = (
    "profiles/profile-summary.json", "qualification/source-qualification.json",
    "advice/evidence-catalog.json", "advice/evidence-manifest.json",
    "advice/evidence-profile.json", "advice-evaluation/advice-evaluation.json",
    "replay/replay-summary.json",
)


class LocalDownloader:
    def __init__(self, path: Path, length: int, record: dict):
        self.path, self.length, self.record = path, length, record

    def chunks(self):
        remaining = self.length
        digest = hashlib.sha256()
        with self.path.open("rb") as source:
            while remaining:
                block = source.read(min(1024 * 1024, remaining))
                if not block:
                    break
                remaining -= len(block)
                self.record["bytes_streamed"] += len(block)
                digest.update(block)
                yield block
        self.record["sha256"] = digest.hexdigest()


class LocalBlob:
    def __init__(self, service: "FilesystemBlobSimulation", container: str, name: str):
        self.service, self.container, self.name = service, container, name

    def get_blob_properties(self, **kwargs):
        if self.container != "inputs":
            raise RuntimeError("Simulation supports properties only for fixed inputs")
        return SimpleNamespace(size=(self.service.input_dir / self.name).stat().st_size)

    def download_blob(self, *, offset: int, length: int, max_concurrency: int, timeout: int):
        if self.container != "inputs" or offset != 0 or max_concurrency != 1:
            raise RuntimeError("Unexpected download request")
        expected = self.service.sources[self.name]
        if length != expected["size_bytes"] + 1:
            raise RuntimeError("Production download byte cap changed")
        record = {"filename": self.name, "requested_length": length,
                  "bytes_streamed": 0, "sha256": None}
        self.service.downloads.append(record)
        print(f"Local input stream: {self.name}", flush=True)
        return LocalDownloader(self.service.input_dir / self.name, length, record)

    def upload_blob(self, *, data: bytes, overwrite: bool, length: int,
                    max_concurrency: int, timeout: int):
        if (self.container != "outputs" or overwrite is not False or type(data) is not bytes
                or length != len(data) or max_concurrency != 1):
            raise RuntimeError("Unexpected simulated upload request")
        path = self.service.blob_root.joinpath(*PurePosixPath(self.name).parts)
        if not path.resolve().is_relative_to(self.service.blob_root.resolve()):
            raise RuntimeError("Simulated upload path escapes output root")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as output:
            output.write(data)
        self.service.uploads.append({
            "blob_name": self.name, "size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
            "overwrite": False, "sequence": len(self.service.uploads) + 1,
        })
        print(f"Local simulated upload: {self.name.split('/', 2)[-1]}", flush=True)


class FilesystemBlobSimulation:
    """Implement only the Blob methods used by run_job, with no SDK imports."""

    def __init__(self, input_dir: Path, blob_root: Path, sources: list[dict]):
        self.input_dir, self.blob_root = input_dir, blob_root
        self.sources = {item["filename"]: item for item in sources}
        self.downloads: list[dict] = []
        self.uploads: list[dict] = []

    def get_blob_client(self, *, container: str, blob: str):
        if container == "inputs":
            if blob not in self.sources:
                raise RuntimeError("Simulation rejects unregistered input names")
        elif container == "outputs":
            match = re.fullmatch(r"runs/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/(.+)", blob)
            if match is None or match[2] not in (*EXPECTED_ARTIFACTS, "completion.json"):
                raise RuntimeError("Simulation rejects unregistered output names")
        else:
            raise RuntimeError("Simulation rejects unregistered containers")
        return LocalBlob(self, container, blob)


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _source_hashes() -> dict:
    paths = [Path(__file__), ROOT / "pyproject.toml", ROOT / "requirements-runtime.lock",
             ROOT / "requirements-azure.lock", ROOT / "data/lineage/source-inventory.json",
             ROOT / "data/evaluation/advice-cases-v1.json"]
    paths.extend((ROOT / "src/ai_command_gateway").glob("*.py"))
    paths.extend((ROOT / "config/policies").glob("*.json"))
    return {path.relative_to(ROOT).as_posix(): _file_hash(path) for path in sorted(set(paths))}


def _strings(value):
    if isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)
    elif isinstance(value, str):
        yield value


def verify(input_dir: Path, destination: Path) -> dict:
    sources, inventory_sha = azure_job._source_inventory()
    before = _source_hashes()
    started = time.perf_counter()
    service = FilesystemBlobSimulation(input_dir, destination / "simulated-blobs/outputs", sources)
    config = azure_job.JobConfig(account_url="https://localsimulation.blob.core.windows.net",
                                 client_id="00000000-0000-0000-0000-000000000001",
                                 mode="dataset-analysis", workspace=destination / "workspace")
    forbidden_attempts = []
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "azure" or name.startswith("azure."):
            forbidden_attempts.append("azure_sdk_import")
            raise RuntimeError("Azure SDK imports are disabled during local verification")
        return original_import(name, *args, **kwargs)

    def forbidden_network(*args, **kwargs):
        forbidden_attempts.append("socket_operation")
        raise RuntimeError("Network operations are disabled during local verification")

    print("Scope: local filesystem Blob simulation; no Azure service validation.", flush=True)
    with ExitStack() as stack:
        stack.enter_context(patch("builtins.__import__", guarded_import))
        for target in ("socket.create_connection", "socket.getaddrinfo", "socket.socket.connect",
                       "socket.socket.connect_ex", "socket.socket.send", "socket.socket.sendall",
                       "socket.socket.sendto"):
            stack.enter_context(patch(target, forbidden_network))
        status = azure_job.run_job(config, blob_service=service)
    print(f"Production dataset-analysis function returned: {status['status']}", flush=True)

    prefix = status["output_prefix"]
    remote = service.blob_root / "runs" / status["run_id"]
    checks = []

    def check(name: str, passed: bool, observed=None):
        item = {"name": name, "passed": bool(passed)}
        if observed is not None:
            item["observed"] = observed
        checks.append(item)
        print(f"{name}: {'PASS' if passed else 'FAIL'}", flush=True)

    check("job_completed", status["status"] == "completed" and status["error_code"] is None, status)
    check("no_azure_sdk_or_network_attempts", not forbidden_attempts, forbidden_attempts)
    expected_sources = {item["filename"]: item for item in sources}
    check("five_exact_input_streams", len(service.downloads) == 5
          and {item["filename"] for item in service.downloads} == set(expected_sources)
          and all(item["bytes_streamed"] == expected_sources[item["filename"]]["size_bytes"]
                  and item["sha256"] == expected_sources[item["filename"]]["sha256"]
                  for item in service.downloads), service.downloads)
    names = [item["blob_name"].removeprefix(prefix) for item in service.uploads]
    check("seven_artifacts_and_completion_only", len(names) == 8
          and set(names) == {*EXPECTED_ARTIFACTS, "completion.json"}, names)
    check("completion_uploaded_last", bool(names) and names[-1] == "completion.json"
          and status["completion_published"] is True)
    check("uploads_never_overwrite", all(item["overwrite"] is False for item in service.uploads))

    documents = {}
    for name in (*EXPECTED_ARTIFACTS, "completion.json"):
        path = remote / name
        if path.is_file():
            documents[name] = json.loads(path.read_text(encoding="utf-8"))
    manifest = documents.get("completion.json", {})
    check("completion_manifest_verified_inputs", manifest.get("status") == "completed"
          and manifest.get("source_inputs_downloaded_and_verified") is True
          and manifest.get("source_inventory_sha256") == inventory_sha
          and manifest.get("sources") == sources)
    recorded_artifacts = manifest.get("artifacts", [])
    actual_files = {path.relative_to(remote).as_posix() for path in remote.rglob("*") if path.is_file()}
    check("filesystem_contains_no_unlisted_or_raw_outputs", actual_files == {*EXPECTED_ARTIFACTS, "completion.json"}
          and not any(name.endswith((".parquet", ".zip", ".sqlite3", ".jsonl")) for name in actual_files))
    hashes_match = len(recorded_artifacts) == 7
    for item in recorded_artifacts:
        path = remote / item["name"]
        hashes_match = hashes_match and item["name"] in EXPECTED_ARTIFACTS and path.is_file()
        if not hashes_match:
            break
        upload = next((record for record in service.uploads if record["blob_name"] == prefix + item["name"]), None)
        hashes_match = (path.stat().st_size == item["size_bytes"] and _file_hash(path) == item["sha256"]
                        and upload is not None and upload["size_bytes"] == item["size_bytes"]
                        and upload["sha256"] == item["sha256"])
    check("seven_uploaded_artifact_sizes_and_hashes_match", hashes_match, recorded_artifacts)
    evaluation = documents.get("advice-evaluation/advice-evaluation.json", {})
    check("all_twelve_advice_cases_pass", evaluation.get("case_count") == 12
          and evaluation.get("passed_count") == 12 and evaluation.get("all_cases_passed") is True
          and len(evaluation.get("cases", [])) == 12
          and all(item.get("passed") is True and item.get("failures") == [] for item in evaluation["cases"]),
          {key: evaluation.get(key) for key in ("casebook_id", "casebook_sha256", "case_count", "passed_count", "all_cases_passed")})
    replay = documents.get("replay/replay-summary.json", {})
    check("twenty_rows_durably_exercise_policy_unqualified", replay.get("rows_replayed") == 20
          and replay.get("decisions") == {"escalate": 20}
          and replay.get("reason_counts", {}).get("policy_unqualified") == 20
          and replay.get("durable_qualification_events") == 20
          and replay.get("qualification_gate_exercised") is True, replay)
    qualification = documents.get("qualification/source-qualification.json", {})
    check("five_sources_match_and_three_parquets_analyzed", qualification.get("inspection_summary", {}).get("status") == "complete"
          and qualification.get("inspection_summary", {}).get("matched_file_count") == 5
          and qualification.get("inspection_summary", {}).get("analyzed_parquet_count") == 3,
          qualification.get("inspection_summary"))
    profile = documents.get("profiles/profile-summary.json", {})
    check("raw_rows_and_archive_text_excluded", manifest.get("raw_dataset_records_uploaded") is False
          and profile.get("raw_records_included") is False and profile.get("archive_text_included") is False
          and replay.get("raw_rows_included") is False and "observations_file" not in replay
          and "audit_db" not in replay)
    local_paths = {str(input_dir), input_dir.as_posix(), str(config.workspace), config.workspace.as_posix()}
    check("published_json_excludes_local_absolute_paths", all(not any(path in value for path in local_paths)
                                                              for value in _strings(documents)))
    check("no_model_or_equipment_authority", manifest.get("models") == {"provider": None, "model": None, "calls": 0}
          and manifest.get("authority", {}).get("physical_commands_executed") is False
          and manifest.get("authority", {}).get("engineering_units_and_operating_limits_qualified") is False
          and evaluation.get("model_inference_used") is False)
    after = _source_hashes()
    check("source_files_unchanged_during_verification", before == after)
    report = {
        "schema_version": "1.0.0", "application_version": __version__,
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "actual dataset-analysis runner using a local filesystem Blob simulation; not Azure service validation",
        "azure_service_validation_performed": False, "azure_sdk_used": False,
        "network_calls_performed": False, "domain_acceptance_evaluated": False,
        "model_inference_used": False, "duration_seconds": round(time.perf_counter() - started, 3),
        "python": platform.python_version(), "platform": platform.platform(),
        "dependencies": {name: importlib.metadata.version(name) for name in ("pyarrow", "scipy", "numpy", "h5py")},
        "job_status": status,
        "job_status_storage_meaning": "azure_blob names the exercised production branch; all Blob operations were simulated on local files",
        "simulated_blob_directory": remote.relative_to(ROOT).as_posix(),
        "workspace_directory": (config.workspace / status["run_id"]).relative_to(ROOT).as_posix(),
        "checks": checks, "all_checks_passed": all(item["passed"] for item in checks),
        "uploads_in_order": service.uploads, "source_sha256": before,
    }
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "outputs/azure-local-verification")
    args = parser.parse_args()
    destination = args.output_dir.resolve()
    if not destination.is_relative_to((ROOT / "outputs").resolve()):
        parser.error("--output-dir must be inside this repository's outputs directory")
    input_dir = args.input_dir.resolve()
    if not input_dir.is_dir():
        parser.error("--input-dir must name the directory containing the five supplied source files")
    report = verify(input_dir, destination)
    print(f"Summary: {(destination / 'summary.json').relative_to(ROOT).as_posix()}")
    return 0 if report["all_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
