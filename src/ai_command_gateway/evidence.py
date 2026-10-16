"""Deterministic local evidence from bounded, typed source observations.

Checksums detect inconsistent local artifacts; they are not signatures. The
profiler, inventory, code and generated manifest remain a trusted local boundary.
No document text, operating limit or permission enters this catalog.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any


SCHEMA_VERSION = "1.0.0"
MAX_JSON_BYTES = 8 * 1024 * 1024
DEFAULT_INVENTORY = Path(__file__).resolve().parents[2] / "data/lineage/source-inventory.json"
# Changing the dataset version requires an explicit code/inventory revision.
PINNED_SOURCES = {
    "logs_dataset.parquet": ("S1", "parquet", 123121, "5ea386a66b4ee5c0c5602f3e70e6c118d6d5e208cabf0d99e9c4110b84e4352d"),
    "packets_dataset.parquet": ("S1", "parquet", 201835803, "5121f480c174f845d243560e8f112ea2ba43dc2922a9f563309cd7c10166ead2"),
    "process_dataset.parquet": ("S1", "parquet", 359657, "163613e85346c8913e423014e9c8911a3407dab2456cc10819e6ee9dad2ee7d8"),
    "n76t439f65-1.zip": ("S2", "zip", 203108810, "f1494903e3c3ff1ea2972af0daa9793f579b2ac444455bdd5035ebee05b8a042"),
    "doi-10.34810-data2936.zip": ("S3", "zip", 904073, "e4fcab2139c77dca64eed45b95adc4fa41d96c17e810d22d89d2d55fc5acdf5e"),
}
KNOWN_COLUMNS = {
    "logs_dataset.parquet": ("server_recv_ts", "device_ts", "hostname", "field_name", "old_value", "new_value", "__index_level_0__"),
    "packets_dataset.parquet": ("timestamp", "packet", "label", "datamod_changes", "s7_datablock"),
    "process_dataset.parquet": (
        "archive_recv_ts", "in_pv_temp_air", "in_pv_wind_speed", "in_pv_poa_direct",
        "in_pv_poa_diffuse", "in_pv_cell_temperature", "in_pv_inverter_ac_power",
        "in_pv_inverter_dc_power", "in_batt_state_of_charge", "in_batt_voltage",
        "in_batt_current", "in_batt_actual_charge_power", "in_batt_temperature",
        "state_batt_voltage", "state_batt_current", "state_batt_state_of_charge",
        "state_batt_stored_energy", "out_pv_on_off", "out_pv_target_power",
        "out_batt_on_off", "out_batt_target_power", "archive_id",
    ),
}
TIME_COLUMNS = {"server_recv_ts", "device_ts", "timestamp", "archive_recv_ts"}
NONNUMERIC_COLUMNS = TIME_COLUMNS | {"hostname", "field_name", "packet", "label", "datamod_changes", "s7_datablock"}
SOURCE_RECORDS = {
    "S1": ("primary_command_context_candidate", "https://doi.org/10.5281/zenodo.15373938"),
    "S2": ("independent_optional_pv_fault_context", "https://doi.org/10.17632/n76t439f65.1"),
    "S3": ("independent_optional_microgrid_context", "https://doi.org/10.34810/DATA2936"),
}


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _object(value: Any, required: set[str], optional: set[str] | None = None) -> dict[str, Any]:
    _require(type(value) is dict, "expected an object")
    _require(required <= value.keys() <= required | (optional or set()), "missing or unexpected object fields")
    return value


def _count(value: Any) -> int:
    _require(type(value) is int and 0 <= value <= 2**63 - 1, "count must be a nonnegative bounded integer")
    return value


def _finite(value: Any) -> int | float:
    _require(type(value) in {int, float} and abs(value) <= 1.7976931348623157e308 and math.isfinite(value), "observation must be a finite number")
    return value


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        _require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def _read_json(path: Path) -> tuple[dict[str, Any], str]:
    with path.open("rb") as stream:
        raw = stream.read(MAX_JSON_BYTES + 1)
    _require(len(raw) <= MAX_JSON_BYTES, "JSON input exceeds the local evidence size limit")
    try:
        value = json.loads(raw, object_pairs_hook=_pairs, parse_float=lambda value: _finite(float(value)), parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))
    except (UnicodeError, RecursionError) as exc:
        raise ValueError("invalid evidence JSON") from exc
    _require(type(value) is dict, "expected JSON object")
    return value, hashlib.sha256(raw).hexdigest()


def _source_identity(file: dict[str, Any]) -> dict[str, Any]:
    filename = file.get("filename")
    _require(type(filename) is str and filename in PINNED_SOURCES, "unknown source filename")
    source_id, file_format, size, sha256 = PINNED_SOURCES[filename]
    _require(file.get("source_id") == source_id and file.get("format") == file_format, "source identity mismatch")
    _require(type(file.get("size_bytes")) is int and file["size_bytes"] == size, "source byte count mismatch")
    _require(file.get("sha256") == sha256, "source digest differs from pinned inventory")
    return {"source_id": source_id, "filename": filename, "format": file_format, "size_bytes": size, "sha256": sha256}


def _inventory(path: Path) -> dict[str, dict[str, Any]]:
    inventory, _ = _read_json(path)
    _require(inventory.get("schema_version") == SCHEMA_VERSION, "unsupported inventory version")
    _require(inventory.get("qualification_status") == "unresolved" and inventory.get("raw_records_included") is False, "unexpected inventory qualification")
    files = inventory.get("files")
    _require(type(files) is list and len(files) == 5, "inventory must contain five source files")
    result = {}
    for file in files:
        _require(type(file) is dict, "invalid inventory file")
        identity = _source_identity(file)
        _require(identity["filename"] not in result, "duplicate inventory file")
        result[identity["filename"]] = file
    _require(set(result) == set(PINNED_SOURCES), "incomplete inventory")
    return result


def _timestamp_order_key(value: Any) -> tuple[int, int]:
    """Validate timestamp spelling and compare exact whole seconds/nanoseconds.

    datetime validates the calendar and offset at whole-second precision only;
    the fractional component stays an integer so no nanoseconds are truncated.
    Naive values are comparable within their stored clock, not asserted as UTC.
    """
    _require(type(value) is str, "invalid observed timestamp")
    match = re.fullmatch(
        r"(?P<whole>\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2})"
        r"(?:\.(?P<fraction>\d{1,9}))?(?P<offset>Z|[+-]\d{2}:?\d{2})?", value)
    _require(match is not None, "invalid observed timestamp")
    offset_text = (match["offset"] or "").replace("Z", "+00:00")
    offset_text = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", offset_text)
    parsed = datetime.fromisoformat(match["whole"] + offset_text)
    seconds = parsed.toordinal() * 86400 + parsed.hour * 3600 + parsed.minute * 60 + parsed.second
    offset = parsed.utcoffset()
    if offset is not None:
        seconds -= offset.days * 86400 + offset.seconds
    fraction = int((match["fraction"] or "0").ljust(9, "0"))
    return seconds, fraction


def _timestamp(value: Any) -> str:
    _timestamp_order_key(value)
    return value


def _column(column: Any, filename: str, rows: int, *, raw: bool) -> dict[str, Any]:
    base = {"name", "null_count", "non_null_count"}
    optional = {"numeric", "time_range", "timezone", "categories"}
    if raw:
        base |= {"arrow_type", "nullable"}
    column = _object(column, base, optional)
    name = column["name"]
    _require(type(name) is str and name in KNOWN_COLUMNS[filename], "unrecognized source column")
    if raw:
        _require(type(column["arrow_type"]) is str and len(column["arrow_type"]) <= 100, "invalid column type")
        _require(type(column["nullable"]) is bool, "invalid nullable flag")
    result = {key: column[key] for key in ("name", "null_count", "non_null_count")}
    _require(_count(column["null_count"]) + _count(column["non_null_count"]) == rows, "column counts do not cover all rows")
    if name not in NONNUMERIC_COLUMNS:
        numeric = _object(column.get("numeric"), {"finite_count", "nonfinite_count", "min", "max", "mean"})
        finite = _count(numeric["finite_count"])
        _require(finite + _count(numeric["nonfinite_count"]) == column["non_null_count"], "numeric counts do not cover non-null rows")
        if finite:
            low, high, mean = (_finite(numeric[key]) for key in ("min", "max", "mean"))
            _require(low <= high and low - max(1, abs(low)) * 1e-12 <= mean <= high + max(1, abs(high)) * 1e-12, "inconsistent numeric bounds")
        else:
            _require(all(numeric[key] is None for key in ("min", "max", "mean")), "empty numeric column must have null bounds")
        result["numeric"] = dict(numeric)
    else:
        _require("numeric" not in column, "numeric evidence on a nonnumeric column")
    if name in TIME_COLUMNS:
        time_range = _object(column.get("time_range"), {"min", "max"})
        if column["non_null_count"]:
            low, high = (_timestamp_order_key(time_range[key]) for key in ("min", "max"))
            _require(low <= high, "reversed timestamp bounds")
        else:
            _require(time_range == {"min": None, "max": None}, "empty time range requires null bounds")
        zone = column.get("timezone")
        _require(zone == ("+01:00" if name == "server_recv_ts" else None), "timestamp timezone differs from known source schema")
        if column["non_null_count"]:
            for value in time_range.values():
                suffix = re.search(r"(?:Z|[+-]\d{2}:?\d{2})$", value)
                _require((suffix is None and zone is None) or (suffix is not None and zone == "+01:00" and suffix.group() in {"+0100", "+01:00"}), "timestamp value and metadata timezone disagree")
        result.update(time_range=dict(time_range), timezone=zone)
    else:
        _require("time_range" not in column and "timezone" not in column, "time evidence on a nontime column")
    if "categories" in column:
        categories = _object(column["categories"], {"counts", "max_categories", "overflow_value_count", "scope", "meaning"})
        _require(type(categories["counts"]) is dict and len(categories["counts"]) <= 64, "invalid category counts")
        _require(categories["scope"] == "all_rows" and categories["meaning"] == "source_observation_not_physical_validity", "unqualified category semantics")
        _require(type(categories["max_categories"]) is int and categories["max_categories"] == 64, "invalid category limit")
        total = sum(_count(value) for value in categories["counts"].values())
        _require(total + _count(categories["overflow_value_count"]) == column["non_null_count"], "categories do not cover non-null rows")
        if filename == "packets_dataset.parquet" and name == "label":
            _require(set(categories["counts"]) <= {"normal", "data_modification"}, "unrecognized research label")
            result["categories"] = dict(categories)
        else:
            # Arbitrary source category strings never become evidence statements.
            _require(raw, "unexpected categories in sanitized snapshot")
    if filename == "packets_dataset.parquet" and name == "label":
        _require("categories" in result, "packet research labels missing")
    return result


def _normalize_files(files: Any, inventory: dict[str, dict[str, Any]], *, raw: bool) -> list[dict[str, Any]]:
    _require(type(files) is list and len(files) == 5, "profile must include all five sources")
    normalized = []
    names = []
    for file in files:
        keys = {"source_id", "filename", "format", "size_bytes", "sha256", "profile"}
        if raw:
            keys |= {"inspection_complete", "md5", "status"}
        _object(file, keys, {"publisher_identity"} if raw else set())
        identity = _source_identity(file)
        filename = identity["filename"]
        names.append(filename)
        if raw:
            _require(file["status"] == "profiled" and file["inspection_complete"] is True, "source profile is incomplete")
            _require(file["md5"] == inventory[filename]["md5"], "source MD5 differs from inventory")
        profile = file["profile"]
        if identity["format"] == "parquet":
            keys = {"row_count", "scanned_row_count", "column_count", "row_group_count", "columns"}
            _object(profile, keys | ({"scan", "qualification"} if raw else set()))
            for key in keys - {"columns"}:
                _require(_count(profile[key]) == inventory[filename][key], "profile count differs from inventory")
            _require(profile["scanned_row_count"] == profile["row_count"], "partial row scan")
            if raw:
                scan = _object(profile["scan"], {"scope", "batch_rows", "row_sampling", "raw_rows_emitted"})
                _require(scan["scope"] == "all_rows" and scan["row_sampling"] is False and type(scan["raw_rows_emitted"]) is int and scan["raw_rows_emitted"] == 0 and _count(scan["batch_rows"]) > 0, "incomplete or raw-row scan")
                _require(profile["qualification"] == "units_sign_conventions_time_alignment_and_experiment_groups_unresolved", "unexpected parquet qualification")
            _require(type(profile["columns"]) is list, "invalid columns")
            columns = [_column(column, filename, profile["row_count"], raw=raw) for column in profile["columns"]]
            _require(tuple(column["name"] for column in columns) == KNOWN_COLUMNS[filename], "unexpected or repeated source columns")
            clean_profile = {key: profile[key] for key in keys - {"columns"}}
            clean_profile["columns"] = columns
        else:
            keys = {"member_count", "uncompressed_bytes"}
            if raw:
                _object(profile, keys | {"members", "archive_extracted", "supplied_code_executed", "inspection", "limits"}, {"duplicate_member_names"})
                _require(profile["archive_extracted"] is False and profile["supplied_code_executed"] is False, "archive handling outside evidence boundary")
                _require(type(profile["inspection"]) is dict and profile["inspection"].get("status") == "complete", "incomplete archive inspection")
                _require(type(profile["members"]) is list and len(profile["members"]) == profile["member_count"], "archive member count mismatch")
            else:
                _object(profile, keys)
            for key in keys:
                _require(_count(profile[key]) == inventory[filename][key], "archive count differs from inventory")
            clean_profile = {key: profile[key] for key in keys}
        normalized.append({**identity, "profile": clean_profile})
    _require(names == list(PINNED_SOURCES), "unexpected or duplicate profile source order")
    return normalized


def find_conflicts(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep independent file subjects distinct; surface incompatible values."""
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for fact in facts:
        grouped[(fact["source_id"], fact["subject"], fact["property"])].append(fact)
    return [
        {"source_id": key[0], "subject": key[1], "property": key[2], "fact_ids": sorted(fact["fact_id"] for fact in group)}
        for key, group in sorted(grouped.items())
        if len({_canonical({"value": fact["value"], "units": fact["units"]}) for fact in group}) > 1
    ]


