# Data qualification

No raw dataset is downloaded or redistributed. Metadata statements below are carried from DISC-001, not newly verified file observations.

| Source | Role | Record | Qualification |
| --- | --- | --- | --- |
| S1: S7 ICS testbed v1.0.0 | Primary command context candidate | https://doi.org/10.5281/zenodo.15373938 | OPEN-03: inspect provenance, license, files, schemas, units, sign conventions, timestamps, experiment groups and labels |
| S2: GPVS-Faults v1 | Optional PV fault context | https://doi.org/10.17632/n76t439f65.1 | Not mandatory; independent experiment |
| S3: islanded AC microgrid experiments | Optional operating context | https://doi.org/10.34810/DATA2936 | Not mandatory; independent experiment |

S1 attack labels are not ground truth for physically valid commands. Source data may include simulated process behavior; physical provenance remains unresolved. Do not combine independent sources as one asset timeline. Approved policies, source guidance, command schemas and reviewed cases are separate prerequisites. Preserve immutable raw files with hashes outside Git; derive validated and contextualized layers only after qualification. Feature-store necessity, splits and any learning task remain undecided.
