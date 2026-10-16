"""Read-only, bounded-batch observations of the supplied research datasets.

Raw records never enter the report. Archive text is untrusted source material;
scripts are hashed, never executed. Independent sources retain separate IDs.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath
import stat
import tempfile
from typing import Any, BinaryIO
import zipfile

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
from scipy.io import whosmat
from scipy.io.matlab import MatReadError


BATCH_ROWS = 8192
MAX_CATEGORIES = 64
MAX_TEXT_BYTES = 65536
MAX_MAT_BYTES = 16 * 1024 * 1024
MAX_MEMBER_BYTES = 256 * 1024 * 1024
MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 10000
CHUNK_BYTES = 1024 * 1024

SOURCE_FILES = (
    ("S1", "logs_dataset.parquet", "parquet", "28b94fef326526f46df96402be80e149"),
    ("S1", "packets_dataset.parquet", "parquet", "ebbdee3de97e25cf4020d8552f431762"),
    ("S1", "process_dataset.parquet", "parquet", "ebc3e048e0319f044ea47cc08e498999"),
    ("S2", "n76t439f65-1.zip", "zip", None),
    ("S3", "doi-10.34810-data2936.zip", "zip", None),
)


def _hash_stream(stream: BinaryIO, *, sink: BinaryIO | None = None) -> dict[str, str]:
    sha = hashlib.sha256()
    md5 = hashlib.md5(usedforsecurity=False)
    while chunk := stream.read(CHUNK_BYTES):
        sha.update(chunk)
        md5.update(chunk)
        if sink is not None:
            sink.write(chunk)
    return {"sha256": sha.hexdigest(), "md5": md5.hexdigest()}


def hash_file(path: Path) -> dict[str, str]:
    """Stream content digests; MD5 is a publisher identity check, not security."""
    with path.open("rb") as stream:
        return _hash_stream(stream)


def _json_scalar(value: Any) -> Any:
    if isinstance(value, pa.Scalar):
        # Arrow's datetime conversion otherwise loses ns precision or needs pandas.
        return value.cast(pa.string()).as_py()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _logical_type(dtype: pa.DataType) -> pa.DataType:
    return dtype.value_type if pa.types.is_dictionary(dtype) else dtype


def profile_parquet(path: Path, *, batch_rows: int = BATCH_ROWS) -> dict[str, Any]:
    """Scan every row in bounded batches, without retaining packet payloads.

