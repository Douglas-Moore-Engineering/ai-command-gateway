"""Exercise the unqualified-policy gate using actual, unmapped S1 observations."""

from collections import Counter
import hashlib
import json
import math
from pathlib import Path

from .gateway import Gateway


def replay_process(input_dir: Path, output_dir: Path, policy_path: Path,
                   db_path: Path, limit: int = 20) -> dict:
    import pyarrow.parquet as pq

    if type(limit) is not int or not 1 <= limit <= 10_000:
        raise ValueError("Replay limit must be between 1 and 10000")
    policy = json.loads(Path(policy_path).read_text(encoding="utf-8"))
    if type(policy) is not dict or policy.get("status") != "unqualified":
        raise ValueError("Historical replay requires an unqualified policy; units and asset mapping remain unresolved")
    source = Path(input_dir) / "process_dataset.parquet"
    digest = hashlib.sha256()
    with source.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    sha256 = digest.hexdigest()
    with pq.ParquetFile(source) as parquet:
        return _replay_rows(parquet, source, sha256, output_dir, policy_path, db_path, limit)


def _replay_rows(parquet, source: Path, sha256: str, output_dir: Path,
                 policy_path: Path, db_path: Path, limit: int) -> dict:
    import pyarrow as pa

    required = {"archive_recv_ts", "out_batt_target_power"}
    if not required.issubset(parquet.schema_arrow.names):
        raise ValueError("S1 process source lacks archive_recv_ts or out_batt_target_power")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    gateway = Gateway(db_path, policy_path)
    decisions = Counter()
    reasons = Counter()
    qualification_events = 0
    row_number = 0
    evidence_file = output_dir / "observations.jsonl"
    with evidence_file.open("w", encoding="utf-8") as handle:
        for batch in parquet.iter_batches(batch_size=min(limit, 512)):
            # Preserve nanosecond precision and timezone absence; no inferred UTC mapping.
            arrays = [column.cast(pa.string()) if pa.types.is_temporal(field.type) else column
                      for column, field in zip(batch.columns, batch.schema)]
            rows = pa.RecordBatch.from_arrays(arrays, names=batch.schema.names).to_pylist()
            for raw in rows:
                raw = {key: None if isinstance(value, float) and not math.isfinite(value) else value
                       for key, value in raw.items()}
                reference = {"id": f"S1-process-{sha256}", "version": sha256}
                request = {
                    "proposal": {"id": f"S1-{sha256}-row-{row_number}",
                                 "asset_id": "S1-battery-unqualified", "action": "set_battery_power",
                                 "value": raw["out_batt_target_power"], "unit": "UNQUALIFIED",
                                 "model_version": "recorded-output:not-inference", "source_refs": [reference]},
                    "state": {"asset_id": "S1-battery-unqualified",
                              "observed_at": raw["archive_recv_ts"], "mode": "UNQUALIFIED", "values": {}},
                }
                result = gateway.evaluate(request)
                decisions[result["decision"]] += 1
                result_reasons = {reason["code"] for reason in result["reasons"]}
                reasons.update(result_reasons)
                # Infrastructure failure is a refusal, not evidence that the
                # intended qualification rule was durably exercised.
                if (result["decision"] == "escalate" and result.get("event_id")
                        and "policy_unqualified" in result_reasons):
                    qualification_events += 1
                record = {"source_id": "S1", "source_file": source.name, "sha256": sha256,
                          "row_index": row_number, "observation": raw, "request": request,
                          "qualification": "unmapped units, mode, timezone and asset; historical context only",
                          "result": result}
                handle.write(json.dumps(record, allow_nan=False) + "\n")
                row_number += 1
                if row_number >= limit:
                    break
            if row_number >= limit:
                break
    summary = {
        "source_id": "S1", "source_file": source.name, "sha256": sha256,
        "total_source_rows": parquet.metadata.num_rows, "rows_replayed": row_number,
        "sampling": "first N rows in storage order, not a representative evaluation split",
        "decisions": dict(decisions), "expected_behavior": "escalate pending source and policy qualification",
        "reason_counts": dict(reasons), "durable_qualification_events": qualification_events,
        "qualification_gate_exercised": row_number > 0 and qualification_events == row_number,
        "physical_command_validity_evaluated": False, "ground_truth_used": False,
        "observations_file": str(evidence_file), "audit_db": str(db_path),
    }
    (output_dir / "replay-summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary
