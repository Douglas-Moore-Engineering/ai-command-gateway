# ADR-005: Cited model explanations and readable output

Status: implemented; offline integration verification only. Date: 2026-10-16. Trace: NEED-02, REQ-05/REQ-02/REQ-06, MEAS-006; AC-05 and live model-quality acceptance remain open.

## Problem and decision

The exact-observation adapter in ADR-003 could repeat facts but could not explain them in conversational prose, and the CLI displayed JSON only. Add explicit `--explain` for the optional provider and `--format text` for readable output. Keep the existing exact-claim contract and offline default as the baseline. Save displayed answers with `--output`; preserve JSON for programmatic consumers.

In explanation mode the strict provider schema adds sentences with supporting evidence IDs. Every selected claim stays exact and every selected evidence ID must be covered. Local code checks shape, bounded text, citation membership, numeric-token membership and conservative operational-language screening, then reconstructs citations. The original catalog is reverified after the provider response, including error paths. A changed catalog removes both claims and prose. Rejected explanations retain only current exact local observations and an explicit failure reason.

## Trust and alternatives

A fixed formatter provides readable offline observations but no model paraphrase. The existing exact-copy provider remains the compatibility baseline. Free-form prose without citation binding was rejected. The selected opt-in path permits useful paraphrase while preserving original evidence and exposing the limits of automated checks.

Citation and token checks are not entailment validation. A model can attach a real citation to a false interpretation, swap meanings using existing numbers or invent causal relationships/units. The answer explicitly records `semantic_entailment: not_evaluated`; the renderer identifies review-required model prose. Contract status `validated` means these bounded checks passed, not that the answer is true. The operational screen is heuristic and cannot replace authorization; no model code imports the gateway or supplies command proposals, tools, policies, approvals or execution credentials. Independent domain review and representative live-provider evaluation remain required before any broader use.

## Verification and disposition

[Explanation tests](../../tests/test_explanations.py) cover paraphrase, local citations, unknown/duplicate/missing references, numeric invention, command-like prose, malicious formatting, refusal, missing keys, stale catalogs, CLI display and saved output. [Recorded examples](../../docs/answer-examples.md) distinguish deterministic output from a hand-authored simulated-provider response. [Verification record](../../governance/cited-explanation-verification-2026-10-16.json) binds actual runs and sources. These development cases are not held-out model-quality evidence. No live inference, Azure connection, domain acceptance or production authorization follows from this change.

Rollback: omit `--explain` to retain the exact-claim adapter; omit `--provider openai` to stay fully offline. Existing historical cloud image/evidence is unchanged and does not qualify the new source.

## Source basis

The [OpenAI Structured Outputs guide](https://developers.openai.com/api/docs/guides/structured-outputs), checked 2026-10-16, documents strict schema responses and notes that structured outputs can still contain mistakes. The [Responses API reference](https://developers.openai.com/api/reference/resources/responses/methods/create) documents `text.format`. No provider API version, dependency, model selection or transport endpoint changed in this increment.
