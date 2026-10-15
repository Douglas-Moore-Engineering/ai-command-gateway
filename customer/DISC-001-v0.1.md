# DISC-001 — AI Command Gateway customer discovery

Faithful text-and-table transcription of the attached v0.1 document. Original DOCX remains the source baseline.

DOUGLAS MOORE ENGINEERING

AI Command Gateway

Customer discovery | LLM-assisted industrial command validation

DISC-001 • Version 0.1 • 14 October 2026 • America/New_York

Engagement and evidence status

Fictional portfolio discovery, prepared for review. Customer A is a fictional industrial-campus operator. Alex Morgan, Director of Facilities and Energy Operations, is a fictional respondent. Douglas Moore / DME is the delivery lead. All first-person customer answers, budgets, schedules, staffing and policies below are scenario assumptions, not statements from a real company.

Public dataset descriptions provide technical context only. No customer incident, business loss, savings, equipment rating, test result or approval is represented as measured or verified. Dataset files have not been inspected. Sources [S1–S4] are listed at the end.

Customer need

“We want AI to help our operators understand solar and battery conditions and propose useful actions. Before those proposals become commands, we need an independently enforced check against approved operating rules, equipment state and user authority. We also need a clear record of what was proposed, checked and approved.”

Initial scope

One offline reference demonstration for photovoltaic and battery command proposals. The LLM retrieves approved guidance and explains recommendations. A separate deterministic gateway returns allow, block or escalate; an allow result remains a demonstration decision and does not operate equipment.

Primary data candidate: the DOI-registered S7 industrial-control dataset [S1]. GPVS-Faults [S2] and islanded-microgrid measurements [S3] are optional supporting sources, not mandatory combined training inputs. No water or CNC scope is included.

Current lifecycle and stop boundary

Phases 1–2: intake and discovery documentation. This deliverable answers the discovery questions and prepares scope inputs. No implementation, cloud provisioning, live equipment connection or external customer communication is authorized by this document.

Discovery answers | Q-01 and Q-02

Q-01. What problem are you trying to solve, and what does it cost you today?

Customer response: “Our operators review energy-management recommendations and check operating instructions before changing settings. We want to introduce an AI assistant, but we do not want its output to become an unchecked control instruction. Today the review depends on people bringing together equipment conditions, procedures and permissions. We want that review to be more consistent and easier to audit.”

“We have not established a defensible annual cost or recorded an AI-caused equipment incident. For the demonstration, compare operator review with and without the assistant using the same cases. Our finance and operations teams would later validate labor costs, actual incidents and any claimed savings.”

Interpretation: the need is prospective command assurance plus reduced review effort. Do not frame the project as proven loss prevention or failure prediction. Reference workflow: inspect telemetry → consult procedure → review proposal → authorize → log decision. No financial baseline has been measured.

Status: Partial. Evidence: Fictional customer response; technical context [S1]. Follow-up OPEN-01: operations/finance to establish review-time and cost baselines before a business-case commitment. Trace: REQ-01, REQ-04; AC-01, AC-04.

Q-02. What would success look like, and how would you measure it?

Customer response: “Show us that the gateway rejects proposals that violate our approved rules and does not unnecessarily block permitted ones. Each decision should identify the rule, equipment state and authorization used. The assistant should cite the relevant guidance and say when it cannot support a recommendation.”

“We also want operators to review a case faster without losing correctness. We will not accept faster answers if they are misleading. Our controls engineer reviews command correctness; operations reviews usability; security reviews access boundaries; I coordinate acceptance.”

Proposed demonstration objectives: zero prohibited commands accepted in the frozen critical test suite; all required audit fields populated; no execution route available to the LLM; grounded recommendations or explicit abstention. These are proposed scenario criteria, not observed performance or a statistical guarantee. Usability, false-block and response-time targets remain subject to pilot measurement; see the acceptance matrix.

Status: Answered for planning; targets are proposed. Evidence: Fictional. Follow-up OPEN-02: controls engineer and operations must review expected decisions and acceptance thresholds before evaluation. Trace: REQ-01–06; AC-01–06.

Discovery answers | Q-03 and Q-04

Q-03. Who will use the system, and what action should they take?

Customer response: “The primary user is an energy operator. A controls engineer owns the operating rules, and our OT security lead reviews access and suspicious activity. An operator can request advice and submit a proposal for checking. The assistant cannot authorize itself or edit the limits.”

