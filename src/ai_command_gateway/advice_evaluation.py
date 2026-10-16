"""Reproducible, engineer-authored retrieval regressions, not domain acceptance."""

import hashlib
import json
import math
from pathlib import Path

from .advisor import _MESSAGES, advise
from .evidence import load_catalog


def _validate_cases(document):
    if (type(document) is not dict or set(document) != {"schema_version", "id", "basis", "cases"}
            or document.get("schema_version") != "1.0.0"):
        raise ValueError("Unsupported advice casebook")
    cases = document.get("cases")
    if any(type(document.get(key)) is not str or not document[key].strip() for key in ("id", "basis")):
        raise ValueError("Advice casebook requires an ID and evidence basis")
    if type(cases) is not list or not 1 <= len(cases) <= 1000:
        raise ValueError("Casebook must contain 1 to 1000 cases")
    ids = set()
    for case in cases:
        keys = {"id", "question", "source_id", "response_type", "required_facts"}
        if type(case) is not dict or set(case) != keys:
            raise ValueError("Invalid advice case fields")
        if type(case["id"]) is not str or not case["id"] or case["id"] in ids:
            raise ValueError("Case IDs must be nonempty and unique")
        ids.add(case["id"])
        if type(case["question"]) is not str or not case["question"].strip() or len(case["question"]) > 2048:
            raise ValueError("Case questions must be nonempty strings")
        if case["source_id"] not in (None, "S1", "S2", "S3"):
            raise ValueError("Invalid source filter in casebook")
        if case["response_type"] not in ("observation", "abstain") or type(case["required_facts"]) is not list:
            raise ValueError("Invalid expected advice response")
        if (case["response_type"] == "observation") != bool(case["required_facts"]):
            raise ValueError("Observation cases require fact expectations; abstentions must have none")
        for fact in case["required_facts"]:
            if type(fact) is not dict or set(fact) != {"subject", "property"}:
                raise ValueError("Expected facts require subject and property")
            if any(type(value) is not str or not value for value in fact.values()):
                raise ValueError("Expected fact fields must be nonempty strings")


def _read_cases(path):
    with Path(path).open("rb") as stream:
        raw = stream.read(1_000_001)
    if len(raw) > 1_000_000:
        raise ValueError("Advice casebook exceeds the 1 MB input limit")

    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON key in advice casebook")
            result[key] = value
        return result

    def reject_constant(_):
        raise ValueError("Nonfinite casebook number")

    try:
        document = json.loads(raw, object_pairs_hook=unique_keys, parse_constant=reject_constant)
    except RecursionError as exc:
        raise ValueError("Advice casebook nesting exceeds the JSON input limit") from exc
    return raw, document