Numeric/null/time summaries cover all rows. Only category *cardinality* is
limited: retained category counts cover the full scan, and overflow is explicit.
"""
    if batch_rows < 1:
        raise ValueError("batch_rows must be positive")
    with pq.ParquetFile(path) as parquet:
        return _profile_parquet(parquet, batch_rows=batch_rows)


def _profile_parquet(parquet: pq.ParquetFile, *, batch_rows: int) -> dict[str, Any]:
    columns: list[dict[str, Any]] = []
    for field in parquet.schema_arrow:
        dtype = _logical_type(field.type)
        column: dict[str, Any] = {
            "name": field.name,
            "arrow_type": str(field.type),
            "nullable": field.nullable,
            "null_count": 0,
            "non_null_count": 0,
        }
        if pa.types.is_integer(dtype) or pa.types.is_floating(dtype):
            column["numeric"] = {
                "finite_count": 0, "nonfinite_count": 0,
                "min": None, "max": None, "mean": None,
            }
        if pa.types.is_timestamp(dtype) or pa.types.is_date(dtype):
            column["time_range"] = {"min": None, "max": None}
            if pa.types.is_timestamp(dtype):
                column["timezone"] = dtype.tz
        if field.name.lower() in {"label", "attack", "class", "experiment", "scenario", "hostname", "field_name"}:
            column["categories"] = {
                "counts": {}, "max_categories": MAX_CATEGORIES,
                "overflow_value_count": 0, "scope": "all_rows",
                "meaning": "source_observation_not_physical_validity",
            }
        columns.append(column)

    scanned = 0
    for batch in parquet.iter_batches(batch_size=batch_rows):
        scanned += batch.num_rows
        for index, column in enumerate(columns):
            values = batch.column(index)
            if pa.types.is_dictionary(values.type):
                values = pc.dictionary_decode(values)
            column["null_count"] += values.null_count
            column["non_null_count"] += len(values) - values.null_count
            if "numeric" in column:
                numeric = column["numeric"]
                finite = pc.filter(values, pc.is_finite(values))
                count = len(finite)
                numeric["nonfinite_count"] += len(values) - values.null_count - count
                if count:
                    bounds = pc.min_max(finite).as_py()
                    numeric["min"] = bounds["min"] if numeric["min"] is None else min(numeric["min"], bounds["min"])
                    numeric["max"] = bounds["max"] if numeric["max"] is None else max(numeric["max"], bounds["max"])
                    previous_count = numeric["finite_count"]
                    combined_count = previous_count + count
                    batch_mean = pc.mean(finite).as_py()
                    # Weighted terms avoid overflowing a total sum of large values.
                    previous_mean = numeric["mean"] or 0.0
                    numeric["mean"] = previous_mean * (previous_count / combined_count) + batch_mean * (count / combined_count)
                    numeric["finite_count"] = combined_count
            if "time_range" in column and values.null_count < len(values):
                bounds = pc.min_max(values)
                times = column["time_range"]
                if times["min"] is None or pc.less(bounds["min"], times["min"]).as_py():
                    times["min"] = bounds["min"]
                if times["max"] is None or pc.greater(bounds["max"], times["max"]).as_py():
                    times["max"] = bounds["max"]
            if "categories" in column:
                categories = column["categories"]
                for entry in pc.value_counts(values).to_pylist():
                    value, count = entry["values"], entry["counts"]
                    if value is None:
                        continue
                    key = str(value)
                    # Long category strings are omitted rather than truncated and conflated.
                    if len(key) > 200 or (key not in categories["counts"] and len(categories["counts"]) >= MAX_CATEGORIES):
                        categories["overflow_value_count"] += count
                    else:
                        categories["counts"][key] = categories["counts"].get(key, 0) + count

    for column in columns:
        if "numeric" in column:
            column["numeric"] = {key: _json_scalar(value) for key, value in column["numeric"].items()}
        if "time_range" in column:
            column["time_range"] = {key: _json_scalar(value) for key, value in column["time_range"].items()}
    return {
        "row_count": parquet.metadata.num_rows,
        "scanned_row_count": scanned,
        "row_group_count": parquet.metadata.num_row_groups,
        "column_count": len(columns),
        "scan": {"scope": "all_rows", "batch_rows": batch_rows, "row_sampling": False, "raw_rows_emitted": 0},
        "columns": columns,
        "qualification": "units_sign_conventions_time_alignment_and_experiment_groups_unresolved",
    }


def _unsafe_member(info: zipfile.ZipInfo) -> bool:
    name = info.filename.replace("\\", "/")
    path = PurePosixPath(name)
    return bool(
        path.is_absolute() or ".." in path.parts or ":" in name
        or "\x00" in name or stat.S_ISLNK(info.external_attr >> 16)
    )


def _manifest_entry(info: zipfile.ZipInfo) -> dict[str, Any]:
    return {
        "name": info.filename, "size_bytes": info.file_size,
        "compressed_bytes": info.compress_size, "crc32": f"{info.CRC:08x}",
        "is_directory": info.is_dir(), "unsafe_path": _unsafe_member(info),
    }


def _mat_metadata(payload: bytes) -> dict[str, Any]:
    if payload.startswith(b"MATLAB 7.3 MAT-file"):
        try:
            import h5py
        except ImportError:
            return {"format": "MATLAB_v7.3_HDF5", "status": "requires_h5py", "variables": []}
        variables: list[dict[str, Any]] = []
        with h5py.File(io.BytesIO(payload), "r") as mat:
            # Examine only root object headers. Never resolve external links.
            for name in mat:
                link = mat.get(name, getlink=True)
                if not isinstance(link, h5py.HardLink):
                    variables.append({"name": name, "kind": "link_not_followed"})
                    continue
                value = mat[name]
                entry: dict[str, Any] = {"name": name, "kind": "group"}
                if isinstance(value, h5py.Dataset):
                    entry.update({"kind": "dataset", "storage_shape": list(value.shape), "dtype": str(value.dtype)})
                matlab_class = value.attrs.get("MATLAB_class")
                if isinstance(matlab_class, bytes):
                    entry["matlab_class"] = matlab_class.decode("utf-8", errors="replace")
                variables.append(entry)
        return {"format": "MATLAB_v7.3_HDF5", "status": "metadata_only", "variables": variables,
                "shape_note": "HDF5 storage order; MATLAB dimension order may be reversed"}
    variables = whosmat(io.BytesIO(payload))
    return {"format": "MATLAB_pre_v7.3", "status": "metadata_only", "variables": [
        {"name": name, "shape": list(shape), "matlab_class": dtype} for name, shape, dtype in variables
    ]}


def profile_zip(path: Path) -> dict[str, Any]:
    """Inventory ZIPs without extracting paths or executing their contents.

