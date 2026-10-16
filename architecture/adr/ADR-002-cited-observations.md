# ADR-002: Local extractive observations before model integration

Status: implemented for v0.3 local retrieval; hosted runtime remains proposed. Date: 2026-10-15. Trace: REQ-05 / AC-05; OPEN-02 and data qualification remain unresolved.

The five research files establish observations, not authoritative operating guidance. Build a catalog from typed profile fields and pinned file identities, regenerate facts when loading it, and return exact statements with source versions and locators. Keep arbitrary document prose outside the executable instruction path. All catalog evidence remains context-only with unresolved engineering qualification.

The advisor supports a bounded set of metric queries and returns an explicit abstention when it cannot support the request. It has no command proposal or execution interface. Local checks detect inconsistent artifact edits, but do not authenticate a publisher or protect against a user controlling all local artifacts. See the [catalog design](../../docs/evidence-design.md), [architecture](../../docs/architecture/README.md) and [source findings](../../docs/source-semantics.md).

An engineer-authored casebook was frozen before its first evaluation. It now serves as a regression suite, including cases used during retrieval development. Its score is not an independent estimate of model quality, domain acceptance or future question coverage. Preserve its version and hash when changing the retriever.

## Proposed next runtime

Evaluate OpenAI Responses API with GPT-6.1 Sol as the first hosted explanation adapter. The official model documentation lists structured outputs and positions it as a lower-cost option for complex work. This is a candidate to test on representative questions, not a measured winner for this system. [Official model documentation](https://developers.openai.com/api/docs/models/gpt-6.1-sol)

No provider connection or paid inference is configured. A future adapter should receive only selected evidence, have its claims checked against that evidence, and remain outside policy evaluation, approval and execution. Keep the current extractive response available when the adapter is absent or fails. A fully local model remains an alternative if offline use or data residency is the primary constraint; model selection requires a separate measured comparison.

Review this decision when adding a provider, an approved operating corpus, new evidence types, external identity or an execution interface. Physical limits require authoritative engineering evidence independently of the model choice.

## v0.4 continuation

The local evidence decision remains in force. The proposed provider adapter is now implemented under [ADR-003](ADR-003-guarded-model-advice.md), with local fixture verification only. This does not qualify the source observations or demonstrate live model quality.