“For this demonstration, an allowed proposal ends at a mock control interface. A blocked proposal displays the reason. An uncertain case goes to the controls engineer. Any future equipment command would need the designated approval and a fresh state check immediately before execution.”

“We will keep our existing controllers and independent protective functions. Loss of this assistant must not stop normal manual operations. We need short operator guidance explaining what an allow decision does and does not mean.”

Status: Answered. Evidence: Fictional. Interpretation: advisory AI with separate authorization and enforcement; no live actuation. Owner: operations lead. Follow-up: role-based workflow review before scope baseline. Trace: REQ-02–04; AC-02–03.

Q-04. What equipment, systems and historical data do you have?

Customer response: “For the portfolio exercise, represent a solar-plus-battery installation with supervisory monitoring and PLC-connected controls. Use the S7 reference dataset for recorded process conditions, target-power commands and on/off signals. Do not imply that these records came from our fictional campus.”

“Our eventual site assessment would require the actual asset list, control interfaces, tag dictionary, engineering limits, procedures, equipment modes and authorized command list. We cannot supply those as verified customer records in this exercise.”

Source-inspected context [S1]: the record lists Siemens PLC 1512 battery logs, PLC 1516 PV logs, network packets and process data. Control-center process records are described at one-second intervals. Available fields include battery state of charge, voltage, current, temperature, PV power and target-power/on-off outputs. This sampling interval is not evidence of gateway response requirements.

Data qualification: physical versus simulated process provenance, units, sign conventions, timestamp alignment, experiment separation, licensing and suitability of labels remain to be checked. Network attack labels are not automatically valid/invalid-command labels. Do not join the three independent datasets as if they describe the same asset or timeline.

Status: Partial. Evidence: Source-inspected metadata [S1–S3] plus Fictional scope. Follow-up OPEN-03 and OPEN-04: DME and controls owner qualify data and document constraints before rule freeze. Trace: REQ-01, REQ-05; AC-01, AC-05.

Discovery answers | Q-05 and Q-06

Q-05. Approved hosting, security and data restrictions?

Customer response: “Start locally in an isolated development environment with public data and no connection to an operational network. We have not selected or approved cloud services for this exercise. If cloud processing is later proposed, show us what information leaves the site, where it is retained, who can access it and what it costs.”

“For an eventual site pilot, the security lead must approve the data flow and access. Equipment credentials must not enter prompts or retrieved documents. Reference documents should be versioned and reviewed. The LLM must not have direct PLC credentials or permission to change the gateway policy.”

Interpretation: hosting and provider selection remain open; Azure/Cosmos DB are not approved requirements. Enforcement must not depend on a successful LLM response or a live cloud lookup. Corrupted, missing or expired policy/state should prevent approval of new AI actions; actual machine response remains an equipment-specific engineering decision.

Status: Answered for offline scope; production hosting Unknown. Evidence: Fictional. Follow-up OPEN-05: security/platform owner to review provider, data retention, network, identity and secrets controls before any external processing. Trace: REQ-02, REQ-05–06; AC-02, AC-05–06.

Q-06. Who will own, operate and support the system?

Customer response: “I own the operational business case. Our controls engineer owns the correctness of operating constraints. The OT security lead owns security acceptance, and our IT/platform owner handles the approved runtime and identities. DME prepares the demonstration, documentation and test evidence.”

“We expect a reproducible local setup, source code, configuration instructions, test results, an operator guide, an escalation procedure and an evidence index. Ongoing support is a separate agreement; we are not assuming a single consultant provides continuous support.”

“Our organization would own site data and site-specific operating policies. DME retains its pre-existing reusable methods; project-code ownership and reuse need a written agreement. On exit, we need exportable records and revocation of any supplier access.”

Status: Answered for scenario; contractual terms not agreed. Evidence: Fictional. Follow-up OPEN-06: sponsor and commercial owner define IP, support hours, escalation, billing and handoff in scope/SOW review. Trace: REQ-04; AC-03. No real individuals have accepted these roles.

Discovery answers | Q-07 and Q-08

Q-07. Required response, downtime and acceptable data loss?

Customer response: “The first demonstration is for supervisory recommendations, not fast electrical protection. An explanation arriving within ten seconds would be a useful starting target. The deterministic decision should be much faster; we propose a 100 ms p95 processing target on the declared local test machine, measured after the complete command and required state are available.”

“Those numbers are demonstration assumptions, not plant deadlines. Our controls engineer must establish actual command deadlines and permissible state age before any live integration. We want measurements under stated load, including worst observed delays and timeouts.”

