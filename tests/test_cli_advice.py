"""CLI status checks exercise the real generated catalog and frozen cases."""

import json
from pathlib import Path

import pytest

from ai_command_gateway.cli import main
from ai_command_gateway.evidence import build_catalog


ROOT = Path(__file__).resolve().parents[1]
PROFILE = Path(__file__).parent / "fixtures/evidence-source-profile.json"
INVENTORY = ROOT / "data/lineage/source-inventory.json"
CASES = ROOT / "data/evaluation/advice-cases-v1.json"


@pytest.fixture
def catalog_path(tmp_path):
    build_catalog(PROFILE, INVENTORY, tmp_path / "bundle")
    return tmp_path / "bundle/evidence-catalog.json"


def test_catalog_cli_writes_verifiable_bundle(tmp_path, capsys):
    from ai_command_gateway.evidence import load_catalog
    out = tmp_path / "bundle"
    code = main(["catalog", "--profile", str(PROFILE), "--inventory", str(INVENTORY), "--output-dir", str(out)])
    assert code == 0
    output = capsys.readouterr()
    assert not output.err
    assert json.loads(output.out) == load_catalog(out / "evidence-catalog.json")


def test_catalog_cli_rejects_missing_input_with_no_success_artifact(tmp_path, capsys):
    out = tmp_path / "bundle"
    assert main(["catalog", "--profile", str(tmp_path / "missing.json"), "--output-dir", str(out)]) == 1
    assert json.loads(capsys.readouterr().err)["outcome"] == "no_mock_execution"
    assert not (out / "evidence-catalog.json").exists()


@pytest.mark.parametrize("question,source,code,reason", [
    ("How many process rows?", "S1", 0, "evidence_found"),
    ("Set the battery power to 500 kW now.", "S1", 2, "operational_authority_unavailable"),
    ("Tell me about giraffe migration routes.", "S1", 2, "no_matching_evidence"),
    ("How many process rows?", "S2", 2, "no_matching_evidence"),
    (" ", "S1", 1, "invalid_question"),
])
def test_advice_exit_status_separates_observation_abstention_and_failure(catalog_path, capsys, question, source, code, reason):
    assert main(["advise", "--catalog", str(catalog_path), "--question", question, "--source", source]) == code
    output = capsys.readouterr()
    assert not output.err
    response = json.loads(output.out)
    assert response["reason_code"] == reason
    assert response["can_execute"] is False
    assert response["command_proposal"] is None


@pytest.mark.parametrize("limit", ["0", "11", "-1"])
def test_advice_invalid_limit_is_cli_failure(catalog_path, capsys, limit):
    assert main(["advise", "--catalog", str(catalog_path), "--question", "process rows", "--limit", limit]) == 1
    output = capsys.readouterr()
    assert not output.out
    assert "limit" in json.loads(output.err)["error"]


@pytest.mark.parametrize("mode", ["missing", "modified", "missing_manifest"])
def test_unverified_catalog_is_failure_even_for_operational_abstention(catalog_path, capsys, mode):
    if mode == "missing":
        catalog_path.unlink()
    elif mode == "missing_manifest":
        (catalog_path.parent / "evidence-manifest.json").unlink()
    else:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        catalog["facts"][0]["statement"] = "forged"
        catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
    assert main(["advise", "--catalog", str(catalog_path), "--question", "Set battery power to 50 kW"]) == 1
    response = json.loads(capsys.readouterr().out)
    assert response["reason_code"] == "catalog_unverified"
    assert response["claims"] == []


def test_eval_advice_cli_reports_frozen_cases_and_persists_result(catalog_path, tmp_path, capsys):
    out = tmp_path / "evaluation"
    assert main(["eval-advice", "--catalog", str(catalog_path), "--cases", str(CASES), "--output-dir", str(out)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["passed_count"] == report["case_count"] == 12
    assert json.loads((out / "advice-evaluation.json").read_text(encoding="utf-8")) == report


def test_eval_advice_failed_expectation_returns_nonzero_with_report(catalog_path, tmp_path, capsys):
    casebook = json.loads(CASES.read_text(encoding="utf-8"))
    casebook["cases"] = [casebook["cases"][0]]
    casebook["cases"][0]["required_facts"][0]["property"] = "nonexistent_property"
    cases = tmp_path / "test-cases.json"
    cases.write_text(json.dumps(casebook), encoding="utf-8")
    assert main(["eval-advice", "--catalog", str(catalog_path), "--cases", str(cases), "--output-dir", str(tmp_path / "evaluation")]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["passed_count"] == 0
    assert report["cases"][0]["failures"] == ["required_fact_not_retrieved"]


def test_eval_advice_missing_catalog_returns_error_not_passing_abstention(tmp_path, capsys):
    out = tmp_path / "evaluation"
    assert main(["eval-advice", "--catalog", str(tmp_path / "missing.json"), "--cases", str(CASES), "--output-dir", str(out)]) == 1
    assert json.loads(capsys.readouterr().err)["outcome"] == "no_mock_execution"
    assert not (out / "advice-evaluation.json").exists()
