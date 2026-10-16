# Application demonstration

Run from the repository root after the [README setup](../README.md#how-do-i-run-the-demo). The default commands use no provider credential or equipment connection. Hosted inference requires the explicit option described below.

```powershell
.venv/Scripts/python.exe -m ai_command_gateway demo
```

This creates a fresh synthetic request and exercises five expected behaviors: allow an in-range proposal, block a limit violation, escalate missing evidence, issue approval and record mock execution, then reject replay. The request timestamp is refreshed only for this synthetic fixture. Output is JSON and the process exits 0 only when all five checks match. The SQLite audit lives under `outputs/demo/` and persists across runs.

## Source inspection and historical replay

```powershell
.venv/Scripts/python.exe -m ai_command_gateway profile --input-dir "C:/Users/moore/Downloads" --output-dir outputs/profiles
.venv/Scripts/python.exe -m ai_command_gateway replay --input-dir "C:/Users/moore/Downloads" --limit 20
```

Profiling inspects all five files, streams Parquet statistics, and inventories ZIP/MAT contents. No source MATLAB program is executed. A missing or unreadable file is reported and causes a nonzero profile exit.

Replay records actual S1 process observations with file SHA-256 and row index. It preserves historical timestamps and marks units/modes unqualified. It exercises the unqualified-policy escalation path without claiming physical command classification. First-N storage-order selection is not a representative test split. S2/S3 remain independent context collections; they are not joined onto the S1 clock.

## Source qualification and cited observations

After `profile`, run:

```powershell
.venv/Scripts/python.exe -m ai_command_gateway qualify --input-dir "C:/Users/moore/Downloads"
.venv/Scripts/python.exe -m ai_command_gateway catalog
.venv/Scripts/python.exe -m ai_command_gateway advise --question "What are the observed minimum and maximum values of in_batt_state_of_charge?" --source S1
.venv/Scripts/python.exe -m ai_command_gateway eval-advice
```

`qualify` checks all five files against `data/lineage/source-inventory.json`, scans all S1 numeric/timestamp rows, and writes `outputs/qualification/source-qualification.json`. It measures stored row order, repeated timestamps, positive-delta cadence and numeric quality. It preserves absent timezones and leaves units/scaling unresolved. Missing or mismatched files produce explicit report statuses and exit 1. A complete run means the declared analysis completed, not engineering approval. See [source semantics](source-semantics.md).

`catalog` consumes `outputs/profiles/dataset-profile.json`, independently of the qualification report. It writes `evidence-catalog.json`, `evidence-profile.json` and `evidence-manifest.json` under `outputs/advice/`. Keep the three files together. The catalog admits controlled aggregate observations and checks file identities against the inventory; archive prose and scripts are excluded. Loading regenerates facts and validates the bundle. This verifies local consistency, not an independently trusted measurement origin. See [evidence design](evidence-design.md).

`advise` performs deterministic local retrieval. Each returned claim copies a catalog statement and cites its source hash, file, property and profile locator. Unknown questions, conflicting observations and equipment-action requests abstain. For example, the following intentionally exits 2:

```powershell
.venv/Scripts/python.exe -m ai_command_gateway advise --question "Is 500000 W a safe battery power target?" --source S1
```

Default advice is an offline observation response with no command proposal or execution authority. `advise` exits 0 for observations, 2 for normal abstention, and 1 for invalid input or an unverifiable catalog. It does not append advice to the gateway audit database.

`eval-advice` runs `data/evaluation/advice-cases-v1.json` and writes `outputs/advice-evaluation/advice-evaluation.json`, including catalog/casebook hashes, exact-citation checks, expected-fact coverage and abstentions. Exit 0 means every local case passed; exit 1 means failure. These frozen engineer-authored cases do not constitute independent domain acceptance or an LLM evaluation. Use each command's `--help` for alternate profile, inventory, catalog, casebook and output paths.

## Readable answers and saved output

For a sentence-based answer without a model, use `advise --format text`. To inspect a recorded example now, open [answer examples](answer-examples.md). Reproduce both offline and simulated-provider examples with:

```powershell
.venv/Scripts/python.exe scripts/show_answer_examples.py
```

This writes `outputs/answers/offline-answer.txt` and `outputs/answers/simulated-model-answer.txt`. The simulated example uses hand-authored provider output, not live inference.

With an existing catalog, preview the new explanation request without credentials or network:

```powershell
.venv/Scripts/python.exe -m ai_command_gateway advise --provider openai --explain --dry-run --question "How many rows are in process_dataset.parquet?" --output outputs/answers/preview.txt
```

For an intentional live LLM answer, configure the provider key as described below, then run:

```powershell
.venv/Scripts/python.exe -m ai_command_gateway advise --provider openai --explain --question "How many rows are in process_dataset.parquet?" --output outputs/answers/answer.txt
```

`--explain` requests natural-language sentences with evidence references and defaults to plain-text output. `--format json` includes the explanation under `answer`, alongside unchanged exact evidence claims under `response.claims`. `--output` saves the same text printed to the terminal; it overwrites that named local file. No default output file is silently created. Without `--explain`, legacy JSON and exact-claim behavior remain available. `--format text` works offline too.

The explanation contract checks shape, bounded text, complete selected-evidence coverage, valid citation IDs, numeric-token membership and a conservative operational-language screen. Local code constructs citations; the model cannot supply citation locators. Rechecking the catalog after a provider call prevents stale facts and stale explanations. These checks do **not** prove semantic entailment, correct attribution, units, causal interpretation or model quality. A schema-valid answer can still be wrong. Generated prose is labeled for review, has no command authority and is not engineering guidance. [ADR-005](../architecture/adr/ADR-005-cited-explanations.md) records this deliberate boundary.

Malformed, unsupported or incomplete explanations fall back to labeled exact local observations (exit 3). Provider failures/refusals do the same. Missing/conflicting evidence and operational questions abstain before inference (exit 2, or 1 for invalid/unverifiable input). Catalog changes reject the result and clear the explanation (exit 1). Dry-run is explicitly labeled and never presented as model-written prose.

## Optional OpenAI advice

Build the catalog first. This command previews the exact request body without reading a credential or making a network call:

```powershell
.venv/Scripts/python.exe -m ai_command_gateway advise --provider openai --dry-run --question "How many rows are in packets_dataset.parquet?" --source S1
```

The adapter starts with the same local retrieval and abstention checks as default `advise`. A request contains the user's question, the selected observation IDs and exact statements, and the catalog ID/hash, alongside the fixed instructions and output schema. It does not attach raw datasets, the full catalog, local paths, gateway policy, approval records or equipment credentials. Observation statements can include source filenames and field names. Text typed in the question is sent as provided, so inspect the preview before including private information. `--explain`, `--dry-run`, `--model`, `--timeout` and `--max-output-tokens` require explicit `--provider openai`.

For a deliberate live call, configure `OPENAI_API_KEY` in the process environment through your normal secret-management method, then omit `--dry-run`:

```powershell
.venv/Scripts/python.exe -m ai_command_gateway advise --provider openai --model gpt-6.1-sol --timeout 30 --max-output-tokens 2048 --question "How many rows are in packets_dataset.parquet?" --source S1
```

This command sends data to OpenAI and can incur provider charges. The application does not automatically read `.env`; keep credentials out of command arguments, source control and output files. The adapter uses `https://api.openai.com/v1/responses`, an empty tool list, `store=false`, one request without automatic retries, and the declared socket timeout/output-token cap. Timeout accepts 1-60 seconds; the output cap accepts 256-4096 tokens. The socket timeout is not an end-to-end latency guarantee, and the token cap does not bound total cost. No live call was made to produce the checked-in v0.4 verification evidence.

`store=false` does not establish Zero Data Retention. Provider abuse-monitoring and prompt-cache retention can still apply; account settings and applicable data controls need separate review for the intended data. [OpenAI data controls](https://developers.openai.com/api/docs/guides/your-data)

Without `--explain`, model output is restricted to the complete selected claim set, copied exactly, in any order, or a refusal. The final claims are reconstructed from local objects in the validated model order; text and citations remain local. Paraphrases, omitted claims, added facts, unsupported IDs and invalid responses are rejected; arbitrary model prose is never displayed. A failed provider result returns the original observations with explicit fallback metadata. If evidence changes or fails verification during the request, observations are cleared and the response is rejected. An unsupported local query never reaches the provider. The adapter currently adds no new retrieval coverage or engineering interpretation; ordering usefulness is unmeasured. Structured output constrains format; local checks enforce the stronger evidence contract. [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses)

Provider mode wraps the unchanged advice contract under `response`, with `model` metadata and a nullable `request_preview`. Metadata includes requested/reported model, status, reason, whether transport was attempted, request SHA-256, response ID and token usage when available. No provider error body or arbitrary error text is returned.

| `model.status` | Meaning | CLI exit |
| --- | --- | --- |
| `dry_run` | Request body preview; no key read or network call | 0 |
| `validated` | Returned IDs/statements passed exact checks; local claim objects follow validated order | 0 |
| `fallback` | Provider/configuration failure, refusal or invalid claims; local observations retained | 3 |
| `skipped` | Local advice abstained before provider use | 2 for normal abstention; 1 for invalid input/catalog |
| `rejected` | Evidence changed or became unverifiable while waiting; claims cleared | 1 |

Invalid CLI/provider options exit 1. Examples of metadata reasons include `provider_not_configured`, `provider_timeout`, `claim_mismatch`, `model_abstained` and `catalog_changed`. Check the metadata as well as the observation result: exit 3 is deliberate, so a fallback cannot silently pass as hosted-model success. The [adapter decision record](../architecture/adr/ADR-003-guarded-model-advice.md) describes the boundary and future review triggers.

## Individual operations

```powershell
.venv/Scripts/python.exe -m ai_command_gateway evaluate --request data/samples/demo-request.json
.venv/Scripts/python.exe -m ai_command_gateway audit --db outputs/demo/audit.sqlite3
.venv/Scripts/python.exe -m ai_command_gateway --help
```

`evaluate`, `approve` and `execute` default to the unqualified policy, so they cannot authorize mock execution unless an explicit synthetic policy is selected. The checked-in request has a fixed timestamp and will become stale; use `demo` for a fresh synthetic example. User requests must contain actual observation times rather than silently refreshed timestamps. `approve` needs `--actor`; `execute` also needs `--approval-id`. Both require the same request, policy and database used for approval. Any state/proposal/policy content change requires reapproval, and execution rechecks freshness.

Decision commands exit 0 for allow, 2 for block/escalate and 1 for CLI/input errors. Actor strings are demonstration labels, not authenticated identities. JSON parsing rejects duplicate keys and non-finite values. No network listener or service is started. See [runbook](../runbooks/README.md) for failure handling and backup.
