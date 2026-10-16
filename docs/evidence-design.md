# Local evidence catalog

Version 1.0.0 converts the completed source profile into finite, typed observations. The catalog is context for local advice. Every fact has `kind: observation`, `status: context_only`, `trust_class: source_observed`, and `qualification_status: unresolved`. The catalog explicitly has `authorizes_execution: false`.

`build_catalog(profile_path, inventory_path, output_dir)` writes three files:

- `evidence-catalog.json`: deterministic facts and provenance for all five source files.
- `evidence-profile.json`: a sanitized aggregate snapshot from which every fact can be regenerated.
- `evidence-manifest.json`: byte digests binding the catalog and snapshot to the local build.

The facts retain source ID, fixed filename, SHA-256 byte version, an exact JSON pointer into the original profile, property, scalar value, units and generated statement. Identical inputs produce identical catalog IDs and fact IDs. The original profile digest distinguishes profile versions; fact identity includes the observation and provenance. The local catalog contains no absolute input paths or uploaded data.

## Allowed evidence

The current source adapter admits the five inventory filenames and fixed column names only. It checks the source IDs, formats, byte lengths and SHA-256 digests against code-pinned file identities and the selected inventory. Profile row counts and archive member counts must agree with the inventory. Profiles must report completed inspection and all-row scans. Numeric fields reject booleans, nonfinite values, inconsistent counts and reversed bounds. Timestamp values preserve recorded nanosecond precision and timezone metadata; naive timestamps remain unspecified.

Evidence includes file sizes, row and column counts, per-column null counts, observed numeric minima/maxima/means and nonfinite counts, recorded time bounds, archive counts and the allowlisted packet research labels `normal` and `data_modification`. Physical measurement units remain `unresolved`; a column name alone does not establish units. For example, the observed `in_batt_state_of_charge` maximum is 121.0 in unresolved units. It cannot be promoted to an acceptable battery state, physical limit or permission to issue a command. Research attack labels describe source categories, not command safety outcomes.

Archive README text, script contents, MATLAB text, arbitrary category strings, publisher prose and source-authored statements are excluded from the snapshot and catalog. Their enclosing profile is input data, never instructions. The loader does not accept externally authored fact statements: it regenerates all statement text from code-owned templates, allowlisted names and validated scalar values.

## Verification and trust boundary

`load_catalog(path)` requires both sibling artifacts, rejects duplicate JSON keys and oversized JSON, validates the sanitized inputs, checks the selected inventory and rebuilds the full expected catalog. A hand-edited fact or inserted instruction fails even if someone recomputes the catalog's own checksum. Changing only the snapshot also fails the manifest check. A partially written bundle fails closed.

The manifest is a local consistency record, not a signature or independent attestation. An actor who controls the profile, snapshot, catalog and manifest can forge internally consistent numeric observations. The source digests establish which dataset bytes the profiler claims to have inspected; this loader does not re-read those source files or prove that a supplied profile was honestly computed. Use locally generated profiles and protect the code, inventory and artifact directory. Domain approval, authenticated source signing, protected audit storage and independently verified profiling are future acceptance requirements. The current system must not claim tamperproof evidence or qualified operating knowledge.

`find_conflicts` groups observations by source, file-qualified subject and property. Differing values or units identify conflicts by fact ID; independent sources remain separate. The current single-profile adapter produces one fact per subject/property and rejects duplicate source files or columns. The advice consumer must abstain when selected evidence conflicts, and also when no evidence supports a query.

## Verification fixtures

`tests/fixtures/evidence-source-profile.json` contains captured aggregate observations with archive metadata bodies removed. It contains no dataset records, packet payloads or README instructions. Tests run without the original downloads. They exercise stable regeneration, exact citation pointers, all five identities, malformed numeric/time/category input, archive prompt-injection exclusion, missing and modified manifests, and incompatible facts. The fixture's byte digest intentionally differs from the full original profile because unconsumed archive metadata was omitted.

The JSON contract is [evidence-catalog.schema.json](../data/contracts/evidence-catalog.schema.json). Runtime acceptance is stricter than its structural schema because it also requires canonical regeneration and the pinned inventory binding.
