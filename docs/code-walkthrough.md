# Code walkthrough

The sole executable is [check_repository.py](../scripts/check_repository.py): enumerate repository Markdown → resolve local file links → load candidate requirement and acceptance IDs → check trace references → verify the original discovery SHA-256 → reject embedded internal skill files → exit nonzero on discrepancies.

It uses only Python's standard library and makes no network calls. It checks file targets, not external URL availability, anchor rendering, safety, application correctness or acceptance. Application input validation, policy evaluation, retrieval, inference, audit and failure handling remain unimplemented.
