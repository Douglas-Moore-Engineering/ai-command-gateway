# MEAS-003 — Authority bypass

Record version: 0.1. Recorded: 2026-10-15. KPI: KPI-003, dictionary v0.1. Need: NEED-01.
Requirement: REQ-02, REQ-03. Criterion: AC-02. [Definitions](../../docs/appendix-a-kpi-dictionary.md). [Acceptance](../../requirements/acceptance.csv).

| Field | Current value |
| --- | --- |
| Definition / unit | observed bypasses / attempted bypass tests |
| Baseline | not measured |
| Target / approval | 0 observed; proposed; not approved |
| Method / population | Predeclare source-qualified cases and reviewed expected decisions before evaluation; selection, exclusions and sample size TBD by security |
| Independent unit | attack scenario; repeated rows must not imply independent assets |
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
| Owner | DME prepares; fictional security role reviews, actual reviewer unassigned |
| criterion_result | not evaluated |
| acceptance_disposition | pending review |
| Decision / authority | no sign-off or release authorization |
| Next action | Resolve OPEN-02 and relevant data/policy prerequisites before measurement |
| Remeasurement trigger | Changes to code, source data, policy, model, permissions or operating envelope |

Only an unmeasured planning record is supported. Customer acceptance and production readiness are not established. [Handoff](../../customer/HANDOFF.md).

## v0.2 evidence boundary - 2026-10-15

The table above preserves the original acceptance-planning baseline. Local implementation and synthetic regression evidence now exist in [results](../../docs/results.md). Source files have been inspected and hashed. These observations do not constitute the frozen, independently reviewed measurement population required by this KPI; its acceptance result remains not evaluated.
