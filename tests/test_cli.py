import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from ai_command_gateway.cli import main, read_json


@pytest.mark.parametrize("content", ['{"x":NaN}', '{"x":1,"x":2}', '{"x":Infinity}', '{"x":1e999}'])
def test_strict_json_rejects_ambiguous_or_nonfinite_values(tmp_path, content):
    path = tmp_path / "request.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError):
        read_json(path)


def test_missing_request_is_machine_readable_error(tmp_path, capsys):
    code = main(["evaluate", "--request", str(tmp_path / "missing.json"), "--db", str(tmp_path / "audit.db")])
    assert code == 1
    assert json.loads(capsys.readouterr().err)["outcome"] == "no_mock_execution"


def test_demo_roundtrip(tmp_path, capsys):
    assert main(["demo", "--db", str(tmp_path / "audit.db")]) == 0
    report = json.loads(capsys.readouterr().out)
    assert all(report["checks"].values())
    assert report["execution"]["decision"] == "allow"
    assert report["replay"]["decision"] == "block"


def test_replay_preserves_source_time_and_escalates(tmp_path):
    import pyarrow as pa
    import pyarrow.parquet as pq
    from ai_command_gateway.replay import replay_process

    timestamp = pa.array([1739930834956493832], type=pa.timestamp("ns"))
    pq.write_table(pa.table({"archive_recv_ts": timestamp, "out_batt_target_power": [100.0]}),
                   tmp_path / "process_dataset.parquet")
    report = replay_process(tmp_path, tmp_path / "out", "config/policies/unqualified-policy.json",
                            tmp_path / "audit.db", limit=1)
    assert report["decisions"] == {"escalate": 1}
    record = json.loads((tmp_path / "out" / "observations.jsonl").read_text())
    assert record["observation"]["archive_recv_ts"].endswith("956493832")
    assert not record["observation"]["archive_recv_ts"].endswith("Z")
    assert record["request"]["proposal"]["unit"] == "UNQUALIFIED"


def test_replay_cannot_apply_synthetic_policy_to_source_data(tmp_path):
    from ai_command_gateway.replay import replay_process
    with pytest.raises(ValueError, match="unqualified policy"):
        replay_process(tmp_path, tmp_path / "out", "config/policies/demo-policy.json", tmp_path / "audit.db")


@pytest.mark.parametrize("fixture", ["{}", "[]", '{"proposal":null,"state":{}}'])
def test_malformed_demo_fixture_is_machine_readable_error(tmp_path, capsys, fixture):
    path = tmp_path / "request.json"
    path.write_text(fixture, encoding="utf-8")
    assert main(["demo", "--request", str(path), "--db", str(tmp_path / "audit.db")]) == 1
    assert json.loads(capsys.readouterr().err)["outcome"] == "no_mock_execution"


def test_corrupt_audit_database_is_machine_readable_error(tmp_path, capsys):
    database = tmp_path / "audit.db"
    database.write_text("corrupted SQLite database", encoding="utf-8")
    assert main(["audit", "--db", str(database)]) == 1
    assert json.loads(capsys.readouterr().err)["outcome"] == "no_mock_execution"


@pytest.mark.parametrize("decision,expected_exit", [("allow", 0), ("block", 2), ("escalate", 2)])
def test_evaluate_exit_codes_match_decision(tmp_path, capsys, decision, expected_exit):
    request = json.loads(Path("data/samples/demo-request.json").read_text(encoding="utf-8"))
    request["state"]["observed_at"] = datetime.now(timezone.utc).isoformat()
    if decision == "block":
        request["proposal"]["value"] = 500
    elif decision == "escalate":
        request["proposal"]["source_refs"] = []
    path = tmp_path / "request.json"
    path.write_text(json.dumps(request), encoding="utf-8")
    assert main(["evaluate", "--request", str(path), "--policy", "config/policies/demo-policy.json",
                 "--db", str(tmp_path / "audit.db")]) == expected_exit
    result = json.loads(capsys.readouterr().out)
    assert result["decision"] == decision
    assert result["event_id"]


@pytest.mark.parametrize("failure", ["audit_unavailable", "policy_unavailable"])
def test_replay_infrastructure_failure_is_not_successful_qualification(tmp_path, capsys, failure):
    import pyarrow as pa
    import pyarrow.parquet as pq

    pq.write_table(pa.table({"archive_recv_ts": pa.array([1739930834956493832], type=pa.timestamp("ns")),
                            "out_batt_target_power": [100.0]}), tmp_path / "process_dataset.parquet")
    policy_path = Path("config/policies/unqualified-policy.json")
    database = tmp_path if failure == "audit_unavailable" else tmp_path / "audit.db"
    if failure == "policy_unavailable":
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
        policy["valid_until"] = "2026-01-01T00:00:01Z"
        policy_path = tmp_path / "expired-policy.json"
        policy_path.write_text(json.dumps(policy), encoding="utf-8")
    assert main(["replay", "--input-dir", str(tmp_path), "--output-dir", str(tmp_path / "out"),
                 "--policy", str(policy_path), "--db", str(database), "--limit", "1"]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["decisions"] == {"escalate": 1}
    assert report["reason_counts"] == {failure: 1}
    assert report["durable_qualification_events"] == 0
    assert report["qualification_gate_exercised"] is False


def test_replay_empty_source_has_no_claimed_gate_coverage(tmp_path, capsys):
    import pyarrow as pa
    import pyarrow.parquet as pq

    pq.write_table(pa.table({"archive_recv_ts": pa.array([], type=pa.timestamp("ns")),
                            "out_batt_target_power": pa.array([], type=pa.float64())}), tmp_path / "process_dataset.parquet")
    assert main(["replay", "--input-dir", str(tmp_path), "--output-dir", str(tmp_path / "out"),
                 "--db", str(tmp_path / "audit.db")]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["rows_replayed"] == 0
    assert report["qualification_gate_exercised"] is False


@pytest.mark.parametrize("status,expected_exit", [("complete", 0), ("partial", 1)])
def test_profile_partial_inspection_has_nonzero_exit(tmp_path, capsys, monkeypatch, status, expected_exit):
    from ai_command_gateway import datasets

    report = {"files": [{"status": "profiled"}], "inspection_summary": {"status": status}}
    monkeypatch.setattr(datasets, "profile_sources", lambda *_: report)
    assert main(["profile", "--input-dir", str(tmp_path), "--output-dir", str(tmp_path / "out")]) == expected_exit
    assert json.loads(capsys.readouterr().out) == report
