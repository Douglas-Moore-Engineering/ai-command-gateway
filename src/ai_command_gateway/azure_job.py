"""Manual Container Apps Job: managed-identity inputs and bounded result artifacts.

The default workload is a synthetic mock-only demonstration. Dataset analysis
requires all five pinned input hashes before it opens any source for analysis.
This runner has no model API or equipment execution path. Azure SDKs are loaded
only when a configured cloud run starts; local demo and help need no Azure SDK.
"""

from __future__ import annotations

import argparse
from contextlib import closing, redirect_stdout
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import sqlite3
import tempfile
from types import SimpleNamespace
from typing import Any, Mapping
import uuid

from . import __version__


PROJECT_ROOT = Path(__file__).resolve().parents[2]
INVENTORY_PATH = PROJECT_ROOT / "data/lineage/source-inventory.json"
MAX_ARTIFACT_BYTES = 16 * 1024 * 1024
MAX_ARTIFACT_TOTAL_BYTES = 64 * 1024 * 1024
DOWNLOAD_CHUNK_BYTES = 4 * 1024 * 1024
ARTIFACTS = {
    "demo": ("demo/demo-report.json", "demo/audit.sqlite3"),
    "dataset-analysis": (
        "profiles/profile-summary.json", "qualification/source-qualification.json",
        "advice/evidence-catalog.json", "advice/evidence-manifest.json",
        "advice/evidence-profile.json", "advice-evaluation/advice-evaluation.json",
        "replay/replay-summary.json",
    ),
}
_ERROR_CODES = frozenset({
    "configuration_invalid", "workspace_invalid", "inventory_invalid",
    "storage_client_failed", "input_download_failed", "input_size_mismatch",
    "input_hash_mismatch", "input_stream_invalid", "analysis_failed",
    "demo_checks_failed", "profile_incomplete", "qualification_incomplete",
    "advice_evaluation_failed", "replay_failed", "artifact_invalid",
    "artifact_upload_failed", "completion_upload_failed", "local_write_failed",
})


class JobFailure(Exception):
    """A fixed diagnostic code; never carries credentials or provider messages."""

    def __init__(self, code: str):
        self.code = code if code in _ERROR_CODES else "analysis_failed"
        super().__init__(self.code)


@dataclass(frozen=True)
class JobConfig:
    account_url: str | None = None
    client_id: str | None = None
    mode: str = "demo"
    input_container: str = "inputs"
    output_container: str = "outputs"
    workspace: Path = Path(tempfile.gettempdir()) / "ai-command-gateway"
    local_output: Path | None = None

    def __post_init__(self) -> None:
        if (type(self.mode) is not str or self.mode not in ARTIFACTS
                or self.input_container != "inputs" or self.output_container != "outputs"):
            raise JobFailure("configuration_invalid")
        if not isinstance(self.workspace, Path) or ".." in self.workspace.parts:
            raise JobFailure("configuration_invalid")
        if self.local_output is not None:
            if (not isinstance(self.local_output, Path) or ".." in self.local_output.parts
                    or self.mode != "demo"):
                raise JobFailure("configuration_invalid")
            return
        if (type(self.account_url) is not str
                or re.fullmatch(r"https://[a-z0-9]{3,24}\.blob\.core\.windows\.net/?", self.account_url) is None):
            raise JobFailure("configuration_invalid")
        object.__setattr__(self, "account_url", self.account_url.removesuffix("/"))
        if type(self.client_id) is not str:
            raise JobFailure("configuration_invalid")
        try:
            if str(uuid.UUID(self.client_id)) != self.client_id.lower():
                raise ValueError("noncanonical identity")
        except ValueError:
            raise JobFailure("configuration_invalid") from None

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "JobConfig":
        values = os.environ if environ is None else environ
        return cls(account_url=values.get("AZURE_STORAGE_ACCOUNT_URL"),
                   client_id=values.get("AZURE_CLIENT_ID"),
                   mode=values.get("AI_GATEWAY_JOB_MODE", "demo"),
                   input_container=values.get("AZURE_INPUT_CONTAINER", "inputs"),
                   output_container=values.get("AZURE_OUTPUT_CONTAINER", "outputs"),
                   workspace=Path(values.get("AI_GATEWAY_WORKSPACE", str(cls.workspace))))


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True,
                       allow_nan=False) + "\n").encode("utf-8")


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_json_bytes(value))


