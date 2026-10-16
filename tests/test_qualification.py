import hashlib
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from ai_command_gateway.datasets import SOURCE_FILES
from ai_command_gateway.qualification import (
    analyze_parquet, canonical_sha256, evidence_sha256, qualify_sources, report_sha256,
)


def inventory_for(tmp_path, sources):
    rows = []
    for source_id, filename, kind, _ in SOURCE_FILES:
        payload = (sources / filename).read_bytes() if (sources / filename).exists() else b"missing"
        rows.append({"source_id": source_id, "filename": filename, "format": kind,
                     "size_bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()})
    path = tmp_path / "inventory.json"
    path.write_text(json.dumps({"schema_version": "1.0.0", "files": rows}))
    return path


def test_timestamp_full_order_duplicates_null_boundaries_and_timezone(tmp_path):
    path = tmp_path / "time.parquet"
    pq.write_table(pa.table({
        "naive": pa.array([0, 0, None, 2, 1, 0, 100], type=pa.timestamp("ns")),
        "aware": pa.array([0, 0, None, 2, 1, 0, 100], type=pa.timestamp("ns", "+01:00")),
    }), path, row_group_size=2)
    result = analyze_parquet(path, batch_rows=2)
    times = [column["timestamp"] for column in result["columns"]]
    assert result["scanned_row_count"] == result["row_count"] == 7
    assert times[0]["stored_timezone"] is None
    assert times[1]["stored_timezone"] == "+01:00"
    assert times[0]["timezone_inferred"] is False
    assert times[0]["time_range"]["max"].endswith(".000000100")
    assert times[1]["time_range"]["max"].endswith(".000000100+0100")
    for time in times:
        assert time["adjacent_pairs"] == {"total": 6, "evaluable": 4, "skipped_due_to_null": 2,
                                          "increasing": 1, "decreasing": 2, "equal": 1}
        assert time["unique_timestamp_count"] == 4
        assert time["duplicate_timestamp_row_count"] == 2
        assert time["nondecreasing_over_all_rows"] is None
        assert time["positive_adjacent_delta_distribution"]["p50"] == 100


def test_cadence_gap_is_descriptive_and_positive_delta_quantiles_are_exact(tmp_path):
    path = tmp_path / "cadence.parquet"
    pq.write_table(pa.table({"time": pa.array([0, 1, 2, 3, 23], type=pa.timestamp("us"))}), path)
    result = analyze_parquet(path, batch_rows=1)["columns"][0]["timestamp"]
    assert result["nondecreasing_over_all_rows"] is True
    assert result["cadence_unit"] == "us"
    assert result["positive_adjacent_delta_distribution"] == {
        "count": 4, "min": 1, "p50": 1, "p95": 20, "p99": 20, "max": 20, "quantile_method": "nearest_rank"}
    assert result["gap_observation"]["threshold_ticks"] == 10
    assert result["gap_observation"]["count"] == 1
    assert result["gap_observation"]["meaning"] == "descriptive_outliers_not_proven_missing_samples"


def test_nonadjacent_duplicate_and_int64_timestamp_interval_do_not_overflow(tmp_path):
    path = tmp_path / "extremes.parquet"
    pq.write_table(pa.table({"time": pa.array([-(2**63) + 1, 2**63 - 1, -(2**63) + 1], type=pa.timestamp("ns"))}), path)
    result = analyze_parquet(path)["columns"][0]["timestamp"]
    assert result["positive_adjacent_delta_distribution"]["max"] == 2**64 - 2
    assert result["duplicate_timestamp_row_count"] == 1
    assert result["adjacent_pairs"]["decreasing"] == 1
    assert result["nondecreasing_over_all_rows"] is False


def test_numeric_quality_and_schema_only_payload_no_scaling(tmp_path, monkeypatch):
    path = tmp_path / "numbers.parquet"
    pq.write_table(pa.table({"power": [0.0, 500000.0, None, float("nan"), float("inf"), -1.0],
                             "packet": [b"PRIVATE_PAYLOAD"] * 6, "text": ["PRIVATE_TEXT"] * 6}), path)
    original = pq.ParquetFile

    class SelectedParquet:
        def __init__(self, path):
            self.parquet = original(path)
            self.metadata, self.schema_arrow = self.parquet.metadata, self.parquet.schema_arrow
        def __enter__(self):
            return self
        def __exit__(self, *args):
            self.parquet.close()
        def iter_batches(self, **kwargs):
            assert kwargs["columns"] == ["power"]
            return self.parquet.iter_batches(**kwargs)

    monkeypatch.setattr("ai_command_gateway.qualification.pq.ParquetFile", SelectedParquet)
    result = analyze_parquet(path, batch_rows=2)
    numeric, binary, text = result["columns"]
    assert numeric["numeric"] == {"finite_count": 3, "nonfinite_count": 2, "min": -1.0, "max": 500000.0}
    assert numeric["null_count"] == 1
    assert numeric["engineering_semantics"]["scale"] is None
    assert binary["scan_status"] == text["scan_status"] == "schema_only"
    assert binary["null_count"] is None
    assert "PRIVATE" not in json.dumps(result, allow_nan=False)


def test_empty_and_all_null_columns_are_explicit(tmp_path):
    path = tmp_path / "empty.parquet"
    pq.write_table(pa.table({"time": pa.array([], type=pa.timestamp("ns")), "value": pa.array([], type=pa.float64())}), path)
    empty = analyze_parquet(path)
    assert empty["status"] == "complete"
    assert empty["columns"][0]["timestamp"]["nondecreasing_over_all_rows"] is None
    assert empty["columns"][0]["timestamp"]["positive_adjacent_delta_distribution"] is None
    assert empty["columns"][1]["null_count"] == 0
    pq.write_table(pa.table({"time": pa.array([None, None], type=pa.timestamp("ns"))}), path)
    result = analyze_parquet(path)["columns"][0]["timestamp"]
    assert result["unique_timestamp_count"] == result["duplicate_timestamp_row_count"] == 0
    assert result["adjacent_pairs"]["skipped_due_to_null"] == 1


def test_timestamp_memory_cap_reports_partial_not_sampled(tmp_path):
    path = tmp_path / "large.parquet"
    pq.write_table(pa.table({"time": pa.array([0, 1, 2], type=pa.timestamp("ns")), "value": [1, 2, 3]}), path)
    result = analyze_parquet(path, max_timestamp_rows=2)
    assert result["status"] == "partial"
    assert result["columns"][0]["timestamp"]["status"] == "skipped_resource_limit"
    assert result["columns"][0]["scanned_row_count"] == 0
    assert result["columns"][1]["scanned_row_count"] == 3


def test_identity_bound_report_and_stable_evidence_hashes(tmp_path):
    sources = tmp_path / "sources"
    sources.mkdir()
    for _, filename, kind, _ in SOURCE_FILES:
        if kind == "parquet":
            pq.write_table(pa.table({"time": pa.array([0, 1], type=pa.timestamp("ns")), "value": [1, 2]}), sources / filename)
        else:
            (sources / filename).write_bytes(b"archive identity only")
    inventory = inventory_for(tmp_path, sources)
    report = qualify_sources(sources, tmp_path / "output", inventory)
    rerun = qualify_sources(sources, tmp_path / "output", inventory)
    assert report["inspection_summary"]["status"] == "complete"
    assert report["inspection_summary"]["matched_file_count"] == 5
    assert report["inspection_summary"]["analyzed_parquet_count"] == 3
    assert report["qualification"]["status"] == "unresolved"
    assert report["qualification"]["physical_limits_learned"] is False
    assert all(entry["status"] == "identity_verified_only" for entry in report["files"][3:])
    assert report["report_sha256"] == rerun["report_sha256"] == report_sha256(report)
    assert len(report["evidence"]) == 6
    assert report["evidence"] == rerun["evidence"]
    assert all(evidence_sha256(fact) == fact["evidence_sha256"] for fact in report["evidence"])
    assert len({fact["evidence_id"] for fact in report["evidence"]}) == 6
    assert json.loads((tmp_path / "output" / "source-qualification.json").read_text()) == rerun
    assert canonical_sha256({"b": 1, "a": 2}) == canonical_sha256({"a": 2, "b": 1})


def test_mismatch_missing_and_corrupt_inputs_are_not_evidence(tmp_path):
    sources = tmp_path / "sources"
    sources.mkdir()
    raw = sources / "logs_dataset.parquet"
    pq.write_table(pa.table({"value": [1]}), raw)
    (sources / "packets_dataset.parquet").write_bytes(b"corrupt")
    inventory = inventory_for(tmp_path, sources)
    raw.write_bytes(b"changed")
    result = qualify_sources(sources, tmp_path / "output", inventory)
    assert [entry["status"] for entry in result["files"]] == ["identity_mismatch", "error", "missing", "missing", "missing"]
    assert result["inspection_summary"]["status"] == "partial"
    assert result["evidence"] == []
    assert all("analysis" not in entry for entry in result["files"])


@pytest.mark.parametrize("failure", ["missing", "malformed", "duplicate", "wrong_source", "wrong_hash"])
def test_invalid_inventory_blocks_all_source_analysis(tmp_path, failure):
    sources = tmp_path / "sources"
    sources.mkdir()
    path = inventory_for(tmp_path, sources)
    value = json.loads(path.read_text())
    if failure == "missing":
        path.unlink()
    elif failure == "malformed":
        path.write_text("not json")
    else:
        if failure == "duplicate":
            value["files"][1] = value["files"][0]
        elif failure == "wrong_source":
            value["files"][0]["source_id"] = "S2"
        else:
            value["files"][0]["sha256"] = "bad"
        path.write_text(json.dumps(value))
    result = qualify_sources(sources, tmp_path / "output", path)
    assert result["inventory"]["status"] == "error"
    assert all(entry["status"] == "inventory_error" for entry in result["files"])
    assert result["evidence"] == []


def test_source_changed_during_analysis_discards_all_observations(tmp_path, monkeypatch):
    sources = tmp_path / "sources"
    sources.mkdir()
    raw = sources / "logs_dataset.parquet"
    pq.write_table(pa.table({"value": [1]}), raw)
    inventory = inventory_for(tmp_path, sources)
    real_analyze = analyze_parquet
    def changing_analyze(path):
        result = real_analyze(path)
        path.write_bytes(b"changed while scanning")
        return result
    monkeypatch.setattr("ai_command_gateway.qualification.analyze_parquet", changing_analyze)
    result = qualify_sources(sources, tmp_path / "output", inventory)
    assert result["files"][0]["status"] == "changed_during_analysis"
    assert result["files"][0]["identity"]["matches"] is False
    assert "analysis" not in result["files"][0]
    assert result["evidence"] == []
