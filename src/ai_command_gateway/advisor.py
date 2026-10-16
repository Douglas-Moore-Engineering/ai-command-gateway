"""Deterministic, extractive retrieval over an integrity-checked local catalog.

This module has no language-model, network, policy-writing, or execution path.
Every returned claim is a catalog statement copied verbatim with its locator.
Lexical matching is deliberately conservative, not a semantic entailment check.
The intent screen is a convenience; the observation-only response structure is
the authority boundary even for wording the screen does not recognize.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
import re
from typing import Any

from .evidence import load_catalog


_STOP = frozenset("""a an the what which how many much is are was were be been
    being do does did have has had of for from in on at to by with and or about
    tell me show give please there their this that these those it its as recorded
    observed observation observations dataset datasets data file files contain
    contains containing exist exists number value values count counts stored carry
    carries carrying""".split())
_ALIASES = {
    "rows": "row", "record": "row", "records": "row",
    "columns": "column", "fields": "column", "field": "column",
    "members": "member", "archives": "archive", "sizes": "size",
    "bytes": "byte", "timestamps": "timestamp", "times": "time",
    "nulls": "null", "missing": "null", "min": "minimum", "max": "maximum",
    "extrema": "range", "batt": "battery", "avg": "mean", "average": "mean",
    "labels": "label", "attacks": "attack", "zones": "zone",
}
_OPERATIONAL = re.compile(
    r"\b(?:recommend\w*|safe|safely|safety|approve\w*|approval|authoriz\w*|"
    r"execute\w*|override\w*|bypass\w*|ignore|instructions?|commands?|should)\b"
    r"|\b(?:can|may)\s+(?:i|we)\b"
    r"|\b(?:operating|operational|allowable|permitted)\s+(?:limits?|ranges?|power)\b"
    r"|\b(?:set|increase|decrease|change)\b.+\bto\b"
    r"|^\s*(?:run|set|charge|discharge|operate|deploy)\b",
    flags=re.IGNORECASE,
)
_MESSAGES = {
    "evidence_found": "Exact catalog observations are shown with their evidence citations.",
    "no_matching_evidence": "No verified observation set covers the requested subject and metrics within the result limit.",
    "operational_authority_unavailable": "This observation-only advisor cannot recommend or authorize equipment actions or operating limits.",
    "conflicting_evidence": "Matching observations conflict; review the underlying evidence before drawing a conclusion.",
    "unknown_source": "The requested source is absent from the verified catalog.",
    "catalog_unverified": "The evidence catalog could not be verified; no observations were returned.",
    "invalid_question": "Provide a nonempty text question of at most 2048 characters.",
    "invalid_filter": "Provide a nonempty source ID of at most 128 characters.",
}


def _terms(text: str) -> set[str]:
    terms = {_ALIASES.get(term, term) for term in re.findall(r"[a-z0-9]+", text.casefold())
             if term not in _STOP}
    # Preserve exact field identifiers as well as readable components. Otherwise
    # in_batt_state_of_charge could silently match state_batt_state_of_charge.
    terms.update(re.findall(r"[a-z0-9]+(?:_[a-z0-9]+)+", text.casefold()))
    return terms


def _document_terms(fact: dict) -> set[str]:
    terms = _terms(" ".join(str(fact[key]) for key in
                            ("statement", "subject", "property", "source_id", "filename")))
    semantic = {"time_min": {"earliest", "timestamp", "range"},
                "time_max": {"latest", "timestamp", "range"},
                "observed_min": {"range"}, "observed_max": {"range"}}
    return terms | semantic.get(fact["property"], set())


def _query_plan(query: set[str], facts: list[dict]) -> tuple[set[str], list[set[str]], set[str]]:
    """Recognize a bounded vocabulary of typed metrics, without interpreting prose.

    Subject terms stay conjunctive. Requested metrics are separate requirements,
    so asking for minimum and maximum retrieves two distinct cited observations.
    A metric family contains alternatives, e.g. minimum may be numeric or time.
    """
    base = set(query)
    groups = []
    aliases = {
        "minimum": {"observed_min", "time_min"},
        "maximum": {"observed_max", "time_max"},
        "earliest": {"time_min"}, "latest": {"time_max"},
        "mean": {"observed_mean"}, "row": {"row_count"},
        "column": {"column_count"}, "null": {"null_count"},
        "nonfinite": {"nonfinite_count"}, "member": {"member_count"},
        "timezone": {"timezone"}, "size": {"size_bytes"}, "byte": {"size_bytes"},
        "label": {fact["property"] for fact in facts if fact["property"].startswith("label_count:")},
    }
    if "row" in query and "group" in query:
        aliases["row"] = aliases["group"] = {"row_group_count"}
    if "uncompressed" in query:
        aliases["uncompressed"] = aliases["byte"] = aliases["size"] = {"uncompressed_bytes"}
    if "range" in query:
        base.remove("range")
        groups.extend(({"observed_min", "time_min"}, {"observed_max", "time_max"}))
    for term, properties in aliases.items():
        if term in query:
            base.remove(term)
            if properties not in groups:
                groups.append(properties)
    ignored = set()
    if "member" in query and "archive" in base:
        base.remove("archive")
        ignored.add("archive")
    if query & {"earliest", "latest", "minimum", "maximum", "range"} and "timestamp" in base:
        base.remove("timestamp")
    return base, groups, query - ignored


def _conflicting_ids(facts: list[dict], declared: list[dict]) -> set[str]:
    """Compare structured values, never pretend to detect prose contradictions."""
    groups: dict[tuple, list[dict]] = {}
    for fact in facts:
        key = (fact["source_id"], fact["subject"], fact["property"])
        groups.setdefault(key, []).append(fact)
    conflicts = set()
    for group in groups.values():
        values = {json.dumps([item["value"], item["units"]], sort_keys=True,
                             separators=(",", ":"), allow_nan=False) for item in group}
        if len(values) > 1:
            conflicts.update(item["fact_id"] for item in group)
    for conflict in declared:
        conflicts.update(conflict["fact_ids"])
    return conflicts


def _eligible(fact: Any) -> bool:
    """Fail closed if a later catalog expands beyond this supported contract."""
    required = {"fact_id", "subject", "property", "value", "units", "statement",
                "source_id", "filename", "sha256", "locator", "kind", "status",
                "qualification_status", "source_version", "trust_class"}
    if type(fact) is not dict or not required.issubset(fact):
        return False
    text_fields = required - {"value", "units"}
    if any(not isinstance(fact[key], str) or not fact[key].strip() for key in text_fields):
        return False
    return (fact["kind"] == "observation" and fact["status"] == "context_only"
            and fact["qualification_status"] == "unresolved"
            and fact["trust_class"] == "source_observed"
            and re.fullmatch(r"[0-9a-f]{64}", fact["sha256"]) is not None
            and fact["source_version"] == f"sha256:{fact['sha256']}")


def advise(question: str, catalog_path: str | Path, source_id: str | None = None,
           limit: int = 3) -> dict:
    """Return exact observed facts or abstain, without producing a command.

    All subject terms must occur in a fact's searchable text after the small
    alias/stop-word normalization. Typed metric families (e.g. min and max) can
    be satisfied by separate facts. Candidates are ranked by binary-term cosine
    similarity with smoothed IDF, then by stable fact ID; each requested metric
    must be represented within the result limit.
    ``limit`` bounds returned extracts; it cannot affect the authority boundary.
    Catalog verification occurs on every valid request, including operational
    requests. A source filter never selects an unverified alternate corpus.
    """
    if type(limit) is not int or not 1 <= limit <= 10:
        raise ValueError("limit must be an integer from 1 to 10")
    result = {
        "schema_version": "1.0.0", "mode": "offline_extractive",
        "response_type": "abstain", "question": question if isinstance(question, str) else None,
        "reason_code": "invalid_question", "message": _MESSAGES["invalid_question"],
        "catalog": None, "source_filter": source_id if isinstance(source_id, str) else None,
        "claims": [], "command_proposal": None,
        "authority": "source_observations_only", "can_execute": False,
    }

    def abstain(reason: str) -> dict:
        result.update(reason_code=reason, message=_MESSAGES[reason])
        return result

    if not isinstance(question, str) or not question.strip() or len(question) > 2048:
        return result
    if source_id is not None and (not isinstance(source_id, str) or not source_id.strip()
                                  or len(source_id) > 128):
        return abstain("invalid_filter")
    try:
        catalog = load_catalog(catalog_path)
        facts = catalog["facts"]
        if type(facts) is not list or any(not _eligible(fact) for fact in facts):
            return abstain("catalog_unverified")
        # Require the supported trust class rather than accepting a corpus label
        # that merely asserts approval. The catalog loader verifies its manifest.
        result["catalog"] = {"catalog_id": catalog["catalog_id"],
                             "content_sha256": catalog["content_sha256"]}
        conflicts = _conflicting_ids(facts, catalog.get("conflicts", []))
    except (OSError, ValueError, KeyError, TypeError):
        result["catalog"] = None
        return abstain("catalog_unverified")
    if _OPERATIONAL.search(question):
        return abstain("operational_authority_unavailable")
    if source_id is not None and source_id not in {fact["source_id"] for fact in facts}:
        return abstain("unknown_source")
    filtered = [fact for fact in facts if source_id is None or fact["source_id"] == source_id]
    query_terms = _terms(question)
    if not query_terms or not filtered:
        return abstain("no_matching_evidence")
    base_terms, metric_groups, query_terms = _query_plan(query_terms, filtered)
    indexed = [(fact, _document_terms(fact)) for fact in filtered]
    vocabulary = set().union(*(terms for _, terms in indexed))
    if not query_terms.issubset(vocabulary):
        return abstain("no_matching_evidence")
    weights = {term: 1.0 + math.log((len(indexed) + 1) /
                                   (1 + sum(term in terms for _, terms in indexed)))
               for term in vocabulary}
    query_norm = math.sqrt(sum(weights[term] ** 2 for term in query_terms))
    ranked = []
    for fact, terms in indexed:
        if not base_terms.issubset(terms):
            continue
        if metric_groups and not any(fact["property"] in group for group in metric_groups):
            continue
        matched = query_terms & terms
        denominator = query_norm * math.sqrt(sum(weights[term] ** 2 for term in terms))
        score = sum(weights[term] ** 2 for term in matched) / denominator
        ranked.append((score, fact))
    ranked.sort(key=lambda pair: (-pair[0], pair[1]["fact_id"]))
    if not ranked:
        return abstain("no_matching_evidence")
    selected_ids = set()
    for group in metric_groups:
        best = next((fact for _, fact in ranked if fact["property"] in group), None)
        if best is None:
            return abstain("no_matching_evidence")
        selected_ids.add(best["fact_id"])
    if len(selected_ids) > limit:
        return abstain("no_matching_evidence")
    # Check all matching facts before truncating, so a low-ranked contradiction
    # cannot disappear because a caller requested one result.
    if any(fact["fact_id"] in conflicts for _, fact in ranked):
        return abstain("conflicting_evidence")
    for _, fact in ranked:
        if len(selected_ids) >= limit:
            break
        selected_ids.add(fact["fact_id"])
    selected = [(score, fact) for score, fact in ranked if fact["fact_id"] in selected_ids]
    if not query_terms.issubset(set().union(*(_document_terms(fact) for _, fact in selected))):
        return abstain("no_matching_evidence")
    for score, fact in selected:
        citation = {"evidence_id": fact["fact_id"], "source_id": fact["source_id"],
                    "source_version": fact["source_version"], "source_sha256": fact["sha256"],
                    "filename": fact["filename"], "locator": fact["locator"],
                    "subject": fact["subject"], "property": fact["property"],
                    "trust_class": fact["trust_class"],
                    "qualification_status": fact["qualification_status"]}
        result["claims"].append({"text": fact["statement"], "citation": citation,
                                 "retrieval": {"score": round(score, 8),
                                               "matched_terms": sorted(query_terms & _document_terms(fact)),
                                               "query_term_coverage": round(len(query_terms & _document_terms(fact)) / len(query_terms), 8)}})
    result.update(response_type="observation", reason_code="evidence_found",
                  message=_MESSAGES["evidence_found"])
    return result