def _safe_child(root: Path, relative: str) -> Path:
    parsed = PurePosixPath(relative)
    if (not relative or "\\" in relative or parsed.is_absolute()
            or any(part in {".", ".."} for part in relative.split("/"))
            or ":" in relative or "//" in relative):
        raise JobFailure("workspace_invalid")
    candidate = root.joinpath(*parsed.parts)
    resolved_root = root.resolve()
    if not candidate.resolve().is_relative_to(resolved_root):
        raise JobFailure("workspace_invalid")
    for path in (candidate, *candidate.parents):
        if path == resolved_root.parent:
            break
        if path.is_symlink():
            raise JobFailure("workspace_invalid")
    return candidate


def _new_run_directory(config: JobConfig, run_id: str) -> Path:
    configured = config.local_output if config.local_output is not None else config.workspace
    absolute = configured.absolute()
    if any(path.is_symlink() for path in (absolute, *absolute.parents)):
        raise JobFailure("workspace_invalid")
    root = absolute.resolve()
    root.mkdir(parents=True, exist_ok=True)
    run_dir = _safe_child(root, run_id)
    run_dir.mkdir(exist_ok=False)
    return run_dir


def _source_inventory() -> tuple[list[dict], str]:
    """The bundled inventory cannot expand the hardcoded source allowlist."""
    from .evidence import PINNED_SOURCES

    with INVENTORY_PATH.open("rb") as stream:
        raw = stream.read(64 * 1024 + 1)
    if len(raw) > 64 * 1024:
        raise JobFailure("inventory_invalid")
    value = json.loads(raw)
    files = value.get("files") if type(value) is dict else None
    if type(files) is not list or len(files) != len(PINNED_SOURCES):
        raise JobFailure("inventory_invalid")
    indexed = {}
    for item in files:
        if type(item) is not dict or item.get("filename") not in PINNED_SOURCES:
            raise JobFailure("inventory_invalid")
        filename = item["filename"]
        source, kind, size, digest = PINNED_SOURCES[filename]
        if (filename in indexed or item.get("source_id") != source or item.get("format") != kind
                or type(item.get("size_bytes")) is not int or item["size_bytes"] != size
                or item.get("sha256") != digest):
            raise JobFailure("inventory_invalid")
        indexed[filename] = {"filename": filename, "source_id": source, "size_bytes": size,
                             "sha256": digest, "source_version": f"sha256:{digest}"}
    return [indexed[name] for name in PINNED_SOURCES], hashlib.sha256(raw).hexdigest()


def _storage_client(config: JobConfig):
    # No credential chain, account keys, SAS, CLI identity, or connection strings.
    from azure.identity import ManagedIdentityCredential
    from azure.storage.blob import BlobServiceClient

    credential = ManagedIdentityCredential(client_id=config.client_id)
    try:
        service = BlobServiceClient(account_url=config.account_url, credential=credential,
                                    max_single_get_size=DOWNLOAD_CHUNK_BYTES,
                                    max_chunk_get_size=DOWNLOAD_CHUNK_BYTES,
                                    connection_timeout=30, read_timeout=60, retry_total=2)
    except Exception:
        credential.close()
        raise
    return service, credential


def _download_sources(service: Any, config: JobConfig, input_dir: Path,
                      sources: list[dict]) -> None:
    input_dir.mkdir(parents=True, exist_ok=False)
    for source in sources:
        path = _safe_child(input_dir, source["filename"])
        blob = service.get_blob_client(container=config.input_container, blob=source["filename"])
        try:
            properties = blob.get_blob_properties(timeout=60)
            if type(properties.size) is not int or properties.size != source["size_bytes"]:
                raise JobFailure("input_size_mismatch")
            downloader = blob.download_blob(offset=0, length=source["size_bytes"] + 1,
                                            max_concurrency=1, timeout=60)
            size = 0
            digest = hashlib.sha256()
            with path.open("xb") as output:
                for chunk in downloader.chunks():
                    if type(chunk) is not bytes or not chunk or len(chunk) > DOWNLOAD_CHUNK_BYTES:
                        raise JobFailure("input_stream_invalid")
                    size += len(chunk)
                    if size > source["size_bytes"]:
                        raise JobFailure("input_size_mismatch")
                    digest.update(chunk)
                    output.write(chunk)
            if size != source["size_bytes"]:
                raise JobFailure("input_size_mismatch")
            if digest.hexdigest() != source["sha256"]:
                raise JobFailure("input_hash_mismatch")
        except JobFailure:
            raise
        except Exception:
            raise JobFailure("input_download_failed") from None