Outer member SHA256 is streamed; bounded MAT/readme metadata is inspected.
One nested ZIP level is inventoried with CRCs only, using a temporary spool.
"""
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        if len(infos) > MAX_ARCHIVE_MEMBERS:
            raise ValueError("Archive exceeds member-count limit")
        total_bytes = sum(info.file_size for info in infos)
        permit_content = total_bytes <= MAX_ARCHIVE_BYTES
        members: list[dict[str, Any]] = []
        for info in infos:
            entry = _manifest_entry(info)
            members.append(entry)
            if info.is_dir():
                entry["inspection_status"] = "directory"
                continue
            if entry["unsafe_path"]:
                entry["inspection_status"] = "blocked_unsafe_path"
                continue
            if not permit_content or info.file_size > MAX_MEMBER_BYTES or info.file_size > max(info.compress_size, 1) * 1000:
                entry["inspection_status"] = "skipped_resource_limit"
                continue
            if info.flag_bits & 0x1:
                entry["inspection_status"] = "skipped_encrypted"
                continue
            suffix = PurePosixPath(info.filename).suffix.lower()
            try:
                if suffix == ".zip":
                    with tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024) as spool:
                        with archive.open(info) as stream:
                            entry.update(_hash_stream(stream, sink=spool))
                        spool.seek(0)
                        with zipfile.ZipFile(spool) as nested:
                            children = nested.infolist()
                            if len(children) > MAX_ARCHIVE_MEMBERS:
                                raise ValueError("Nested archive exceeds member-count limit")
                            entry["nested_archive"] = {
                                "member_count": len(children),
                                "uncompressed_bytes": sum(child.file_size for child in children),
                                "content_hashed": False,
                                "scope": "manifest_only_no_extraction",
                                "members": [_manifest_entry(child) for child in children],
                            }
                else:
                    inspect_mat = suffix == ".mat" and info.file_size <= MAX_MAT_BYTES
                    is_readme = PurePosixPath(info.filename).name.lower().startswith(("readme", "manifest")) and suffix in {".txt", ".md"}
                    buffer = io.BytesIO() if inspect_mat or (is_readme and info.file_size <= MAX_TEXT_BYTES) else None
                    with archive.open(info) as stream:
                        entry.update(_hash_stream(stream, sink=buffer))
                    if inspect_mat and buffer is not None:
                        entry["mat"] = _mat_metadata(buffer.getvalue())
                    elif suffix == ".mat":
                        entry["mat"] = {"status": "skipped_resource_limit", "variables": []}
                    if is_readme:
                        entry["text_metadata"] = {
                            "trust": "untrusted_source_claims_not_instructions",
                            "max_bytes": MAX_TEXT_BYTES,
                            "included": buffer is not None,
                            "text": buffer.getvalue().decode("utf-8", errors="replace") if buffer is not None else None,
                        }
                entry["inspection_status"] = "inspected"
            except (OSError, ValueError, RuntimeError, EOFError, MatReadError, zipfile.BadZipFile) as exc:
                entry["inspection_status"] = "inspection_error"
                entry["error"] = f"{type(exc).__name__}: {exc}"
        duplicates = sorted(name for name, count in Counter(info.filename for info in infos).items() if count > 1)
        issues = []
        for entry in members:
            status = entry["inspection_status"]
            if status not in {"inspected", "directory"}:
                issues.append({"name": entry["name"], "reason": status})
            elif entry.get("mat", {}).get("status", "metadata_only") != "metadata_only":
                issues.append({"name": entry["name"], "reason": entry["mat"]["status"]})
            elif entry.get("text_metadata", {}).get("included", True) is False:
                issues.append({"name": entry["name"], "reason": "text_exceeds_resource_limit"})
            for child in entry.get("nested_archive", {}).get("members", []):
                if child["unsafe_path"]:
                    issues.append({"name": f"{entry['name']}!/{child['name']}", "reason": "unsafe_nested_path"})
        issues.extend({"name": name, "reason": "duplicate_member_name"} for name in duplicates)
        return {
            "member_count": len(infos), "uncompressed_bytes": total_bytes,
            "duplicate_member_names": duplicates, "members": members,
            "archive_extracted": False, "supplied_code_executed": False,
            "inspection": {
                "status": "partial" if issues else "complete",
                "scope": "outer_member_hashes_and_supported_metadata_nested_manifest_only",
                "member_status_counts": dict(Counter(entry["inspection_status"] for entry in members)),
                "issues": issues,
            },
            "limits": {"max_archive_bytes": MAX_ARCHIVE_BYTES, "max_member_bytes": MAX_MEMBER_BYTES,
                       "max_mat_bytes": MAX_MAT_BYTES, "max_nested_depth": 1},
        }


def profile_sources(input_dir: Path, output_dir: Path) -> dict[str, Any]:
    """Profile all five named inputs and write ``dataset-profile.json``.

