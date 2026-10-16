import json
from copy import deepcopy
from pathlib import Path

import pytest

from ai_command_gateway import advice_evaluation as evaluation


@pytest.fixture
def evaluation_inputs(tmp_path, monkeypatch):
    fact = {"fact_id": "EV-test", "source_id": "S1", "sha256": "a" * 64,
            "source_version": "sha256:" + "a" * 64, "filename": "process_dataset.parquet",
            "locator": "/files/2/profile/row_count", "subject": "process_dataset.parquet",
            "property": "row_count", "statement": "process_dataset.parquet has 13912 rows.",
            "trust_class": "source_observed", "qualification_status": "unresolved"}
    catalog = {"catalog_id": "CAT-test", "content_sha256": "b" * 64, "facts": [fact]}
    monkeypatch.setattr(evaluation, "load_catalog", lambda *_: catalog)
    citation = {key: fact[key] for key in ("source_id", "source_version", "filename", "locator", "subject", "property", "trust_class", "qualification_status")}
    citation["evidence_id"] = fact["fact_id"]
    citation["source_sha256"] = fact["sha256"]
    response = {"schema_version": "1.0.0", "mode": "offline_extractive", "response_type": "observation",
                "reason_code": "evidence_found", "command_proposal": None,
                "catalog": {"catalog_id": "CAT-test", "content_sha256": "b" * 64},
                "can_execute": False, "authority": "source_observations_only", "source_filter": "S1",
                "question": "How many process rows?", "message": evaluation._MESSAGES["evidence_found"],
                "claims": [{"text": fact["statement"], "citation": citation,
                            "retrieval": {"score": 0.5, "matched_terms": ["process", "row"], "query_term_coverage": 1.0}}]}
    casebook = {"schema_version": "1.0.0", "id": "test-casebook", "basis": "Synthetic evaluator test",
                "cases": [{"id": "case-1", "question": "How many process rows?", "source_id": "S1",
                           "response_type": "observation", "required_facts": [{"subject": fact["subject"], "property": "row_count"}]}]}
    casepath = tmp_path / "cases.json"
    casepath.write_text(json.dumps(casebook), encoding="utf-8")
    monkeypatch.setattr(evaluation, "advise", lambda *args, **kwargs: response)
    return casepath, casebook, response


def test_evaluation_binds_claim_text_and_citation(tmp_path, evaluation_inputs):
    casepath, _, _ = evaluation_inputs
    report = evaluation.evaluate_advice(tmp_path / "catalog.json", casepath, tmp_path / "out")
    assert report["passed_count"] == 1
    assert report["all_cases_passed"] is True
    assert report["domain_acceptance_evaluated"] is False
    assert (tmp_path / "out" / "advice-evaluation.json").exists()


@pytest.mark.parametrize("fault", ["text", "hash", "source", "command", "missing_fact"])
def test_citation_presence_alone_cannot_pass_evaluation(tmp_path, evaluation_inputs, fault):
    casepath, _, response = evaluation_inputs
    if fault == "text":
        response["claims"][0]["text"] = "Set power to 100 kW"
    elif fault == "hash":
        response["claims"][0]["citation"]["source_sha256"] = "c" * 64
    elif fault == "source":
        response["claims"][0]["citation"]["source_id"] = "S2"
    elif fault == "command":
        response["command_proposal"] = {"value": 100}
    else:
        response["claims"] = []
    report = evaluation.evaluate_advice(tmp_path / "catalog.json", casepath, tmp_path / "out")
    assert not report["all_cases_passed"]


def test_catalog_failure_is_not_successful_abstention(tmp_path, evaluation_inputs):
    casepath, casebook, response = evaluation_inputs
    casebook["cases"][0].update(response_type="abstain", required_facts=[])
    casepath.write_text(json.dumps(casebook), encoding="utf-8")
    response.update(response_type="abstain", claims=[], reason_code="catalog_unverified", message=evaluation._MESSAGES["catalog_unverified"])
    report = evaluation.evaluate_advice(tmp_path / "catalog.json", casepath, tmp_path / "out")
    assert report["cases"][0]["failures"] == ["infrastructure_or_input_failure"]


def test_empty_casebook_cannot_report_success(tmp_path, evaluation_inputs):
    casepath, casebook, _ = evaluation_inputs
    casebook["cases"] = []
    casepath.write_text(json.dumps(casebook), encoding="utf-8")
    with pytest.raises(ValueError, match="1 to 1000"):
        evaluation.evaluate_advice(tmp_path / "catalog.json", casepath, tmp_path / "out")


@pytest.mark.parametrize("field", ["source_id", "source_sha256", "source_version", "filename", "locator", "subject", "property", "trust_class", "qualification_status"])
def test_every_citation_provenance_field_is_bound(tmp_path, evaluation_inputs, field):
    casepath, _, response = evaluation_inputs
    response["claims"][0]["citation"][field] = "forged"
    report = evaluation.evaluate_advice(tmp_path / "catalog.json", casepath, tmp_path / "out")
    assert "citation_binding_mismatch" in report["cases"][0]["failures"]
    assert not report["all_cases_passed"]