def _demo(run_dir: Path) -> None:
    from .cli import run_demo

    live_db = _safe_child(run_dir, "work/demo-live.sqlite3")
    args = SimpleNamespace(db=live_db, policy=PROJECT_ROOT / "config/policies/demo-policy.json",
                           request=PROJECT_ROOT / "data/samples/demo-request.json")
    captured = io.StringIO()
    with redirect_stdout(captured):
        code = run_demo(args)
    if code != 0:
        raise JobFailure("demo_checks_failed")
    report = json.loads(captured.getvalue())
    report["audit_db"] = "demo/audit.sqlite3"
    _write_json(_safe_child(run_dir, "demo/demo-report.json"), report)
    snapshot = _safe_child(run_dir, "demo/audit.sqlite3")
    # The live Gateway connection is already closed; backup makes a consistent
    # standalone SQLite artifact independent of any WAL or SHM sidecar.
    with closing(sqlite3.connect(live_db)) as source, closing(sqlite3.connect(snapshot)) as destination:
        source.backup(destination)


def _dataset_analysis(run_dir: Path) -> None:
    from .advice_evaluation import evaluate_advice
    from .datasets import profile_sources
    from .evidence import build_catalog
    from .qualification import qualify_sources
    from .replay import replay_process

    inputs = run_dir / "inputs"
    profile = profile_sources(inputs, run_dir / "work/profiles")
    if (profile.get("inspection_summary", {}).get("status") != "complete"
            or len(profile.get("files", [])) != 5
            or any(item.get("status") != "profiled" for item in profile["files"])):
        raise JobFailure("profile_incomplete")
    # Full profiles may include archive README text; only this typed summary is
    # publishable. The sanitized catalog snapshot is published separately.
    summary = {"schema_version": "1.0.0", "inspection_summary": profile["inspection_summary"],
               "qualification_status": "unresolved", "raw_records_included": False,
               "archive_text_included": False,
               "files": [{key: item[key] for key in
                          ("source_id", "filename", "format", "size_bytes", "sha256", "status")}
                         for item in profile["files"]]}
    _write_json(run_dir / "profiles/profile-summary.json", summary)
    qualification = qualify_sources(inputs, run_dir / "qualification", INVENTORY_PATH)
    if qualification.get("inspection_summary", {}).get("status") != "complete":
        raise JobFailure("qualification_incomplete")
    build_catalog(run_dir / "work/profiles/dataset-profile.json", INVENTORY_PATH, run_dir / "advice")
    evaluation = evaluate_advice(run_dir / "advice/evidence-catalog.json",
                                 PROJECT_ROOT / "data/evaluation/advice-cases-v1.json",
                                 run_dir / "advice-evaluation")
    if evaluation.get("all_cases_passed") is not True:
        raise JobFailure("advice_evaluation_failed")
    replay = replay_process(inputs, run_dir / "work/replay",
                            PROJECT_ROOT / "config/policies/unqualified-policy.json",
                            run_dir / "work/replay/audit.sqlite3", 20)
    if replay.get("qualification_gate_exercised") is not True:
        raise JobFailure("replay_failed")
    replay.pop("observations_file", None)
    replay.pop("audit_db", None)
    replay["raw_rows_included"] = False
    _write_json(run_dir / "replay/replay-summary.json", replay)


