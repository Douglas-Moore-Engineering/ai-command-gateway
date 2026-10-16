"""Verify a downloaded job run against this checkout's artifact contract.

This checks bounded local bytes and declared results only. A completion manifest
is not signed: Azure provenance, execution success, upload ordering and effective
permissions need separate evidence. SQLite artifacts are hashed, never opened.
The run directory must contain only completion.json and its mode's artifacts.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import uuid

from ai_command_gateway import __version__, azure_job
from ai_command_gateway.advice_evaluation import _check_response, _read_cases, _validate_cases
from ai_command_gateway.evidence import PINNED_SOURCES, load_catalog


ROOT = Path(__file__).resolve().parents[1]
MAX_MANIFEST_BYTES = 64 * 1024
MANIFEST_KEYS = {
    "schema_version", "run_id", "mode", "status", "error_code", "started_at_utc",
    "finished_at_utc", "application_version", "runner_sha256", "source_inventory_sha256",
    "sources", "source_inputs_downloaded_and_verified", "models", "authority", "artifacts",
    "artifact_storage", "raw_dataset_records_uploaded", "completion_semantics",
}
DEMO_CHECKS = {
    "synthetic_in_range_allowed", "synthetic_out_of_range_blocked", "missing_evidence_escalated",
    "approved_mock_executed", "approval_replay_blocked",
}


class VerificationFailure(ValueError):
    """Only fixed diagnostic codes escape the downloaded-data boundary."""


def _require(condition, code):
    if not condition:
        raise VerificationFailure(code)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _same(actual, expected):
    # JSON booleans must not masquerade as integer counts.
    return json.dumps(actual, sort_keys=True, allow_nan=False) == json.dumps(expected, sort_keys=True, allow_nan=False)


def _json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result, "duplicate_json_key")
            result[key] = value
        return result

    def constant(_):
        raise VerificationFailure("nonfinite_json")

    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    pending = [(value, 0)]
    while pending:
        item, depth = pending.pop()
        _require(depth <= 32, "json_nesting_limit")
        if type(item) is float:
            _require(math.isfinite(item), "nonfinite_json")
        if type(item) is dict:
            pending.extend((child, depth + 1) for child in item.values())
        elif type(item) is list:
            pending.extend((child, depth + 1) for child in item)
    _require(type(value) is dict, "json_object_required")
    return value


def _unlinked(path):
    info = path.lstat()
    _require(not stat.S_ISLNK(info.st_mode)
             and not getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT,
             "linked_path_rejected")
    return info


def _directory_files(directory, expected):
    absolute = directory.absolute()
    _require(".." not in absolute.parts, "unsafe_run_directory")
    for parent in (absolute, *absolute.parents):
        _unlinked(parent)
    _require(absolute.is_dir(), "run_directory_missing")
    directories = {str(Path(name).parent).replace("\\", "/") for name in expected} - {"."}
    actual = set()
    pending = [absolute]
    entries = 0
    while pending:
        with os.scandir(pending.pop()) as children:
            for child in children:
                entries += 1
                _require(entries <= len(expected) + len(directories), "unexpected_artifact")
                path = Path(child.path)
                info = _unlinked(path)
                name = path.relative_to(absolute).as_posix()
                if stat.S_ISDIR(info.st_mode):
                    _require(name in directories, "unexpected_artifact_directory")
                    pending.append(path)
                else:
                    _require(stat.S_ISREG(info.st_mode) and name in expected, "unexpected_artifact")
                    _require(info.st_nlink == 1, "linked_path_rejected")
                    actual.add(name)
    _require(actual == expected, "missing_artifact")
    return absolute


def _read(path, limit):
    info = _unlinked(path)
    _require(stat.S_ISREG(info.st_mode) and 0 < info.st_size <= limit, "artifact_size_invalid")
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    _require(len(raw) == info.st_size and len(raw) <= limit, "artifact_size_invalid")
    return raw


def _source_hashes():
    paths = [Path(__file__), ROOT / "data/lineage/source-inventory.json",
             ROOT / "data/evaluation/advice-cases-v1.json"]
    paths.extend((ROOT / "src/ai_command_gateway").glob("*.py"))
    return {p.relative_to(ROOT).as_posix(): _sha(p.read_bytes()) for p in sorted(paths)}


def _demo(doc):
    _require(type(doc.get("checks")) is dict and set(doc["checks"]) == DEMO_CHECKS
             and all(value is True for value in doc["checks"].values()), "demo_checks_failed")
    _require(doc.get("audit_db") == "demo/audit.sqlite3", "demo_audit_reference_invalid")
    for field, decision in (("evaluate", "allow"), ("block", "block"), ("escalate", "escalate"),
                            ("approval", "allow"), ("execution", "allow"), ("replay", "block")):
        _require(type(doc.get(field)) is dict and doc[field].get("decision") == decision
                 and doc[field].get("mock_only") is True,
                 "demo_result_mismatch")
    _require(doc["execution"].get("outcome") == "mock_executed"
             and type(doc["execution"].get("mock_receipt")) is dict
             and type(doc["approval"].get("approval_id")) is str and bool(doc["approval"]["approval_id"])
             and doc["execution"]["mock_receipt"].get("approval_id") == doc["approval"]["approval_id"],
             "demo_result_mismatch")


def _dataset(directory, documents, inventory_sha):
    profile = documents["profiles/profile-summary.json"]
    summary = profile.get("inspection_summary", {})
    _require(summary.get("status") == "complete"
             and all(type(summary.get(k)) is int and summary[k] == 5 for k in
                     ("expected_file_count", "profiled_file_count", "fully_inspected_file_count")),
             "profile_incomplete")
    expected_files = [{"filename": name, "source_id": item[0], "format": item[1],
                       "size_bytes": item[2], "sha256": item[3], "status": "profiled"}
                      for name, item in PINNED_SOURCES.items()]
    _require(_same(profile.get("files"), expected_files), "profile_source_identity_mismatch")
    _require(profile.get("raw_records_included") is False and profile.get("archive_text_included") is False
             and profile.get("qualification_status") == "unresolved", "profile_scope_mismatch")
    qualification = documents["qualification/source-qualification.json"]
    summary = qualification.get("inspection_summary", {})
    _require(summary.get("status") == "complete" and type(summary.get("matched_file_count")) is int
             and summary["matched_file_count"] == 5 and type(summary.get("analyzed_parquet_count")) is int
             and summary["analyzed_parquet_count"] == 3, "qualification_incomplete")
    _require(qualification.get("inventory") == {"status": "loaded", "sha256": inventory_sha},
             "qualification_inventory_mismatch")
    qualified = qualification.get("qualification", {})
    _require(qualified.get("status") == "unresolved" and qualified.get("raw_rows_included") is False
             and qualified.get("physical_limits_learned") is False
             and qualified.get("physical_validity_labels_available") is False, "qualification_scope_mismatch")
    files = qualification.get("files")
    _require(type(files) is list and len(files) == 5, "qualification_source_identity_mismatch")
    names = set()
    for item in files:
        _require(type(item) is dict and type(item.get("filename")) is str
                 and item["filename"] in PINNED_SOURCES and item["filename"] not in names,
                 "qualification_source_identity_mismatch")
        names.add(item["filename"])
        source, kind, size, digest = PINNED_SOURCES[item["filename"]]
        _require(item.get("source_id") == source and item.get("format") == kind
                 and _same(item.get("identity"), {"expected_sha256": digest, "observed_sha256": digest,
                                                  "expected_size_bytes": size, "observed_size_bytes": size,
                                                  "matches": True}), "qualification_source_identity_mismatch")
    catalog = load_catalog(directory / "advice/evidence-catalog.json")
    evaluation = documents["advice-evaluation/advice-evaluation.json"]
    case_raw, casebook = _read_cases(ROOT / "data/evaluation/advice-cases-v1.json")
    _validate_cases(casebook)
    _require(evaluation.get("casebook_id") == casebook["id"]
             and evaluation.get("casebook_sha256") == _sha(case_raw)
             and evaluation.get("catalog_id") == catalog["catalog_id"]
             and evaluation.get("catalog_sha256") == catalog["content_sha256"], "evaluation_reference_mismatch")
    count = len(casebook["cases"])
    _require(type(evaluation.get("case_count")) is int and evaluation["case_count"] == count == 12
             and type(evaluation.get("passed_count")) is int and evaluation["passed_count"] == count
             and evaluation.get("all_cases_passed") is True and evaluation.get("model_inference_used") is False
             and evaluation.get("domain_acceptance_evaluated") is False, "evaluation_failed")
    cases = evaluation.get("cases")
    _require(type(cases) is list and len(cases) == count, "evaluation_failed")
    facts = {fact["fact_id"]: fact for fact in catalog["facts"]}
    for actual, expected in zip(cases, casebook["cases"]):
        _require(type(actual) is dict and set(actual) == {"id", "passed", "failures", "response"}
                 and actual["id"] == expected["id"] and actual["passed"] is True and actual["failures"] == []
                 and _check_response(actual["response"], expected, catalog, facts) == [], "evaluation_failed")
    replay = documents["replay/replay-summary.json"]
    expected = {"rows_replayed": 20, "decisions": {"escalate": 20}, "reason_counts": {"policy_unqualified": 20},
                "durable_qualification_events": 20, "qualification_gate_exercised": True,
                "raw_rows_included": False, "physical_command_validity_evaluated": False,
                "ground_truth_used": False, "source_id": "S1", "source_file": "process_dataset.parquet",
                "sha256": PINNED_SOURCES["process_dataset.parquet"][3], "total_source_rows": 13912}
    _require(all(_same(replay.get(key), value) for key, value in expected.items())
             and "observations_file" not in replay and "audit_db" not in replay, "replay_failed")


def verify(run_directory: Path, *, expected_mode: str, expected_run_id: str) -> dict:
    report = {"schema_version": "1.0.0", "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
              "scope": "downloaded artifact consistency only; unsigned declarations are not cloud provenance",
              "azure_provenance_verified": False, "arm_execution_success_verified": False,
              "completion_upload_order_verified": False, "sqlite_contents_evaluated": False,
              "domain_acceptance_evaluated": False, "all_checks_passed": False, "error_code": None}
    try:
        _require(type(expected_mode) is str and expected_mode in azure_job.ARTIFACTS, "invalid_expected_mode")
        _require(type(expected_run_id) is str and str(uuid.UUID(expected_run_id)) == expected_run_id,
                 "invalid_expected_run_id")
        before = _source_hashes()
        allowed = {*azure_job.ARTIFACTS[expected_mode], "completion.json"}
        directory = _directory_files(Path(run_directory), allowed)
        raw = _read(directory / "completion.json", MAX_MANIFEST_BYTES)
        manifest = _json(raw)
        _require(set(manifest) == MANIFEST_KEYS and manifest["schema_version"] == "1.0.0",
                 "manifest_schema_mismatch")
        _require(manifest["mode"] == expected_mode and manifest["run_id"] == expected_run_id,
                 "manifest_run_binding_mismatch")
        _require(manifest["status"] == "completed" and manifest["error_code"] is None, "run_not_completed")
        _require(manifest["application_version"] == __version__
                 and manifest["runner_sha256"] == before["src/ai_command_gateway/azure_job.py"],
                 "runner_baseline_mismatch")
        started, finished = (datetime.fromisoformat(manifest[key]) for key in ("started_at_utc", "finished_at_utc"))
        _require(started.utcoffset() is not None and finished.utcoffset() is not None and finished >= started,
                 "manifest_time_invalid")
        sources, inventory_sha = azure_job._source_inventory()
        _require(_same(manifest["sources"], sources) and manifest["source_inventory_sha256"] == inventory_sha
                 and manifest["source_inputs_downloaded_and_verified"] is (expected_mode == "dataset-analysis"),
                 "manifest_source_identity_mismatch")
        _require(_same(manifest["models"], {"provider": None, "model": None, "calls": 0})
                 and _same(manifest["authority"], {"mock_execution_only": True, "physical_commands_executed": False,
                                                   "engineering_units_and_operating_limits_qualified": False})
                 and manifest["artifact_storage"] == "azure_blob" and manifest["raw_dataset_records_uploaded"] is False
                 and manifest["completion_semantics"] == "written_after_all_listed_artifacts_are_acknowledged; not domain acceptance",
                 "manifest_scope_mismatch")
        artifacts = manifest["artifacts"]
        _require(type(artifacts) is list and len(artifacts) == len(allowed) - 1, "artifact_manifest_mismatch")
        names, total, documents = set(), 0, {}
        records = [{"name": "completion.json", "size_bytes": len(raw), "sha256": _sha(raw)}]
        for item in artifacts:
            _require(type(item) is dict and set(item) == {"name", "size_bytes", "sha256"}
                     and type(item["name"]) is str and item["name"] in allowed - {"completion.json"}
                     and item["name"] not in names, "artifact_manifest_mismatch")
            names.add(item["name"])
            raw = _read(directory / item["name"], azure_job.MAX_ARTIFACT_BYTES)
            total += len(raw)
            _require(total <= azure_job.MAX_ARTIFACT_TOTAL_BYTES, "artifact_total_size_invalid")
            _require(type(item["size_bytes"]) is int and item["size_bytes"] == len(raw)
                     and item["sha256"] == _sha(raw), "artifact_hash_or_size_mismatch")
            records.append(item)
            if item["name"].endswith(".json"):
                documents[item["name"]] = _json(raw)
        if expected_mode == "demo":
            _demo(documents["demo/demo-report.json"])
        else:
            _dataset(directory, documents, inventory_sha)
        _require(before == _source_hashes(), "verifier_baseline_changed")
        report.update(all_checks_passed=True, run_id=expected_run_id, mode=expected_mode,
                      evidence_directory=str(directory), artifact_evidence=records, source_sha256=before,
                      source_identities=sources)
    except VerificationFailure as exc:
        report["error_code"] = str(exc)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError, OverflowError):
        report["error_code"] = "invalid_or_unreadable_artifacts"
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--expected-mode", choices=sorted(azure_job.ARTIFACTS), required=True)
    parser.add_argument("--expected-run-id", required=True)
    args = parser.parse_args(argv)
    report = verify(args.run_dir, expected_mode=args.expected_mode, expected_run_id=args.expected_run_id)
    print(json.dumps(report, indent=2, allow_nan=False))
    return 0 if report["all_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
