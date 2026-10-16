# Synthetic policy reference — synthetic-1

This document defines the artificial `demo-policy-manual` source referenced by the demo policy and fixtures. It is an implementation test specification, not an equipment manual or a finding from the supplied datasets.

Only the fictional `battery-demo-1` asset, `set_battery_power` action, `kW` command unit, and `remote` mode are eligible. The synthetic inclusive command range is −5 to +5 kW. Synthetic state requirements are battery state of charge 20–80 percent and temperature 0–45 degrees Celsius. These chosen values only exercise both sides of a boundary; they have no established physical meaning for S1, S2, S3, or a real battery.

The exact timing limits and authorized local actor are versioned in [demo-policy.json](../config/policies/demo-policy.json). Source references must identify this document as `demo-policy-manual`, version `synthetic-1`. Changing policy content invalidates existing approvals. The demo operator label represents local workflow mechanics and is not authenticated identity.

Every allow is eligibility for the mock adapter only. Physical limits, interlocks, sign conventions, units, action semantics and owner-reviewed cases must be qualified separately before a real policy can be proposed.
