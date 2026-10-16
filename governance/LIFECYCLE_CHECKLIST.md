# Lifecycle checklist — v0.2

Fictional engagement. Authorized: local offline application foundation as of the 2026-10-15 build request. Active baseline: DISC-001 v0.1. Date: 2026-10-15. [Handoff](../customer/HANDOFF.md) defines current authorization and remaining exposure boundaries.

The table and original v0.2 discussion below preserve that increment's lifecycle state. Later continuation and foundation approval are recorded in the follow-ons at the end.

| Phase | Activity | State | Entry / exit and authority | Evidence / gap |
| --- | --- | --- | --- | --- |
| 1 | Intake | prepared for review | Discovery review by user; no real customer sign-off | [DISC-001](../customer/DISC-001-v0.1.md) |
| 2 | Discovery | prepared for review | Discovery review by user; no real customer sign-off | [DISC-001](../customer/DISC-001-v0.1.md) |
| 3 | Scope and responsibilities | next review; not approved | Scoped inputs and accountable review required before exit | [Open items](../customer/open-items.csv); evidence not yet available |
| 4 | Commercial/SOW | not started | Scoped inputs and accountable review required before exit | [Open items](../customer/open-items.csv); evidence not yet available |
| 5 | Hosting decision | not started | Scoped inputs and accountable review required before exit | [Open items](../customer/open-items.csv); evidence not yet available |
| 6 | Data/security/privacy/IP | local files inspected; qualification open | Scoped inputs and accountable review required before exit | [Open items](../customer/open-items.csv); evidence not yet available |
| 7 | Standards/tailoring/SEMP | v0.2 preliminary tailoring prepared | Scoped inputs and accountable review required before exit | [Open items](../customer/open-items.csv); evidence not yet available |
| 8 | System engineering | local foundation implemented and tested | Scoped inputs and accountable review required before exit | [Open items](../customer/open-items.csv); evidence not yet available |
| 9 | Reviews and change control | implementation trace updated; domain review pending | Scoped inputs and accountable review required before exit | [Open items](../customer/open-items.csv); evidence not yet available |
| 10 | Reference demo review | synthetic demo exercised; acceptance pending | Scoped inputs and accountable review required before exit | [Open items](../customer/open-items.csv); evidence not yet available |
| 11 | Site adaptation | not started | Scoped inputs and accountable review required before exit | [Open items](../customer/open-items.csv); evidence not yet available |
| 12 | Site validation | not started | Scoped inputs and accountable review required before exit | [Open items](../customer/open-items.csv); evidence not yet available |
| 13 | Operational readiness | not started | Scoped inputs and accountable review required before exit | [Open items](../customer/open-items.csv); evidence not yet available |
| 14 | Customer acceptance | not started | Scoped inputs and accountable review required before exit | [Open items](../customer/open-items.csv); evidence not yet available |
| 15 | Production release | not started | Scoped inputs and accountable review required before exit | [Open items](../customer/open-items.csv); evidence not yet available |
| 16 | Service management | not started | Scoped inputs and accountable review required before exit | [Open items](../customer/open-items.csv); evidence not yet available |
| 17 | Change/retraining | not started | Scoped inputs and accountable review required before exit | [Open items](../customer/open-items.csv); evidence not yet available |
| 18 | Transfer/renewal | not started | Scoped inputs and accountable review required before exit | [Open items](../customer/open-items.csv); evidence not yet available |
| 19 | Retirement | not started | Scoped inputs and accountable review required before exit | [Open items](../customer/open-items.csv); evidence not yet available |

Production platform and model deployment remain unstarted. The local runtime, dataset profiler and mock application foundation are implemented; [standards tailoring](standards-tailoring.md) and [results](../docs/results.md) record scope and evidence. Governance gates have not passed. No cloud transition or lifecycle checker PASS is claimed. Local software checks do not verify production controls or VS Code installation on the user's computer.

This update records authorized engineering progress, not customer approval of phases 3-7 or a passed lifecycle gate. Scope/cost/domain conditions remain visible while local software work proceeds.

## v0.3 local continuation

Source timestamp/numeric quality analysis and exact observation retrieval now extend the offline foundation. The catalog retains unresolved qualification, source identities and explicit context-only status. [ADR-002](../architecture/adr/ADR-002-cited-observations.md) records the implemented design and proposed hosted runtime. No provider is connected and no governance or acceptance gate is passed by this increment. [Results](../docs/results.md) distinguish regression evidence from domain measurement.

## v0.4 implementation progress

Optional hosted-advice code and the first Azure batch implementation are now prepared. This advances phases 5, 6, 8 and 9 through architecture/code evidence only. No cloud resource, operator readiness result, customer acceptance or production release follows automatically. [Azure implementation](../docs/azure-implementation.md) and [results](../docs/results.md) distinguish local validation from pending deployment checks.

## v0.4 foundation authorization follow-on

The user explicitly approved the private foundation in `rg-ai-command-gateway-dev`, East US 2, including standing cost, usage and partial-failure risk. Foundation deployment succeeded with the job disabled and 21/21 read-only control-plane checks passed; [deployment review](../docs/azure-deployment-review.md) records the outcome. This advances the bounded hosting/infrastructure work beyond local preparation. It does not verify data-plane access or authorize image publication, dataset uploads or job execution, and does not close operational readiness, customer acceptance or production gates. [COST-001](../customer/COST-001.md) records the spending scope separately from the fictional discovery budget.