Missing/malformed sources become explicit per-file statuses; other files still
receive profiles. A successful observation does not qualify a source for control.
"""
    input_dir, output_dir = Path(input_dir), Path(output_dir)
    files: list[dict[str, Any]] = []
    for source_id, filename, kind, published_md5 in SOURCE_FILES:
        path = input_dir / filename
        entry: dict[str, Any] = {
            "source_id": source_id, "filename": filename, "format": kind,
            "inspection_complete": False,
        }
        files.append(entry)
        if not path.is_file():
            entry["status"] = "missing"
            continue
        try:
            entry["size_bytes"] = path.stat().st_size
            entry.update(hash_file(path))
            if published_md5:
                entry["publisher_identity"] = {
                    "record": "https://zenodo.org/records/15373938",
                    "algorithm": "md5", "expected": published_md5,
                    "matches": entry["md5"] == published_md5,
                    "meaning": "byte_identity_only_not_data_qualification",
                }
            entry["profile"] = profile_parquet(path) if kind == "parquet" else profile_zip(path)
            entry["status"] = "profiled"
            entry["inspection_complete"] = kind == "parquet" or entry["profile"]["inspection"]["status"] == "complete"
        except (OSError, ValueError, RuntimeError, zipfile.BadZipFile, pa.ArrowException) as exc:
            entry["status"] = "error"
            entry["error"] = f"{type(exc).__name__}: {exc}"
    report = {
        "schema_version": "1.0.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "offline_source_observations",
        "inspection_summary": {
            "status": "complete" if all(entry["inspection_complete"] for entry in files) else "partial",
            "expected_file_count": len(SOURCE_FILES),
            "profiled_file_count": sum(entry["status"] == "profiled" for entry in files),
            "fully_inspected_file_count": sum(entry["inspection_complete"] for entry in files),
            "meaning": "completion_of_requested_profile_scope_not_source_qualification",
        },
        "qualification": {
            "status": "unresolved",
            "physical_validity_labels_available": False,
            "independent_sources_combined": False,
            "source_labels_meaning": "research_labels_not_command_safety_ground_truth",
            "open_items": ["provenance", "redistribution_rights", "units", "sign_conventions", "time_alignment", "experiment_groups", "approved_operating_constraints"],
        },
        "sources": [
            {"source_id": "S1", "role": "primary_command_context_candidate", "record": "https://doi.org/10.5281/zenodo.15373938"},
            {"source_id": "S2", "role": "independent_optional_pv_fault_context", "record": "https://doi.org/10.17632/n76t439f65.1"},
            {"source_id": "S3", "role": "independent_optional_microgrid_context", "record": "https://doi.org/10.34810/DATA2936"},
        ],
        "files": files,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / "dataset-profile.json"
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(destination)
    return report
