# Operating instructions

No application or service is deployed. Repository inspection: run `python scripts/check_repository.py` from the root; a failure identifies a broken reference or baseline inconsistency. Correct the underlying file, review the diff and rerun.

Before a future offline demo, document start/stop, input acquisition/integrity, missing/stale-state behavior, escalation, audit failure, export/backup and restoration. No equipment or cloud rollback is currently applicable because neither is connected. Preserve the original discovery source and its checksum during changes.
