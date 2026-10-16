# Data qualification - v0.3

All five user-supplied files were inspected locally on 2026-10-15. Raw bytes remain in the user's Downloads directory, outside Git. [Observed schemas, hashes, timestamps, labels and limitations](../docs/data-observations.md) record the evidence. The generated full report is `outputs/profiles/dataset-profile.json`; the compact [source inventory](lineage/source-inventory.json) binds observed file identities.

The v0.3 `qualify` command checks those identities and analyzes every S1 numeric/timestamp row. Its separate report, `outputs/qualification/source-qualification.json`, records exact timestamp repetition, stored-order transitions, positive-delta cadence, and finite/nonfinite/null numeric counts. The supplied run found 2,966,555 repeated packet timestamps and a maximum process interval of 66.970768608 seconds. These are descriptive observations, not source joins or physical validity findings. [Source semantics](../docs/source-semantics.md) records scope, source-reported meanings and unresolved conversions.

| Source | Role | Supplied files | Remaining qualification |
| --- | --- | --- | --- |
| S1: S7 ICS testbed v1.0.0 | Primary historical command context | logs/process/packets Parquet | Units, source-to-asset semantics, physical provenance, clock alignment, rights and experiment groups |
| S2: GPVS-Faults v1 | Independent optional PV fault context | n76t439f65-1.zip | Logical table/CSV ingestion and units/labels; no S1 join |
| S3: islanded AC microgrid | Independent optional operating context | doi-10.34810-data2936.zip | Variable meanings, experiment mapping and verified license scope; no S1 join |

Source records: [S1](https://zenodo.org/records/15373938), [S2](https://data.mendeley.com/datasets/n76t439f65/1), [S3](https://doi.org/10.34810/DATA2936). Source claims are distinguished from inspected byte-level observations. A matching publisher checksum is file identity, not physical validation. No supplied MATLAB program is executed, and archive text is never interpreted as agent instructions.

The [profile contract](contracts/source-profile.schema.json) describes generated observations. The [command contract](contracts/command-request.schema.json) describes qualified synthetic request shape, with explicit state units and UTC time. Historical replay retains a separate unqualified representation and cannot reach the allow path. Synthetic samples under `samples/` belong to software tests and are not replacements for the real files.

The [qualification contract](contracts/qualification.schema.json) adds identity-bound aggregate evidence. The [catalog contract](contracts/evidence-catalog.schema.json) describes controlled observation facts used by local advice. `catalog` consumes the aggregate profile, excludes source-authored prose, and writes a catalog/snapshot/manifest bundle. `advise` verifies and retrieves exact cited statements; it cannot authorize commands. These artifacts preserve independent source IDs and unknown engineering units. [Evidence design](../docs/evidence-design.md) explains the local consistency boundary and why it is not an authenticity guarantee.

[The frozen advice casebook](evaluation/advice-cases-v1.json) supplies engineer-authored retrieval, citation and abstention regressions for `eval-advice`. It is not independent domain acceptance, a model training split, or physical command ground truth. The [demo guide](../docs/demo.md) provides the complete command sequence.

S1 attack labels are not physical command-validity labels. The three research collections are not one asset timeline. OPEN-03 remains open; successful profiling does not approve dataset redistribution, units, equipment limits, validity labels, or a learning task. Derived local outputs are ignored by Git and retained until the user removes them; no automatic retention or external processing is configured.
