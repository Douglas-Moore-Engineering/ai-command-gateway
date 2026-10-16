# ADR-001: Local deterministic foundation with a mock outcome

Status: selected for the authorized local implementation increment; not a production architecture approval. Date: 2026-10-15. Owner/preparer: DME delivery lead. Trace: REQ-01, REQ-02, REQ-03, REQ-04, REQ-06; OPEN-03, OPEN-04, OPEN-05, OPEN-07.

## Context

The user has supplied five research inputs and authorized starting the AI Command Gateway. Discovery identifies command assurance and explicit human authority as the mission. Dataset semantics, equipment limits, real identities, throughput, latency obligations and hosting are not qualified. Research labels cannot substitute for a controls engineer's expected command decisions.

## Decision

Build a Python CLI with explicit structured contracts, deterministic policy evaluation and a SQLite ledger. Profile data read-only and preserve provenance. End the approval/revalidation path at a mock outcome. Default unqualified policy cannot allow an action. Keep policy evaluation independent of any LLM or external service. Bind approval to the specific proposal/policy and revalidate current state before recording a mock outcome.

Use a single local transaction to persist the authorization/outcome state changes before returning success. Local actor names exercise workflow but are not authenticated identities. The workstation and its user remain trusted; neither application logic nor SQLite prevents that user editing local artifacts.

## Alternatives and tradeoffs

| Alternative | Benefit | Decision basis |
|---|---|---|
| LLM decides command eligibility | Flexible natural-language interpretation | Deferred: unreviewed guidance and nondeterministic output cannot establish authoritative limits; REQ-01/02 require explicit enforcement |
| Network API plus managed database | Central identity and multi-user integration could be added | Deferred: workload, exposure, role ownership and cost unknown; creates unnecessary hosting commitments now |
| Flat JSON audit files | Minimal dependency | Rejected for transaction workflow: approval consumption and outcome linkage benefit from one durable database boundary |
| Full training pipeline first | Could explore detection models | Deferred: source labels/units and command ground truth remain unqualified; model training does not solve approval authority |
| Live PLC adapter | Tests real end-to-end actuation | Outside this increment: no equipment authority, site network or safety evidence |

The selected approach provides reproducible logic and inexpensive local iteration. It also limits concurrency, identity assurance, tamper resistance and availability; those are explicit constraints, not production properties. SQLite is a local persistence implementation choice, not a claim that it meets a future multi-user or operational workload.

## Verification and review triggers

Inspect negative/authority/replay/storage-failure tests and exact runtime code before asserting implemented behavior. Retain actual test output separately from acceptance claims. Reconsider this decision when a real operator identity, external API, live telemetry, new actuation path, measured contention, protected evidence retention or approved hosted deployment is required. Review source contracts and policy authority before a data-derived state can support eligibility. No ADR can authorize equipment operation by itself.
