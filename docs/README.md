# Documentation index

v0.4 adds an optional guarded OpenAI adapter and the deployed private Azure foundation. The job remains unprovisioned. Local validation and deployed evidence are recorded separately; formal acceptance remains pending.

## Contents

- [Implementation baseline, CONOPS, threats and verification](implementation-baseline.md)
- [Architecture and rendered diagram](architecture/README.md)
- [ADR-001: local foundation](../architecture/adr/ADR-001-offline-foundation.md)
- [ADR-002: cited observations and proposed model runtime](../architecture/adr/ADR-002-cited-observations.md)
- [ADR-003: guarded model adapter](../architecture/adr/ADR-003-guarded-model-advice.md)
- [Azure implementation and deployment steps](azure-implementation.md), [ADR-004: Azure batch foundation](../architecture/adr/ADR-004-azure-batch-foundation.md)
- [Approved foundation deployment and outcome](azure-deployment-review.md), [regional cost estimate](azure-cost-estimate.md)
- [Container resource checks](azure-runtime-checks.md), [image scan findings and release boundary](image-security.md)
- [Evidence catalog design](evidence-design.md), [source semantics and timestamp findings](source-semantics.md)
- [Standards tailoring and SEMP](../governance/standards-tailoring.md)
- [Data qualification](../data/README.md)
- [Synthetic policy specification](synthetic-policy-reference.md)
- [Runnable demo](demo.md), [code walkthrough](code-walkthrough.md), [results](results.md)
- [Requirements](../requirements/requirements.csv), [acceptance](../requirements/acceptance.csv), [traceability](../requirements/traceability.csv)
- [KPI dictionary](appendix-a-kpi-dictionary.md), [lifecycle](../governance/LIFECYCLE_CHECKLIST.md), [AI governance](../governance/AI_GOVERNANCE_PLAN.md)
- [Release boundaries](../governance/release_gates.md), [open items](../customer/open-items.csv), [cost model](../customer/COST-001.md)
- [Discovery](../customer/DISC-001-v0.1.md), [handoff](../customer/HANDOFF.md), [operating instructions](../runbooks/README.md)
- [Historical repository setup verification](../governance/repository-verification.md)

- [Readable answer examples](answer-examples.md), [cited explanation decision](../architecture/adr/ADR-005-cited-explanations.md) and [verification](../governance/cited-explanation-verification-2026-10-16.json).
