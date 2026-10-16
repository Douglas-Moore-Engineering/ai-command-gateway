# Supplied dataset observations

These are local file observations from 15 October 2026, produced by the first offline increment. They advance OPEN-03 but do not close data qualification, establish equipment limits, or approve a control policy. The original files remain outside Git. The generated report is `outputs/profiles/dataset-profile.json` and follows [the source profile contract](../data/contracts/source-profile.schema.json). The committed [source inventory](../data/lineage/source-inventory.json) retains only aggregate counts and file identities; it contains no source records or readme text.

## Observed files

| Source | Supplied file | Bytes | Observed structure |
| --- | --- | ---: | --- |
| S1 | `logs_dataset.parquet` | 123,121 | 6,459 rows; 7 columns; 1 row group |
| S1 | `packets_dataset.parquet` | 201,835,803 | 10,002,790 rows; 5 columns; 10 row groups |
| S1 | `process_dataset.parquet` | 359,657 | 13,912 rows; 22 columns; 1 row group |
| S2 | `n76t439f65-1.zip` | 203,108,810 | 18 members: 16 MATLAB files, a PDF readme, and a nested CSV ZIP |
| S3 | `doi-10.34810-data2936.zip` | 904,073 | 16 members: 7 MATLAB files, 7 MATLAB scripts, a text readme, and a manifest |

All three S1 MD5 values match the file checksums in the [publisher's Zenodo record](https://zenodo.org/records/15373938). This is evidence of byte identity with that record; it does not establish physical provenance, correctness, or suitability for control. SHA256 identities for the supplied bytes are:

| File | SHA256 |
| --- | --- |
| `logs_dataset.parquet` | `5ea386a66b4ee5c0c5602f3e70e6c118d6d5e208cabf0d99e9c4110b84e4352d` |
| `packets_dataset.parquet` | `5121f480c174f845d243560e8f112ea2ba43dc2922a9f563309cd7c10166ead2` |
| `process_dataset.parquet` | `163613e85346c8913e423014e9c8911a3407dab2456cc10819e6ee9dad2ee7d8` |
| `n76t439f65-1.zip` | `f1494903e3c3ff1ea2972af0daa9793f579b2ac444455bdd5035ebee05b8a042` |
| `doi-10.34810-data2936.zip` | `e4fcab2139c77dca64eed45b95adc4fa41d96c17e810d22d89d2d55fc5acdf5e` |

## S1: alignment and engineering interpretation remain open

All Parquet rows were scanned in batches of 8,192. Schema, null counts, finite numeric extrema/means, and timestamp extrema cover the complete files. No raw records or binary packet payloads are emitted. Category counts retain up to 64 distinct values with explicit overflow accounting; all observed packet labels fit within this cap.

The packet source contains 9,991,107 `normal` and 11,683 `data_modification` labels. These describe source attack annotations, not valid/invalid physical command decisions. `datamod_changes` has 9,991,107 nulls; `s7_datablock` has 9,673,817 nulls. The logs and process files contain no Arrow nulls in any column; that does not imply every measurement is valid.

Timestamp observations require reconciliation before joins:

| Field | Minimum | Maximum | Stored timezone |
| --- | --- | --- | --- |
| Logs `server_recv_ts` | 2025-02-19 03:08:34.106661000+0100 | 2025-02-19 07:00:06.161340000+0100 | +01:00 |
| Logs `device_ts` | 2015-05-18 17:27:12.804000000 | 2015-05-18 21:24:06.717000000 | absent |
| Packets `timestamp` | 2025-02-19 01:59:44.229999000 | 2025-02-19 05:59:32.675575000 | absent |
| Process `archive_recv_ts` | 2025-02-19 02:07:14.956493832 | 2025-02-19 06:00:12.745930709 | absent |

The device clock differs by years from the server clock. Timestamp ranges alone cannot establish a reliable join. The profiler preserves nanosecond precision and does not invent UTC offsets for fields without timezone metadata.

The process schema contains PV and battery observations plus `out_pv_on_off`, `out_pv_target_power`, `out_batt_on_off`, and `out_batt_target_power`. Observed raw `in_batt_state_of_charge` ranges from 36 to 121. The raw battery target-power value is 500,000 in every row; raw PV target-power values range from 0 to 65,445. These numbers require source-specific units, scaling, validity flags, sign conventions, and scenario interpretation. They are not automatically percentages, watts, safe limits, or approved commands. No limits were learned from these distributions.

## S2 and S3 remain independent supporting collections

S2 MATLAB files use MATLAB v7.3/HDF5. Root metadata identifies MATLAB table objects. HDF5 storage shapes are recorded as storage metadata and are not reported as logical observation counts. The nested `CSV_Files.zip` contains 21 members, including 16 CSV files and directory/macOS metadata entries, with 493,431,482 total uncompressed bytes. Its member names, sizes, and CRCs are inventoried without extracting or scanning CSV rows. The PDF readme is hashed, but its text is not parsed by this increment. Dataset identification and license context are available in the [GPVS-Faults publisher record](https://data.mendeley.com/datasets/n76t439f65/1).

S3 MATLAB files each expose 114 top-level variables through metadata inspection. Examples include `export1_1` with shape 2,048 × 1, `t_1` with shape 1 × 2,048, and label/cell variables. Variable names and shapes do not establish complete engineering semantics. The supplied `Readme.txt` claims laboratory microgrid measurements and CC0 1.0 licensing, consistent with the identity of the [DATA2936 record](https://doi.org/10.34810/DATA2936). Those statements are retained as source claims; the text's instructions to run MATLAB scripts are not executed.

Neither S2 nor S3 is joined to S1, used as an extension of its asset timeline, or treated as command safety ground truth. No model training, operational validity labels, or production performance claims are derived from these files.

## Reproduction and limits

From the repository root after installing the project:

```powershell
.venv/Scripts/python.exe -m ai_command_gateway profile --input-dir C:\Users\moore\Downloads --output-dir outputs/profiles
```

The report records per-file missing/error status instead of silently omitting files. Archive member paths are never extracted; absolute/traversal paths and symbolic links are flagged and skipped. Outer member hashes are streamed. MATLAB inspection is capped at 16 MiB per member, source text at 64 KiB, other inspected members at 256 MiB, archive uncompressed content at 512 MiB, and inventories at 10,000 members. Nested ZIP metadata inspection stops after one level and uses a temporary spool with an 8 MiB memory threshold. Nested member CRCs are metadata observations, not independently verified SHA256 hashes. HDF5 external links are not followed.

A file status of `profiled` means a report was produced. `inspection_complete` and the report's `inspection_summary` separately show whether all configured checks completed. Skipped, blocked, malformed, or duplicate archive entries produce a partial inspection summary. Deliberate metadata-only scopes, such as nested ZIP inventories and PDF hashes, are recorded explicitly; completion does not mean every member was semantically decoded. Source qualification remains unresolved even when all configured inspections complete. The first complete local run of this implementation took 7.81 seconds; this single execution is not a benchmark or an SLO result.

Focused automated tests cover complete batch statistics, nonfinite values, nulls, dictionary columns, empty files, category overflow, nanosecond preservation, missing/corrupt inputs, immutable source hashes, unsafe archive names, nested inventories, MATLAB metadata, and HDF5 external-link handling. Fixtures exercise parser behavior and are not substituted for the supplied source records.