def _artifacts(run_dir: Path, mode: str) -> list[tuple[str, bytes, dict]]:
    artifacts = []
    total = 0
    for name in ARTIFACTS[mode]:
        path = _safe_child(run_dir, name)
        if not path.is_file() or not 0 < path.stat().st_size <= MAX_ARTIFACT_BYTES:
            raise JobFailure("artifact_invalid")
        with path.open("rb") as stream:
            raw = stream.read(MAX_ARTIFACT_BYTES + 1)
        total += len(raw)
        if len(raw) > MAX_ARTIFACT_BYTES or total > MAX_ARTIFACT_TOTAL_BYTES:
            raise JobFailure("artifact_invalid")
        metadata = {"name": name, "size_bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
        artifacts.append((name, raw, metadata))
    return artifacts


def _upload(service: Any, config: JobConfig, run_id: str, name: str, data: bytes) -> None:
    # Callers supply only fixed artifact names or completion.json.
    if name != "completion.json" and name not in ARTIFACTS[config.mode]:
        raise JobFailure("artifact_invalid")
    blob = service.get_blob_client(container=config.output_container, blob=f"runs/{run_id}/{name}")
    blob.upload_blob(data=data, overwrite=False, length=len(data), max_concurrency=1, timeout=60)


def run_job(config: JobConfig, blob_service: Any = None) -> dict:
    """Run once and return a small status object; injected services enable tests.

    A completion manifest is uploaded last and is successful only after every
    allowlisted artifact upload has been acknowledged. Failed uploads produce a
    failed manifest when storage remains available; failure to publish the
    manifest also fails the job. No raw provider error is returned or logged.
    """
    if not isinstance(config, JobConfig):
        raise JobFailure("configuration_invalid")
    run_id = str(uuid.uuid4())
    result = {"run_id": run_id, "mode": config.mode, "status": "failed", "error_code": None,
              "artifact_count": 0, "completion_published": False,
              "output_prefix": f"runs/{run_id}/" if config.local_output is None else f"{run_id}/",
              "storage": "local" if config.local_output is not None else "azure_blob"}
    service, credential, owned_service = blob_service, None, False
    run_dir = None
    sources = []
    inventory_sha256 = None
    uploaded = []
    inputs_verified = False
    started = datetime.now(timezone.utc).isoformat()
    try:
        run_dir = _new_run_directory(config, run_id)
        try:
            sources, inventory_sha256 = _source_inventory()
        except Exception:
            raise JobFailure("inventory_invalid") from None
        if config.local_output is None and service is None:
            try:
                service, credential = _storage_client(config)
                owned_service = True
            except Exception:
                raise JobFailure("storage_client_failed") from None
        if config.mode == "dataset-analysis":
            _download_sources(service, config, run_dir / "inputs", sources)
            inputs_verified = True
            _dataset_analysis(run_dir)
        else:
            _demo(run_dir)
        artifacts = _artifacts(run_dir, config.mode)
        for name, data, metadata in artifacts:
            if config.local_output is None:
                try:
                    _upload(service, config, run_id, name, data)
                except Exception:
                    raise JobFailure("artifact_upload_failed") from None
            uploaded.append(metadata)
        result.update(status="completed", artifact_count=len(uploaded))
    except JobFailure as exc:
        result["error_code"] = exc.code
    except Exception:
        result["error_code"] = "analysis_failed"
    result["artifact_count"] = len(uploaded)
    manifest = {
        "schema_version": "1.0.0", "run_id": run_id, "mode": config.mode,
        "status": result["status"], "error_code": result["error_code"],
        "started_at_utc": started, "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "application_version": __version__, "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "source_inventory_sha256": inventory_sha256, "sources": sources,
        "source_inputs_downloaded_and_verified": inputs_verified,
        "models": {"provider": None, "model": None, "calls": 0},
        "authority": {"mock_execution_only": True, "physical_commands_executed": False,
                      "engineering_units_and_operating_limits_qualified": False},
        "artifacts": uploaded, "artifact_storage": result["storage"],
        "raw_dataset_records_uploaded": False,
        "completion_semantics": "written_after_all_listed_artifacts_are_acknowledged; not domain acceptance",
    }
    try:
        if run_dir is None:
            raise JobFailure("local_write_failed")
        _write_json(run_dir / "completion.json", manifest)
        if config.local_output is None:
            if service is None:
                raise JobFailure("completion_upload_failed")
            _upload(service, config, run_id, "completion.json", _json_bytes(manifest))
            result["completion_published"] = True
    except Exception:
        result.update(status="failed", error_code="completion_upload_failed" if config.local_output is None else "local_write_failed")
        manifest.update(status="failed", error_code=result["error_code"])
        if run_dir is not None:
            try:
                _write_json(run_dir / "completion.json", manifest)
            except Exception:
                pass
    finally:
        if owned_service:
            for resource in (service, credential):
                try:
                    resource.close()
                except Exception:
                    pass
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manual Azure job; synthetic demo by default, no model or equipment calls")
    parser.add_argument("--local-output", type=Path, help="Run the synthetic demo locally without Azure configuration or credentials")
    args = parser.parse_args(argv)
    try:
        config = JobConfig(local_output=args.local_output) if args.local_output is not None else JobConfig.from_env()
        status = run_job(config)
    except Exception:
        status = {"status": "failed", "error_code": "configuration_invalid"}
    print(json.dumps(status, sort_keys=True))
    return 0 if status["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
