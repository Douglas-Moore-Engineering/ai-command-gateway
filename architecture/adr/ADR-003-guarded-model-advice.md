# ADR-003: Optional model adapter with exact evidence validation

Status: implemented for the v0.4 local reference system; live integration and model quality remain unverified. Date: 2026-10-15. Trace: REQ-02, REQ-05 and REQ-06; AC-02, AC-05 and AC-06 remain proposed. This advances the runtime candidate in [ADR-002](ADR-002-cited-observations.md) after the user requested continuation.

## Context and decision

The local catalog supplies research observations with unresolved engineering meaning. It cannot support operating advice or a physical safety conclusion. The user asked which runtime to target and then requested continuation. Implement an optional OpenAI Responses adapter targeting `gpt-6.1-sol`, while preserving offline retrieval and the independent mock gateway.

GPT-6.1 Sol supports structured outputs. It is the first runtime to evaluate, selected as an implementation starting point rather than a measured winner on this system's questions. [Official model documentation](https://developers.openai.com/api/docs/models/gpt-6.1-sol)

The adapter operates after deterministic retrieval. It receives the question, selected IDs and exact statements, and the verified catalog ID/hash. It may return all selected claims unchanged in any order, or refuse. The application rejects missing, changed, duplicate or additional claims. The final result reconstructs the original local claim objects in the validated model order, preserving their text and citations. It never displays arbitrary provider prose. This contract adds an integration boundary without expanding semantic question coverage; ordering quality is unmeasured.

The command remains offline unless `--provider openai` is explicit. `--dry-run` returns the exact request body without reading a credential or making a request. The live path reads `OPENAI_API_KEY` only from the process environment; `.env` is not loaded automatically. It uses a fixed OpenAI endpoint, no tools, `store=false`, a bounded response, a timeout and no automatic retries. Local abstentions skip the provider; provider/configuration failures or invalid responses retain the local result with explicit metadata.

## Alternatives and rationale

| Option | Benefit | Decision for this increment |
| --- | --- | --- |
| Keep offline retrieval only | Reproducible observations with no provider dependency | Retained as the default and fallback |
| Optional hosted model with exact output checks | Exercises request, response and failure contracts while preserving evidence coverage | Implemented; no live quality claim |
| Free-form generative explanation | Could improve readability and contextual reasoning | Deferred until reviewed knowledge and semantic evaluation exist |
| Locally hosted model | Could satisfy a future offline-inference requirement | Remains an alternative; model, hardware and evaluation evidence are not established |

The deliberately narrow output contract offers little immediate explanatory benefit. It makes provider integration reviewable before permitting claims that cannot be verified by exact comparison. Structured outputs enforce the requested format, while application validation handles evidence binding and refusal/failure paths. [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses)

## Data, authority and failure boundaries

Only the selected aggregate evidence is placed in the request. The adapter does not attach raw files, full profiles/catalogs, local paths, policy documents or approval/audit records. Statements contain research filenames and fields; the question may itself contain private information. A request preview exposes the exact content before transmission. The key is transport authentication, never prompt content or reported metadata.

`store=false` is not a Zero Data Retention guarantee. Provider abuse monitoring, prompt caching and account-specific controls still require review for intended data. No account configuration, residency, retention approval or subscription is established by the code. [OpenAI data controls](https://developers.openai.com/api/docs/guides/your-data)

The response retains observation-only authority, no command proposal and no execution capability. The adapter has no gateway execution dependency and receives no equipment credentials. Metadata distinguishes `validated` model output, `fallback`, `skipped` calls, `dry_run` previews and `rejected` evidence. Local evidence is checked again after provider use; changed or unverifiable evidence clears the observations. A valid offline fallback exits 3 and is not counted as successful hosted inference. A caller who can alter local code or evidence can defeat these checks; this remains a trusted-workstation reference implementation.

## Verification and review triggers

Verification uses simulated provider replies, exact payload inspection, negative citation/claim cases and failure injection. The original retrieval casebook continues to test the offline path. A dry run demonstrates request construction with supplied dataset observations without transmitting them. See [results](../../docs/results.md) for recorded commands and outcomes. These checks do not measure model correctness, usefulness, latency, provider uptime or operational safety.

Review this decision when changing the provider/model, prompt, response contract, retrieval coverage, evidence trust, endpoint, data exposure, tools or command authority. Broader explanation requires reviewed sources and independently assessed representative cases. Live evaluation needs explicit configuration and measured usage/cost evidence. Equipment integration, identities, approved policy and release gates remain independent pending work; OPEN-01-08 are not closed by this adapter.