def _facts(files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    facts = []
    for index, file in enumerate(files):
        filename = file["filename"]
        profile = file["profile"]
        def add(subject: str, prop: str, value: Any, units: str, locator: str) -> None:
            # All names are code allowlisted; values are finite numbers, fixed labels
            # or validated timestamps. No source-authored statement is accepted.
            shown = "unspecified" if value is None else str(value)
            statement = f"{subject}: {prop.replace('_', ' ')} = {shown} ({units}); source observation, qualification unresolved."
            body = {
                "source_id": file["source_id"], "filename": filename, "sha256": file["sha256"],
                "source_version": "sha256:" + file["sha256"], "subject": subject,
                "property": prop, "value": value, "units": units, "locator": locator,
                "statement": statement, "kind": "observation", "status": "context_only",
                "qualification_status": "unresolved", "trust_class": "source_observed",
            }
            facts.append({"fact_id": "EV-" + _digest(body)[:24], **body})
        base = f"/files/{index}"
        add(filename, "size_bytes", file["size_bytes"], "bytes", base + "/size_bytes")
        if file["format"] == "zip":
            add(filename, "member_count", profile["member_count"], "archive_members", base + "/profile/member_count")
            add(filename, "uncompressed_bytes", profile["uncompressed_bytes"], "bytes", base + "/profile/uncompressed_bytes")
            continue
        for key, units in (("row_count", "rows"), ("column_count", "columns"), ("row_group_count", "row_groups")):
            add(filename, key, profile[key], units, base + "/profile/" + key)
        for column_index, column in enumerate(profile["columns"]):
            subject = filename + ":" + column["name"]
            loc = base + f"/profile/columns/{column_index}"
            add(subject, "null_count", column["null_count"], "rows", loc + "/null_count")
            if "numeric" in column and column["name"] not in {"__index_level_0__", "archive_id"}:
                for key in ("min", "max", "mean"):
                    add(subject, "observed_" + key, column["numeric"][key], "unresolved", loc + "/numeric/" + key)
                add(subject, "nonfinite_count", column["numeric"]["nonfinite_count"], "rows", loc + "/numeric/nonfinite_count")
            if "time_range" in column:
                for key in ("min", "max"):
                    add(subject, "time_" + key, column["time_range"][key], "timestamp_as_recorded", loc + "/time_range/" + key)
                add(subject, "timezone", column["timezone"], "timezone_metadata", loc + "/timezone")
            if "categories" in column:
                for label, count in sorted(column["categories"]["counts"].items()):
                    add(subject, "label_count:" + label, count, "rows_research_label", loc + "/categories/counts/" + label)
    return sorted(facts, key=lambda fact: (fact["source_id"], fact["subject"], fact["property"]))


def _catalog(snapshot: dict[str, Any]) -> dict[str, Any]:
    facts = _facts(snapshot["files"])
    body = {
        "schema_version": SCHEMA_VERSION, "purpose": "offline_context_only_evidence",
        "qualification_status": "unresolved", "authorizes_execution": False,
        "source_profile_sha256": snapshot["source_profile_sha256"],
        "profile_snapshot_sha256": _digest(snapshot), "inventory_sha256": snapshot["inventory_sha256"],
        "source_files": [{key: value for key, value in file.items() if key != "profile"} for file in snapshot["files"]],
        "facts": facts, "conflicts": find_conflicts(facts),
    }
    digest = _digest(body)
    return {"catalog_id": "CAT-" + digest[:24], "content_sha256": digest, **body}


def _write_json(path: Path, value: dict[str, Any]) -> str:
    raw = (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n").encode("utf-8")
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def build_catalog(profile_path: str | Path, inventory_path: str | Path, output_dir: str | Path) -> dict[str, Any]:
    """Create catalog, sanitized input snapshot and local integrity manifest."""
    profile, profile_sha = _read_json(Path(profile_path))
    _object(profile, {"schema_version", "generated_at_utc", "purpose", "inspection_summary", "qualification", "sources", "files"})
    _require(profile["schema_version"] == SCHEMA_VERSION and profile["purpose"] == "offline_source_observations", "unsupported source profile")
    _timestamp(profile["generated_at_utc"])
    _require(type(profile["sources"]) is list and len(profile["sources"]) == 3, "source registry must contain three records")
    source_ids = []
    for source in profile["sources"]:
        _object(source, {"source_id", "role", "record"})
        _require(type(source["source_id"]) is str and source["source_id"] in SOURCE_RECORDS, "unknown source record")
        _require((source["role"], source["record"]) == SOURCE_RECORDS[source["source_id"]], "source registry differs from known records")
        source_ids.append(source["source_id"])
    _require(source_ids == list(SOURCE_RECORDS), "duplicate or reordered source records")
    summary = _object(profile["inspection_summary"], {"status", "expected_file_count", "profiled_file_count", "fully_inspected_file_count", "meaning"})
    _require(summary == {"status": "complete", "expected_file_count": 5, "profiled_file_count": 5, "fully_inspected_file_count": 5, "meaning": "completion_of_requested_profile_scope_not_source_qualification"}, "source inspection incomplete")
    qualification = _object(profile["qualification"], {"status", "physical_validity_labels_available", "independent_sources_combined", "source_labels_meaning", "open_items"})
    _require(qualification["status"] == "unresolved" and qualification["physical_validity_labels_available"] is False and qualification["independent_sources_combined"] is False and qualification["source_labels_meaning"] == "research_labels_not_command_safety_ground_truth", "source qualification cannot be promoted")
    _require(type(qualification["open_items"]) is list and all(type(item) is str and item in {"provenance", "redistribution_rights", "units", "sign_conventions", "time_alignment", "experiment_groups", "approved_operating_constraints"} for item in qualification["open_items"]), "unrecognized source qualification field")
    inventory = _inventory(Path(inventory_path))
    snapshot = {
        "schema_version": SCHEMA_VERSION, "source_profile_sha256": profile_sha,
        "inventory_sha256": _digest(inventory),
        "files": _normalize_files(profile["files"], inventory, raw=True),
    }
    catalog = _catalog(snapshot)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    snapshot_sha = _write_json(out / "evidence-profile.json", snapshot)
    catalog_sha = _write_json(out / "evidence-catalog.json", catalog)
    _write_json(out / "evidence-manifest.json", {
        "schema_version": SCHEMA_VERSION, "trust_boundary": "trusted_local_files_not_signed",
        "catalog_file_sha256": catalog_sha, "snapshot_file_sha256": snapshot_sha,
        "catalog_content_sha256": catalog["content_sha256"], "source_profile_sha256": profile_sha,
        "inventory_sha256": snapshot["inventory_sha256"],
    })
    return catalog


def load_catalog(path: str | Path, *, inventory_path: str | Path = DEFAULT_INVENTORY) -> dict[str, Any]:
    """Rebuild every statement from typed input and verify local artifact linkage.

Editing all trusted local artifacts can forge the chain. This check proves
internal consistency and allowlisted content, not source or operator authenticity.
"""
    path = Path(path)
    catalog, catalog_sha = _read_json(path)
    snapshot, snapshot_sha = _read_json(path.parent / "evidence-profile.json")
    manifest, _ = _read_json(path.parent / "evidence-manifest.json")
    _object(manifest, {"schema_version", "trust_boundary", "catalog_file_sha256", "snapshot_file_sha256", "catalog_content_sha256", "source_profile_sha256", "inventory_sha256"})
    _require(manifest["schema_version"] == SCHEMA_VERSION and manifest["trust_boundary"] == "trusted_local_files_not_signed", "unsupported evidence manifest")
    _require(manifest["catalog_file_sha256"] == catalog_sha and manifest["snapshot_file_sha256"] == snapshot_sha, "local evidence manifest mismatch")
    _object(snapshot, {"schema_version", "source_profile_sha256", "inventory_sha256", "files"})
    _require(snapshot["schema_version"] == SCHEMA_VERSION, "unsupported evidence snapshot")
    _require(type(snapshot["source_profile_sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", snapshot["source_profile_sha256"]) is not None, "invalid source profile digest")
    inventory = _inventory(Path(inventory_path))
    _require(snapshot["inventory_sha256"] == manifest["inventory_sha256"] == _digest(inventory), "inventory evidence mismatch")
    _require(snapshot["source_profile_sha256"] == manifest["source_profile_sha256"], "source profile linkage mismatch")
    clean = _normalize_files(snapshot["files"], inventory, raw=False)
    _require(clean == snapshot["files"], "unexpected snapshot data")
    expected = _catalog(snapshot)
    _require(_canonical(expected) == _canonical(catalog), "catalog facts differ from deterministic source observations")
    _require(catalog["content_sha256"] == manifest["catalog_content_sha256"], "catalog content manifest mismatch")
    return catalog