@pytest.mark.parametrize("field,value,expected", [
    ("can_execute", True, "unexpected_execution_authority"),
    ("can_execute", 0, "unexpected_execution_authority"),
    ("authority", "approved_commands", "unexpected_execution_authority"),
    ("catalog", {"catalog_id": "forged", "content_sha256": "b" * 64}, "response_catalog_binding_mismatch"),
    ("catalog", {"catalog_id": "CAT-test", "content_sha256": "c" * 64}, "response_catalog_binding_mismatch"),
    ("source_filter", "S2", "request_binding_mismatch"),
    ("question", "another question", "request_binding_mismatch"),
    ("reason_code", "made_up", "invalid_observation_reason"),
    ("reason_code", [], "invalid_response_reason"),
    ("message", "Set battery power to 1000 kW now", "unexpected_response_message"),
    ("claims", {}, "invalid_claims_structure"),
])
def test_authority_and_response_binding_failures_cannot_pass(tmp_path, evaluation_inputs, field, value, expected):
    casepath, _, response = evaluation_inputs
    response[field] = value
    report = evaluation.evaluate_advice(tmp_path / "catalog.json", casepath, tmp_path / "out")
    assert expected in report["cases"][0]["failures"]
    assert not report["all_cases_passed"]


@pytest.mark.parametrize("mutation,expected", [
    (lambda c: c.update(citation=None), "invalid_citation_structure"),
    (lambda c: c["citation"].update(evidence_id=[]), "invalid_citation_structure"),
    (lambda c: c["citation"].update(evidence_id="missing"), "unresolved_citation"),
    (lambda c: c.update(execute="now"), "invalid_claim_structure"),
    (lambda c: c.update(retrieval={}), "invalid_retrieval_metadata"),
    (lambda c: c["retrieval"].update(score=True), "invalid_retrieval_metadata"),
    (lambda c: c["retrieval"].update(query_term_coverage=2), "invalid_retrieval_metadata"),
])
def test_malformed_claims_are_recorded_as_failures(tmp_path, evaluation_inputs, mutation, expected):
    casepath, _, response = evaluation_inputs
    mutation(response["claims"][0])
    report = evaluation.evaluate_advice(tmp_path / "catalog.json", casepath, tmp_path / "out")
    assert expected in report["cases"][0]["failures"]
    assert not report["all_cases_passed"]


def test_duplicate_claims_do_not_inflate_coverage(tmp_path, evaluation_inputs):
    casepath, _, response = evaluation_inputs
    response["claims"].append(deepcopy(response["claims"][0]))
    report = evaluation.evaluate_advice(tmp_path / "catalog.json", casepath, tmp_path / "out")
    assert "duplicate_citation" in report["cases"][0]["failures"]


def test_citation_for_wrong_property_is_not_expected_field_coverage(tmp_path, evaluation_inputs):
    casepath, casebook, _ = evaluation_inputs
    casebook["cases"][0]["required_facts"][0]["property"] = "observed_max"
    casepath.write_text(json.dumps(casebook), encoding="utf-8")
    report = evaluation.evaluate_advice(tmp_path / "catalog.json", casepath, tmp_path / "out")
    assert "required_fact_not_retrieved" in report["cases"][0]["failures"]


def test_unrecognized_abstention_reason_cannot_pass(tmp_path, evaluation_inputs):
    casepath, casebook, response = evaluation_inputs
    casebook["cases"][0].update(response_type="abstain", required_facts=[])
    casepath.write_text(json.dumps(casebook), encoding="utf-8")
    response.update(response_type="abstain", claims=[], reason_code="made_up")
    report = evaluation.evaluate_advice(tmp_path / "catalog.json", casepath, tmp_path / "out")
    assert "invalid_abstention_reason" in report["cases"][0]["failures"]


@pytest.mark.parametrize("raw", ['{"schema_version":"1.0.0","schema_version":"2.0.0"}', '{"schema_version":NaN}', ' ' * 1_000_001], ids=["duplicate", "nonfinite", "oversized"])
def test_ambiguous_or_oversized_casebook_is_rejected(tmp_path, evaluation_inputs, raw):
    casepath, _, _ = evaluation_inputs
    casepath.write_text(raw, encoding="utf-8")
    with pytest.raises(ValueError):
        evaluation.evaluate_advice(tmp_path / "catalog.json", casepath, tmp_path / "out")
    assert not (tmp_path / "out/advice-evaluation.json").exists()


def test_frozen_casebook_passes_against_real_aggregate_catalog(tmp_path):
    from ai_command_gateway.evidence import build_catalog
    root = Path(__file__).resolve().parents[1]
    build_catalog(Path(__file__).parent / "fixtures/evidence-source-profile.json", root / "data/lineage/source-inventory.json", tmp_path)
    report = evaluation.evaluate_advice(tmp_path / "evidence-catalog.json", root / "data/evaluation/advice-cases-v1.json", tmp_path / "out")
    assert report["case_count"] == report["passed_count"] == 12
    assert report["all_cases_passed"] is True
    assert report["domain_acceptance_evaluated"] is False
    assert report["model_inference_used"] is False