def _check_response(response, case, catalog, facts):
    """Fail closed on authority, provenance and typed response contract changes."""
    if type(response) is not dict:
        return ["invalid_response_structure"]
    failures = []
    required = {"schema_version", "mode", "response_type", "question", "reason_code", "message",
                "catalog", "source_filter", "claims", "command_proposal", "authority", "can_execute"}
    if set(response) != required or response.get("schema_version") != "1.0.0" or response.get("mode") != "offline_extractive":
        failures.append("invalid_response_structure")
    if response.get("response_type") != case["response_type"]:
        failures.append("unexpected_response_type")
    if response.get("command_proposal", "missing") is not None:
        failures.append("unexpected_command_proposal")
    if response.get("can_execute") is not False or response.get("authority") != "source_observations_only":
        failures.append("unexpected_execution_authority")
    if response.get("question") != case["question"] or response.get("source_filter") != case["source_id"]:
        failures.append("request_binding_mismatch")
    if response.get("catalog") != {"catalog_id": catalog["catalog_id"], "content_sha256": catalog["content_sha256"]}:
        failures.append("response_catalog_binding_mismatch")
    if type(response.get("message")) is not str or not response["message"]:
        failures.append("invalid_response_message")
    reason = response.get("reason_code")
    if type(reason) is str and response.get("message") != _MESSAGES.get(reason):
        failures.append("unexpected_response_message")
    if type(reason) is not str:
        failures.append("invalid_response_reason")
    elif reason in {"catalog_unverified", "invalid_question", "invalid_filter"}:
        failures.append("infrastructure_or_input_failure")
    elif response.get("response_type") == "observation" and reason != "evidence_found":
        failures.append("invalid_observation_reason")
    elif response.get("response_type") == "abstain" and reason not in {
            "operational_authority_unavailable", "no_matching_evidence", "conflicting_evidence", "unknown_source"}:
        failures.append("invalid_abstention_reason")
    claims = response.get("claims")
    if type(claims) is not list:
        failures.append("invalid_claims_structure")
        claims = []
    if len(claims) > 3:
        failures.append("response_limit_exceeded")
    if response.get("response_type") == "observation" and not claims:
        failures.append("observation_without_evidence")
    if response.get("response_type") == "abstain" and claims:
        failures.append("abstention_contains_claims")
    present = set()
    citation_ids = set()
    for claim in claims:
        if type(claim) is not dict or set(claim) != {"text", "citation", "retrieval"}:
            failures.append("invalid_claim_structure")
            continue
        citation = claim["citation"]
        if type(citation) is not dict or type(citation.get("evidence_id")) is not str:
            failures.append("invalid_citation_structure")
            continue
        fact = facts.get(citation["evidence_id"])
        if fact is None:
            failures.append("unresolved_citation")
            continue
        if citation["evidence_id"] in citation_ids:
            failures.append("duplicate_citation")
        citation_ids.add(citation["evidence_id"])
        if claim.get("text") != fact["statement"]:
            failures.append("claim_not_exact_catalog_observation")
        citation_keys = {"source_id": "source_id", "source_sha256": "sha256",
                         "source_version": "source_version", "filename": "filename",
                         "locator": "locator", "subject": "subject", "property": "property",
                         "trust_class": "trust_class", "qualification_status": "qualification_status"}
        if set(citation) != set(citation_keys) | {"evidence_id"} or any(citation.get(key) != fact[target] for key, target in citation_keys.items()):
            failures.append("citation_binding_mismatch")
        if case["source_id"] is not None and fact["source_id"] != case["source_id"]:
            failures.append("source_filter_leak")
        retrieval = claim["retrieval"]
        if (type(retrieval) is not dict or set(retrieval) != {"score", "matched_terms", "query_term_coverage"}
                or any(type(retrieval[key]) not in {int, float} or not 0 <= retrieval[key] <= 1
                       or not math.isfinite(retrieval[key]) for key in ("score", "query_term_coverage"))
                or type(retrieval["matched_terms"]) is not list
                or any(type(term) is not str for term in retrieval["matched_terms"])):
            failures.append("invalid_retrieval_metadata")
        present.add((fact["subject"], fact["property"]))
    if any((fact["subject"], fact["property"]) not in present for fact in case["required_facts"]):
        failures.append("required_fact_not_retrieved")
    return list(dict.fromkeys(failures))


def evaluate_advice(catalog_path: Path, cases_path: Path, output_dir: Path) -> dict:
    catalog = load_catalog(Path(catalog_path))
    case_bytes, casebook = _read_cases(cases_path)
    _validate_cases(casebook)
    facts = {fact["fact_id"]: fact for fact in catalog["facts"]}
    results = []
    for case in casebook["cases"]:
        response = advise(case["question"], Path(catalog_path), source_id=case["source_id"], limit=3)
        failures = _check_response(response, case, catalog, facts)
        results.append({"id": case["id"], "passed": not failures, "failures": failures, "response": response})
    report = {
        "schema_version": "1.0.0", "casebook_id": casebook["id"],
        "casebook_sha256": hashlib.sha256(case_bytes).hexdigest(), "basis": casebook["basis"],
        "catalog_id": catalog["catalog_id"], "catalog_sha256": catalog["content_sha256"],
        "case_count": len(results), "passed_count": sum(item["passed"] for item in results),
        "all_cases_passed": all(item["passed"] for item in results),
        "domain_acceptance_evaluated": False, "model_inference_used": False, "cases": results,
    }
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / "advice-evaluation.json"
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(destination)
    return report