“If the LLM fails, operators should retain their existing procedures. If the gateway cannot validate a proposal, it must not allow a new AI command. Do not issue a generic emergency stop just because an AI recommendation is invalid.”

“For offline work, a one-business-day restoration objective and daily backups are acceptable planning assumptions. Keep decision records durably written before reporting a completed authorized transaction; an audit-write failure must be visible. Site availability and recovery targets require separate agreement.”

Status: Partial. Evidence: Fictional numerical planning assumptions. Follow-up OPEN-07: controls/platform owners establish timing, workload, freshness and recovery obligations before integration. Trace: REQ-05–06; AC-06. p95 performance does not establish a hard real-time bound.

Q-08. Budget, target date and approval process?

Customer response: “For planning, use a USD 30,000 ceiling for an eight-week offline demonstration after data access and scope agreement. That is a fictional customer budget assumption, not a market quote or authorization to spend. Separate DME fees from third-party charges and our internal effort.”

“Week 1 should establish scope and data feasibility; weeks 2–3 define rules and the evaluation cases; weeks 4–6 implement and evaluate; weeks 7–8 demonstrate, resolve findings and hand over. If source documentation is inadequate, bring that issue to the scope review rather than inventing limits to preserve the schedule.”

“I coordinate the business decision; finance approves spending; controls and security review their areas; the designated site owner approves any future exposure. We want change impacts documented before expanding scope.”

Status: Answered as fictional planning constraints; no commitment approved. Follow-up OPEN-08: DME estimate effort and recurring costs; sponsor reviews affordability before build commitment. Trace: DEC-02. Dates are relative to a future agreed kickoff, not promises from today.

Candidate requirements and verification

All requirements below are candidates for version 0.1. No implementation or test pass is claimed. DME produces evidence; named customer roles below are fictional authority assignments.

| ID / source | Candidate requirement | Verification / acceptance |
| --- | --- | --- |
| REQ-01 / Q-01,02,04 | Validate every proposed command against approved action, units, equipment mode, state and applicable constraints. | AC-01: frozen command cases and boundary tests; controls owner. |
| REQ-02 / Q-03,05 | Prevent the LLM from changing policy or reaching any equipment execution interface. | AC-02: permission inspection and attempted bypass tests; security owner. |
| REQ-03 / Q-03 | Require the designated approval and revalidation of current conditions before eligible execution. Offline output remains mock-only. | AC-02: unauthorized, expired and replayed approval tests; controls/security. |
| REQ-04 / Q-02,06 | Record proposal, source references, rule/model versions, state time, decision, actor and outcome. | AC-03: audit-field and linkage checks; operations. |
| REQ-05 / Q-02,04,05 | Ground recommendations in versioned approved sources; abstain or escalate when evidence is missing or conflicting. | AC-05: independently reviewed source-based case set; controls owner. |
| REQ-06 / Q-05,07 | Prevent new AI approvals when required policy, state, authorization or audit services are unavailable; expose the reason. | AC-06: fault injection and restart tests; controls/platform. |

Measurement and acceptance candidates

| ID / measure | Proposed criterion and evaluation basis |
| --- | --- |
| AC-01 / command errors | Zero forbidden accepts in the critical case suite; report numerator/denominator, event groups and uncertainty. Report valid-command false blocks separately; threshold TBD before testing. |
| AC-02 / authority | Zero observed bypasses in specified permission, replay and direct-access tests. Finite test coverage is not proof against every attack. |
| AC-03 / traceability | 100% required fields and version links in tested decision records. Verify failure behavior when audit storage is unavailable. |
| AC-04 / review effort | Measure median review time and decision correctness on matched cases against manual review. Baseline/target not measured; predefine target before final test. |
| AC-05 / LLM quality | Every consequential recommendation has supporting approved references or abstains. Human domain review determines correctness; model self-grading alone is insufficient. |
| AC-06 / timing/recovery | Candidate p95: gateway ≤100 ms; explanation ≤10 s. Declare hardware, load and measurement boundaries. Also test stale state, outages, restart and audit failure. |

Ownership, cost and unresolved conditions

Lifecycle cost planning record | COST-001

Basis: USD; 14 October 2026; undiscounted 12-month planning horizon including offline demonstration and potential continuation. No actual costs or savings measured. The USD 30,000 ceiling is an assumed procurement constraint, not the calculated total cost of ownership.

