"""Identity-bound, aggregate source qualification evidence for offline review.

This module measures stored timestamps and numeric quality. It does not infer
clock offsets, unit scales, physical limits, or command safety from observations.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from .datasets import SOURCE_FILES, hash_file


BATCH_ROWS = 65536
MAX_TIMESTAMP_ROWS = 20_000_000
GAP_MEDIAN_MULTIPLIER = 10


def canonical_sha256(value: Any) -> str:
    """Digest canonical JSON; a content identity, not an authenticity signature."""
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def evidence_sha256(evidence: dict[str, Any]) -> str:
    return canonical_sha256({k: v for k, v in evidence.items() if k not in {"evidence_id", "evidence_sha256"}})


def report_sha256(report: dict[str, Any]) -> str:
    return canonical_sha256({k: v for k, v in report.items() if k not in {"generated_at_utc", "report_sha256"}})


def _distribution(values: np.ndarray) -> dict[str, Any] | None:
    if not len(values):
        return None
    # Nearest-rank order statistics avoid interpolation of integer clock ticks.
    ranks = [max(0, (len(values) * numerator + 99) // 100 - 1) for numerator in (50, 95, 99)]
    partition = np.partition(values, ranks)
    return {"count": len(values), "min": int(values.min()), "p50": int(partition[ranks[0]]),
            "p95": int(partition[ranks[1]]), "p99": int(partition[ranks[2]]),
            "max": int(values.max()), "quantile_method": "nearest_rank"}


def _timestamp_summary(values: np.ndarray, valid: np.ndarray, dtype: pa.TimestampType) -> dict[str, Any]:
    kept = values[valid]
    pair_valid = valid[:-1] & valid[1:]
    left, right = values[:-1][pair_valid], values[1:][pair_valid]
    positive, negative = right > left, right < left
    equal = ~(positive | negative)
    # Unsigned subtraction represents the full possible positive int64 interval
    # without overflowing at timestamps straddling the int64 boundary.
    deltas = right[positive].astype(np.uint64) - left[positive].astype(np.uint64)
    cadence = _distribution(deltas)
    threshold = cadence["p50"] * GAP_MEDIAN_MULTIPLIER if cadence else None
    gaps = int(np.count_nonzero(deltas > threshold)) if threshold is not None and threshold <= np.iinfo(np.uint64).max else 0
    unique_count = len(np.unique(kept))
    time_range = {"min": None, "max": None}
    if len(kept):
        time_range = {name: pa.scalar(int(value), pa.int64()).cast(dtype).cast(pa.string()).as_py()
                      for name, value in (("min", kept.min()), ("max", kept.max()))}
    return {
        "status": "observed", "scope": "all_rows_in_stored_order", "row_count": len(values),
        "valid_timestamp_count": len(kept), "null_count": int(np.count_nonzero(~valid)),
        "stored_unit": dtype.unit, "stored_timezone": dtype.tz,
        "clock_basis": "timezone_metadata_present" if dtype.tz else "naive_timezone_unresolved",
        "timezone_inferred": False, "time_range": time_range,
        "adjacent_pairs": {"total": max(0, len(values) - 1), "evaluable": int(pair_valid.sum()),
                           "skipped_due_to_null": int((~pair_valid).sum()), "increasing": int(positive.sum()),
                           "decreasing": int(negative.sum()), "equal": int(equal.sum())},
        "nondecreasing_over_all_rows": bool(not negative.any()) if len(values) > 1 and valid.all() else None,
        "unique_timestamp_count": unique_count,
        "duplicate_timestamp_row_count": len(kept) - unique_count,
        "duplicate_scope": "all_non_null_rows_including_nonadjacent_repeats",
        "positive_adjacent_delta_distribution": cadence,
        "cadence_unit": dtype.unit,
        "gap_observation": {"rule": "positive_adjacent_delta_gt_10_times_positive_delta_p50",
                            "threshold_ticks": threshold, "count": gaps,
                            "meaning": "descriptive_outliers_not_proven_missing_samples"},
        "interpretation": "stored_order_and_clock_ticks_only_not_clock_alignment_or_measurement_validity",
    }


def analyze_parquet(path: Path, *, batch_rows: int = BATCH_ROWS,
                    max_timestamp_rows: int = MAX_TIMESTAMP_ROWS) -> dict[str, Any]:
    """Scan numeric/time fields completely; never decode payload/text columns.

    Exact timestamp duplicate counts and cadence order statistics use arrays up
    to the explicit row cap. Sources above it are partial, never sampled silently.
    """
    if batch_rows < 1 or max_timestamp_rows < 0:
        raise ValueError("batch_rows must be positive and max_timestamp_rows nonnegative")
    with pq.ParquetFile(path) as parquet:
        row_count = parquet.metadata.num_rows
        columns: list[dict[str, Any]] = []
        selected: list[str] = []
        time_buffers: dict[str, tuple[list[np.ndarray], list[np.ndarray], pa.TimestampType]] = {}
        for field in parquet.schema_arrow:
            dtype = field.type.value_type if pa.types.is_dictionary(field.type) else field.type
            column: dict[str, Any] = {
                "name": field.name, "arrow_type": str(field.type), "scan_status": "schema_only",
                "scanned_row_count": 0, "null_count": None,
                "engineering_semantics": {"status": "unresolved", "units": None, "scale": None,
                                          "sign_convention": None, "validity_rules": None,
                                          "candidate_scaling": "unsupported_no_conversion_applied"},
            }
            if pa.types.is_integer(dtype) or pa.types.is_floating(dtype):
                column["numeric"] = {"finite_count": 0, "nonfinite_count": 0, "min": None, "max": None}
                selected.append(field.name)
            elif pa.types.is_timestamp(dtype):
                if row_count <= max_timestamp_rows:
                    selected.append(field.name)
                    time_buffers[field.name] = ([], [], dtype)
                else:
                    column["timestamp"] = {"status": "skipped_resource_limit", "stored_timezone": dtype.tz,
                                           "stored_unit": dtype.unit, "row_limit": max_timestamp_rows}
            columns.append(column)
        by_name = {column["name"]: column for column in columns}
        scanned = 0
        if selected:
            for batch in parquet.iter_batches(batch_size=batch_rows, columns=selected):
                scanned += batch.num_rows
                for field, values in zip(batch.schema, batch.columns):
                    column = by_name[field.name]
                    if pa.types.is_dictionary(values.type):
                        values = pc.dictionary_decode(values)
                    column["scan_status"] = "all_rows"
                    column["scanned_row_count"] += len(values)
                    column["null_count"] = (column["null_count"] or 0) + values.null_count
                    if "numeric" in column:
                        numeric = column["numeric"]
                        finite = pc.filter(values, pc.is_finite(values))
                        numeric["finite_count"] += len(finite)
                        numeric["nonfinite_count"] += len(values) - values.null_count - len(finite)
                        if len(finite):
                            bounds = pc.min_max(finite).as_py()
                            numeric["min"] = bounds["min"] if numeric["min"] is None else min(numeric["min"], bounds["min"])
                            numeric["max"] = bounds["max"] if numeric["max"] is None else max(numeric["max"], bounds["max"])
                    else:
                        ticks, valid, _ = time_buffers[field.name]
                        ticks.append(pc.fill_null(values.cast(pa.int64()), 0).to_numpy(zero_copy_only=False))
                        valid.append(pc.is_valid(values).to_numpy(zero_copy_only=False))
        for name, (tick_parts, valid_parts, dtype) in time_buffers.items():
            ticks = np.concatenate(tick_parts) if tick_parts else np.array([], dtype=np.int64)
            valid = np.concatenate(valid_parts) if valid_parts else np.array([], dtype=np.bool_)
            by_name[name]["timestamp"] = _timestamp_summary(ticks, valid, dtype)
            # Empty columns still received a complete scan of their zero rows.
            by_name[name].update({"scan_status": "all_rows", "null_count": int(np.count_nonzero(~valid))})
        if row_count == 0:
            for column in columns:
                if column["name"] in selected:
                    column.update({"scan_status": "all_rows", "null_count": 0})
        complete = scanned == row_count and all(column.get("timestamp", {}).get("status") != "skipped_resource_limit" for column in columns)
        return {"row_count": row_count, "scanned_row_count": scanned, "status": "complete" if complete else "partial",
                "scope": "timestamp_and_numeric_fields_all_rows_other_fields_schema_only",
                "selected_columns": selected, "binary_payloads_decoded": False, "raw_rows_emitted": 0,
                "timestamp_row_limit": max_timestamp_rows, "columns": columns}


def _load_inventory(path: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    payload = path.read_bytes()
    value = json.loads(payload)
    rows = value.get("files") if isinstance(value, dict) else None
    if not isinstance(rows, list) or len(rows) != len(SOURCE_FILES):
        raise ValueError("inventory must identify exactly the five expected source files")
    inventory: dict[str, dict[str, Any]] = {}
    expected = {filename: (source_id, kind) for source_id, filename, kind, _ in SOURCE_FILES}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("inventory file entry must be an object")
        name = row.get("filename")
        if not isinstance(name, str) or name not in expected or name in inventory:
            raise ValueError("inventory contains unexpected or duplicate filenames")
        source_id, kind = expected[name]
        if row.get("source_id") != source_id or row.get("format") != kind:
            raise ValueError("inventory source identity or format mismatch")
        if not isinstance(row.get("sha256"), str) or re.fullmatch(r"[0-9a-f]{64}", row["sha256"]) is None:
            raise ValueError("inventory SHA256 is invalid")
        if type(row.get("size_bytes")) is not int or row["size_bytes"] < 0:
            raise ValueError("inventory size_bytes is invalid")
        inventory[name] = row
    return {"status": "loaded", "sha256": hashlib.sha256(payload).hexdigest()}, inventory


def _evidence_for(entry: dict[str, Any]) -> list[dict[str, Any]]:
    facts = []
    for index, column in enumerate(entry["analysis"]["columns"]):
        if "timestamp" in column and column["timestamp"]["status"] == "observed":
            observation = column["timestamp"]
            stored_tz = observation["stored_timezone"]
            tz_text = f"stored timezone {stored_tz}" if stored_tz else "no stored timezone; timezone unresolved"
            text = (f"{entry['filename']} field {column['name']} contains {observation['valid_timestamp_count']} non-null timestamps "
                    f"across {observation['row_count']} rows, with {tz_text}. "
                    f"Stored row order has {observation['adjacent_pairs']['decreasing']} decreasing adjacent pairs; "
                    f"{observation['duplicate_timestamp_row_count']} rows repeat a timestamp. "
                    "Clock alignment and physical measurement validity remain unresolved.")
            kind = "timestamp_quality"
        elif "numeric" in column:
            observation = {"row_count": column["scanned_row_count"], "null_count": column["null_count"], **column["numeric"]}
            text = (f"{entry['filename']} field {column['name']} has {observation['finite_count']} finite, "
                    f"{observation['nonfinite_count']} nonfinite, and {observation['null_count']} null values "
                    f"across {observation['row_count']} scanned rows. Observed raw finite range: "
                    f"{observation['min']} to {observation['max']}. Units, scaling, and physical validity remain unresolved; "
                    "these extrema are not approved operating limits.")
            kind = "numeric_quality"
        else:
            continue
        fact = {"source_id": entry["source_id"], "filename": entry["filename"],
                "source_sha256": entry["identity"]["observed_sha256"], "kind": kind,
                "trust_class": "source_observed", "text": text,
                "locator": f"source-qualification.json#/files/{next(i for i, source in enumerate(SOURCE_FILES) if source[1] == entry['filename'])}/analysis/columns/{index}/{('timestamp' if kind == 'timestamp_quality' else 'numeric')}", "field": column["name"],
                "observations": observation}
        digest = evidence_sha256(fact)
        fact.update({"evidence_id": f"QUAL-{digest[:20]}", "evidence_sha256": digest})
        facts.append(fact)
    return facts


def qualify_sources(input_dir: Path, output_dir: Path,
                    inventory_path: Path = Path("data/lineage/source-inventory.json")) -> dict[str, Any]:
    """Write ``source-qualification.json`` with identity-bound aggregate evidence.

    A missing/invalid inventory blocks analysis. Missing or changed source bytes
    are reported per file and never produce qualifying observations or evidence.
    ZIP sources receive identity checks only; their timelines remain unexamined.
    """
    input_dir, output_dir, inventory_path = Path(input_dir), Path(output_dir), Path(inventory_path)
    inventory_error = None
    try:
        inventory_metadata, inventory = _load_inventory(inventory_path)
    except (OSError, ValueError, TypeError) as exc:
        inventory_error = f"{type(exc).__name__}: {exc}"
        inventory_metadata, inventory = {"status": "error", "sha256": None, "error": inventory_error}, {}
    files: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    for source_id, filename, kind, _ in SOURCE_FILES:
        entry: dict[str, Any] = {"source_id": source_id, "filename": filename, "format": kind,
                                 "qualification_status": "unresolved", "analysis_complete": False}
        files.append(entry)
        if inventory_error:
            entry["status"] = "inventory_error"
            continue
        expected = inventory[filename]
        path = input_dir / filename
        if not path.is_file():
            entry["status"] = "missing"
            continue
        try:
            before = hash_file(path)["sha256"]
            size = path.stat().st_size
            matches = before == expected["sha256"] and size == expected["size_bytes"]
            entry["identity"] = {"expected_sha256": expected["sha256"], "observed_sha256": before,
                                 "expected_size_bytes": expected["size_bytes"], "observed_size_bytes": size,
                                 "matches": matches}
            if not matches:
                entry["status"] = "identity_mismatch"
                continue
            if kind == "zip":
                entry.update({"status": "identity_verified_only", "scope": "archive_bytes_identity_only",
                              "unexamined": ["member_semantics", "numeric_quality", "timestamps", "units"]})
                continue
            analysis = analyze_parquet(path)
            after = hash_file(path)["sha256"]
            if after != before:
                entry["identity"].update({"matches": False, "post_analysis_sha256": after})
                entry["status"] = "changed_during_analysis"
                continue
            entry.update({"status": "analyzed", "analysis": analysis, "analysis_complete": analysis["status"] == "complete"})
            evidence.extend(_evidence_for(entry))
        except (OSError, ValueError, RuntimeError, pa.ArrowException) as exc:
            entry.update({"status": "error", "error": f"{type(exc).__name__}: {exc}"})
    matched = sum(entry.get("identity", {}).get("matches", False) for entry in files)
    analyzed = sum(entry["analysis_complete"] for entry in files)
    report = {
        "schema_version": "1.0.0", "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "offline_source_qualification", "inventory": inventory_metadata,
        "inspection_summary": {"status": "complete" if matched == 5 and analyzed == 3 else "partial",
                               "expected_file_count": 5, "matched_file_count": matched,
                               "analyzed_parquet_count": analyzed,
                               "meaning": "completion_of_declared_scope_not_semantic_or_control_qualification"},
        "qualification": {"status": "unresolved", "clock_alignment": "unresolved",
                          "engineering_units": "unresolved", "scaling": "unresolved",
                          "independent_sources_combined": False, "physical_limits_learned": False,
                          "physical_validity_labels_available": False, "raw_rows_included": False},
        "files": files, "evidence": evidence,
    }
    report["report_sha256"] = report_sha256(report)
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / "source-qualification.json"
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(destination)
    return report
