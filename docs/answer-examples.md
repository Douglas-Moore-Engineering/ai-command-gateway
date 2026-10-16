# Readable answer examples

Executed from the committed aggregate fixture on 2026-10-16. Reproduce with `python scripts/show_answer_examples.py`. These are software examples, not fresh inspection of the original datasets.

## Offline answer

```text
Question: How many rows are in process_dataset.parquet?

Answer from verified local observations (no model-written explanation).

process_dataset.parquet: row count = 13912 (rows); source observation, qualification unresolved. [1]

Sources:
[1] process_dataset.parquet — /files/2/profile/row_count (source S1; evidence EV-403a76a3ca0d868470d1af0b)

Research observations only. This answer does not authorize equipment actions.
```

## Simulated provider explanation

The following uses hand-authored provider output through the real parser, validation and renderer. No live LLM generated this sentence.

```text
SIMULATED PROVIDER: hand-authored test response; no live LLM inference.

Question: How many rows are in process_dataset.parquet?

Model status: validated (model_validated).
Model explanation: citation bindings and numeric tokens checked; semantic accuracy requires review.

The process dataset contains 13,912 recorded rows. [1]

Sources:
[1] process_dataset.parquet — /files/2/profile/row_count (source S1; evidence EV-403a76a3ca0d868470d1af0b)

Research observations only. This answer does not authorize equipment actions.
```

For a real provider answer, follow the [explanation instructions](demo.md#readable-answers-and-saved-output). The source and its qualification limits remain available alongside the prose.
