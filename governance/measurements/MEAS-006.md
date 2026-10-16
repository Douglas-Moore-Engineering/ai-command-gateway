# MEAS-006 — Grounded recommendation or abstention

Record version: 0.1. Recorded: 2026-10-15. KPI: KPI-006, dictionary v0.1. Need: NEED-02.
Requirement: REQ-05. Criterion: AC-05. [Definitions](../../docs/appendix-a-kpi-dictionary.md). [Acceptance](../../requirements/acceptance.csv).

| Field | Current value |
| --- | --- |
| Definition / unit | supported consequential recommendations or justified abstentions / reviewed consequential recommendations |
| Baseline | not measured |
| Target / approval | all reviewed items; proposed; not approved |
| Method / population | Predeclare source-qualified cases and reviewed expected decisions before evaluation; selection, exclusions and sample size TBD by controls |
| Independent unit | source-grounded case; repeated rows must not imply independent assets |
| Window / clock | not evaluated; record source clock and test wall clock separately |
| Comparator / split | Manual review for AC-04; reviewed expected outcomes otherwise. Freeze independent evaluation cases before tuning |
| Protocol / fixed date | not established; OPEN-02 remains open |
| Aggregation / uncertainty | Ratio denominators and event grouping required; interval method TBD before tests. Quantiles require declared hardware/load and sampling method |
| measurement_status | not measured |
| Observed result / denominator | not measured / no evaluated cases |
| Environment / data origin | no evaluation run; intended offline public reference data |
| Uncertainty estimate | not measured |
| Representativeness | No validated source files, operational limits or site transfer evidence |
| Intervention / follow-up / attribution | not measured; engineering metrics alone cannot establish avoided loss |
| Financial basis | N/A for this engineering measure; savings not measured |
| Run / log / code / data bindings | none; no evaluated implementation or dataset snapshot |
| Model / config / dependencies | not selected; no inference evaluation |
| Reproduction command | unavailable until implementation and frozen protocol exist |
| Owner | DME prepares; fictional controls role reviews, actual reviewer unassigned |
| criterion_result | not evaluated |
| acceptance_disposition | pending review |
| Decision / authority | no sign-off or release authorization |
| Next action | Resolve OPEN-02 and relevant data/policy prerequisites before measurement |
| Remeasurement trigger | Changes to code, source data, policy, model, permissions or operating envelope |

Only an unmeasured planning record is supported. Customer acceptance and production readiness are not established. [Handoff](../../customer/HANDOFF.md).

## v0.2 evidence boundary - 2026-10-15

The table above preserves the original acceptance-planning baseline. Local implementation and synthetic regression evidence now exist in [results](../../docs/results.md). Source files have been inspected and hashed. These observations do not constitute the frozen, independently reviewed measurement population required by this KPI; its acceptance result remains not evaluated.

## v0.3 evidence boundary - 2026-10-15

The offline advisor now returns verified exact observations or abstains. The [12-case regression suite](../../data/evaluation/advice-cases-v1.json) was authored before its first evaluation and used during retrieval development. It checks expected facts, exact citations and refusal behavior; it is not a held-out or independently reviewed consequential-recommendation population. No model inference was used. KPI-006 and AC-05 remain unevaluated under their domain protocol; the [results record](../../docs/results.md) reports the narrower software evidence.

## v0.4 provider boundary evidence

The provider adapter is exercised using injected responses, including exact-claim acceptance, missing credentials, refusal, malformed claims, errors and catalog changes. These tests establish application behavior, not live model correctness or recommendation coverage. The local observation casebook remains unchanged; AC-05 and KPI-006 remain unevaluated.

## Cited explanation increment — 2026-10-16

Opt-in natural-language explanation and readable output are now implemented. [Integration verification](../cited-explanation-verification-2026-10-16.json) checks citation/numeric-token contracts using injected responses, not a live model or an independent consequential-recommendation population. KPI-006 remains not measured, AC-05 not evaluated, acceptance pending review. Semantic entailment, units and interpretation remain unqualified; no engineering-acceptance claim is added.