| Cost boundary | Owner and next estimate |
| --- | --- |
| One-time delivery | DME: discovery, architecture, data qualification, corpus preparation, development, verification, security review, training and handoff. Estimate hours × rate before scope commitment. |
| Customer effort | Customer sponsor: controls-engineer review, operator evaluation, security/platform review and acceptance. Estimate separately; do not double-count in DME fees. |
| Recurring / third-party | Platform owner: inference, storage, monitoring, licenses, backups, support and revalidation. Quantities and provider rates TBD after hosting/workload selection. |
| Change and exit | DME/service owner: policy/model updates, regression tests, export and retirement. Include low/base/high estimates and contingency in the next cost baseline. |

Open-item register

| ID / owner | Closure evidence and timing |
| --- | --- |
| OPEN-01 / operations, finance | Baseline review-time study and cost basis before ROI/business-case claims. |
| OPEN-02 / controls, operations | Reviewed expected decisions and predeclared thresholds before evaluation freeze. |
| OPEN-03 / DME data lead | Inspected files, rights, provenance, units, cadence, timestamp joins and event-based splits before data acceptance. |
| OPEN-04 / controls owner | Version-matched equipment limits, sign conventions, modes, interlocks and action list before rule freeze; unavailable items remain out of executable scope. |
| OPEN-05 / security, platform | Provider/data-flow, access, retention and secrets review before external processing or site access. |
| OPEN-06 / sponsor, commercial | Scope, ownership, support and exit terms before delivery commitment. |
| OPEN-07 / controls, platform | Timing, freshness, concurrency and recovery requirements before integration qualification. |
| OPEN-08 / DME, sponsor | Low/base/high lifecycle estimate and affordability decision before implementation commitment. |

Governance screen: the current exercise has no physical actuation. Future equipment influence introduces potential physical and operational harm; impact tier remains provisional until the affected assets and credible consequences are assessed. No governance gate, independent assessment or functional-safety certification is claimed.

Source register and discovery read-back

Source descriptions were inspected on 14 October 2026. Dataset DOI links below identify research records, not customer-owned histories. Raw-file quality, complete operational context and redistribution rights must be checked before use.

[S1] Primary command-context dataset

Kellerer et al. (2025), S7 Data Modification Attacks using an Industrial Control System Testbed, version 1.0.0. https://doi.org/10.5281/zenodo.15373938

Supports: recorded process inputs, command outputs, PLC logs and modified-packet labels. Three Parquet files are listed. Does not by itself establish physical safety limits, customer incidents or LLM recommendation ground truth. Physical-versus-simulated process provenance remains unresolved.

[S2] Optional PV fault context

Bakdi et al. (2020), GPVS-Faults: Experimental Data for fault scenarios in grid-connected PV systems under MPPT and IPPT modes, version 1. https://doi.org/10.17632/n76t439f65.1

Supports: laboratory PV fault scenarios in CSV/MAT files. Not required for initial command validation and not a substitute for a reviewed command policy.

[S3] Optional microgrid operating context

Universitat Politècnica de Catalunya (2026), Replication Data for: Decoupled simultaneous complex power sharing and voltage regulation in islanded AC microgrids. https://doi.org/10.34810/DATA2936

Supports: laboratory microgrid experiments and MATLAB plotting resources. Language does not disqualify the data, but variable meanings and units must be verified. Not a synchronized extension of S1.

[S4] Operational context

National laboratory microgrid-control and REopt project descriptions: https://nrel.sitefinity.cloud/grid/microgrid-controls and https://www.nlr.gov/reopt/projects/

Supports general microgrid dispatch, control and resilience context; supplies no evidence of this fictional customer’s losses, budget or achieved benefits.

Read-back and continuation

“You need an offline demonstration that helps energy operators interpret solar/battery conditions, proposes evidence-supported actions, and independently checks those proposals before a mock execution interface. Success means tested constraints, clear authority, traceable decisions and useful operator assistance. We still need qualified source data, authoritative rules, reviewed cases and a defensible cost baseline.”

Review state: prepared for user review; no real customer sign-off. All Q-01–Q-08 topics have a disposition. DEC-01: solar/battery reference setting is a fictional planning baseline. DEC-02: budget and schedule are fictional assumptions. Neither authorizes spending, deployment or equipment access.

Handoff: remain with customer-delivery-service-operations for Phase 3 scope/responsibility review. DME is the preparer; the user reviews the portfolio baseline. Carry OPEN-01–08 forward into standards assurance and production-AI engineering when authorized. Stop after delivery of this discovery document; no project build has begun.
