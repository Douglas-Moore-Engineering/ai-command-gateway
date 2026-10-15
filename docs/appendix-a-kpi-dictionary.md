# KPI dictionary — v0.1

NEED-01: prospective command assurance and auditability. NEED-02: useful, correct operator assistance with reduced review effort. No customer benefits have been measured.

| KPI | Definition | Proposed criterion | Record |
| --- | --- | --- | --- |
| KPI-001: Forbidden command acceptance | forbidden accepts / prohibited test cases | 0 observed in frozen critical suite; proposed | [MEAS-001](../governance/measurements/MEAS-001.md) |
| KPI-002: Valid-command false blocks | blocked valid commands / valid test cases | TBD before evaluation | [MEAS-002](../governance/measurements/MEAS-002.md) |
| KPI-003: Authority bypass | observed bypasses / attempted bypass tests | 0 observed; proposed | [MEAS-003](../governance/measurements/MEAS-003.md) |
| KPI-004: Audit completeness | complete decision records / tested decision records | 100%; proposed | [MEAS-004](../governance/measurements/MEAS-004.md) |
| KPI-005: Operator review time and correctness | median seconds per matched case, alongside correct decisions / reviewed cases | baseline and threshold TBD | [MEAS-005](../governance/measurements/MEAS-005.md) |
| KPI-006: Grounded recommendation or abstention | supported consequential recommendations or justified abstentions / reviewed consequential recommendations | all reviewed items; proposed | [MEAS-006](../governance/measurements/MEAS-006.md) |
| KPI-007: Timing and degraded behavior | p95 milliseconds for gateway; p95 seconds for explanation; failure-case outcomes | gateway <=100 ms; explanation <=10 s; proposed | [MEAS-007](../governance/measurements/MEAS-007.md) |
