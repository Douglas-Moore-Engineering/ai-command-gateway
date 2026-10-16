# Source semantics and qualification evidence

The second offline increment adds identity-bound timestamp and numeric quality checks. The full supplied-file run on 15 October 2026 matched all five committed SHA256 identities, analyzed every numeric/timestamp value in the three S1 Parquet files, and generated 28 aggregate evidence facts. S2 and S3 receive archive identity checks in this increment; their measurement semantics remain unqualified. No raw rows are included here.

The implementation is [qualification.py](../src/ai_command_gateway/qualification.py), and its output is `outputs/qualification/source-qualification.json`, following [the qualification contract](../data/contracts/qualification.schema.json). Each evidence fact includes its source file SHA256, field, report locator, canonical-content SHA256, and stable evidence ID. These hashes establish content identity, not publisher authenticity or approval. The report binds to the exact bytes of [the committed inventory](../data/lineage/source-inventory.json). Missing, mismatched, malformed, or changed-during-analysis sources yield explicit statuses and no evidence from that failed analysis.

## Full S1 timestamp observations

Times are measured in stored row order. Cadence statistics use positive differences between adjacent, non-null rows; they exclude equal/decreasing transitions. Duplicate counts include every repeat after the first occurrence, including nonadjacent repetitions. The displayed seconds are conversions from the report's exact integer nanoseconds, not assumptions about clock offsets.

| File / field | Rows | Stored timezone | Decreasing adjacent pairs | Repeated timestamp rows | Positive delta p50 (s) | Positive delta maximum (s) |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| Logs / `server_recv_ts` | 6,459 | +01:00 | 1 | 0 | 0.797428 | 175.219876 |
| Logs / `device_ts` | 6,459 | absent | 407 | 0 | 0.941 | 443.891 |
| Packets / `timestamp` | 10,002,790 | absent | 0 | 2,966,555 | 0.000627 | 0.03225 |
| Process / `archive_recv_ts` | 13,912 | absent | 0 | 0 | 1.011444222 | 66.970768608 |

All four timestamp fields have zero Arrow nulls. Packet and process timestamps are nondecreasing across their complete stored row order. Logs have decreasing transitions on both clocks. Repeated packet timestamps do not by themselves establish duplicate packets or faulty measurements.

The report also counts positive deltas greater than ten times the positive-delta median: 216 server-log, 524 device-log, 715,259 packet, and one process interval. This is a descriptive, per-field outlier rule. It does not establish missing samples, expected periodicity, latency, or an operational threshold. Event-triggered records and packet traffic need not be periodic. No records are reordered, clocks corrected, or sources joined.

## Publisher claims versus local observations

The S1 publisher describes process records collected once per second and saved in a database; `in_` fields represent monitoring inputs, `out_` fields represent control outputs, and `state_` fields represent calculated power-flow state. Logs describe changes passing a minimum reporting threshold. Their device timestamps begin in 2015, while `server_recv_ts` records server receipt. These are source-reported meanings, not an independently validated engineering dictionary. The measured process median is close to one second, while the maximum interval shows that the stored sequence is not uniformly spaced. [S1 publisher record](https://zenodo.org/records/15373938)

The publisher-linked attack repository uses `fields_limit` in signal-randomization routines that construct attack values. Those numbers cannot be promoted into equipment safety limits. Its battery target field encoding also does not establish a conversion for the Parquet battery target value of 500,000; an encoding-to-column mapping is still required. Only the source text was reviewed. Supplied or linked attack scripts were not executed or imported. [Publisher-linked packet implementation](https://github.com/nbke/s7-attacks/blob/main/src/s7_datablock.py)

The S3 supplied `Readme.txt` states that the MATLAB files contain laboratory measurements for six microgrid inverters and that embedded labels identify physical quantities. It reports CC0 1.0 licensing. These remain source claims: this increment does not map every MATLAB variable, parse its time series, or verify its physical units. The readme's directions to run MATLAB plotting scripts are document contents, not task instructions. [S3 publisher record](https://doi.org/10.34810/DATA2936)

S2 retains its independent PV-fault context. Its archive, MATLAB metadata, and nested CSV manifest were inspected by the first increment; this increment checks the same archive identity without decoding the PDF readme or scanning CSV measurements. [S2 publisher record](https://data.mendeley.com/datasets/n76t439f65/1)

## Engineering meaning remains unresolved

All 21 numeric process fields and all three numeric log fields were scanned completely. They contain zero null or nonfinite numeric values. This establishes finite stored numbers, not physical validity. Every field receives explicit unresolved engineering semantics in the report: units, scale, sign convention, and validity rules. No candidate scaling is applied.

| Field group | Supported observation | Missing qualification |
| --- | --- | --- |
| Process `in_*` | Source-described monitoring inputs; complete finite-value scan | Engineering units, scaling, sign, sensor/asset mapping, validity flags |
| Process `state_*` | Source-described calculated state; complete finite-value scan | Model definition, units, scaling, assumptions, validity domain |
| Process `out_*` | Source-described control outputs; complete finite-value scan | Encoding, command units, sign, authority, approved limits |
| Log `old_value` / `new_value` | Finite stored numeric values | Per-`field_name` semantics and engineering conversion |
| `archive_id` / `__index_level_0__` | Numeric fields in the supplied schema | Identifier/ordering semantics; not a physical measurement |
| Timestamp fields | Stored units, timezone metadata, ranges, row order, repeats, cadence | Clock basis, offset/drift, synchronization, experiment boundaries |
| Text/binary fields | Schema metadata only in this increment | Record meaning and any additional content checks |

In particular, observed raw state-of-charge values of 36 through 121 are not assumed to be percentages, and the constant battery target value 500,000 is not assumed to be watts. Packet labels retain their research annotation meaning. None of these facts supplies physical command-validity ground truth.

## Reproduction and limits

The public Python entry point is:

```python
from pathlib import Path
from ai_command_gateway.qualification import qualify_sources

qualify_sources(
    Path("C:/Users/moore/Downloads"),
    Path("outputs/qualification"),
    Path("data/lineage/source-inventory.json"),
)
```

Numeric values are processed in batches of 65,536. Exact timestamp duplicate counts and cadence order statistics retain integer timestamp arrays, with a 20,000,000-row cap per file. A source above the cap is explicitly partial; timestamp rows are not silently sampled. Binary payloads and text contents are not decoded. Quantiles use the nearest-rank definition. Null timestamps break adjacent-pair evaluation; a monotonicity assertion for the whole sequence remains unknown when nulls occur or fewer than two rows exist.

The supplied run completed in 4.47 seconds on the local development machine; this single execution is not a benchmark. Fourteen focused tests cover null boundaries, cross-batch and nonadjacent repeats, timezone/nanosecond preservation, unsigned interval overflow, cadence outliers, finite/nonfinite values, payload-column exclusion, resource caps, stable evidence identities, invalid inventories, changed source bytes, and missing/corrupt inputs. Semantic qualification, clock alignment, equipment approval, and operating constraints remain open.
