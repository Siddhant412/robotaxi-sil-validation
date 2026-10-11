# Robotaxi Ride-Service Validation Lab

## Project context and implementation brief

**GitHub repository:** `robotaxi-sil-validation`  
**Project type:** Software-only system integration and Software-in-the-Loop (SIL) validation lab  
**Primary language:** Python  
**Primary tools:** FastAPI, Pytest, SUMO/TraCI, Playwright, SQLite, Git, optional Docker Compose

## 1. What we are building

Build a small but working robotaxi ride service and an automated validation framework around it. The service includes a passenger web interface, backend ride management, a vehicle agent, SUMO vehicle simulation, and an operator workflow. Tests exercise the integrated system through real HTTP interfaces, inject faults at communication boundaries, observe the resulting behavior, and produce evidence of correctness or failure.

The project answers:

> Does the passenger app, backend, and vehicle agree about the ride when messages are delayed, duplicated, reordered, or lost, or a service restarts?

It must execute a complete ride: request, assignment, approach, boarding, transport, drop-off, and completion. It must also handle cancellation, interrupted connectivity, stale updates, and changes to pickup locations.

The main product is the validation capability: requirements, repeatable scenarios, independent test oracles, failure evidence, and readiness reports. The ride service is the real system under test, not a collection of mocked API responses.

### Example failure

A vehicle receives a pickup assignment and begins approaching the passenger. Its acknowledgement is lost, so the backend retries the same assignment, but this duplicate message is delayed in transit. Meanwhile, the passenger cancels the ride, and the vehicle receives and acknowledges the newer cancellation instruction. The delayed assignment retry then arrives. A defective vehicle agent accepts this outdated instruction and resumes the cancelled pickup. The lab must reproduce and detect this behavior, show the message sequence and conflicting mission versions, and verify through a regression test that the corrected agent rejects the obsolete assignment.

No physical hardware, paid cloud service, mobile device, or real autonomous vehicle is required. Run locally. The passenger web interface stands in for a mobile client; do not claim native mobile testing.

## 2. Why this project matters

Completing a ride depends on more than vehicle navigation. Passenger requests, durable backend state, vehicle commands, telemetry, and operator actions must work together despite imperfect communication.

## 3. What qualifies as SIL here

The actual backend, communication logic, and vehicle-agent application execute. SUMO replaces the physical vehicle and traffic environment. Commands change the simulated vehicle's mission; observed execution changes backend state and what the passenger sees.

The loop is:

1. A client requests a ride through the real backend API.
2. The backend creates durable ride state and commands.
3. The running vehicle agent receives the commands across HTTP.
4. The agent applies routes/stops to SUMO through TraCI.
5. SUMO advances the vehicle and reports its actual position and stop state.
6. The agent emits execution feedback.
7. The backend processes feedback and the passenger interface updates.
8. Tests check evidence from the complete loop.

This is **ride-service and mission-execution SIL**. Perception, sensor fusion, trajectory planning, steering/braking controllers, HIL, and physical robotics are outside scope. Logical boarding and door state are simplified application abstractions; they are not simulated actuator validation.

Tests using a fake simulator are useful component tests, but must be labeled separately. A SIL suite cannot silently substitute a mock when SUMO is unavailable.

## 4. Scope and non-goals

### Required first release

- One SUMO vehicle and one active mission per vehicle.
- A small synthetic road network with valid pickup/drop-off points and designated holding locations.
- A working FastAPI backend with durable SQLite state.
- A separate running vehicle-agent process controlling SUMO through Python TraCI.
- A passenger browser interface and minimal operator interface.
- A fault relay for repeatable communication faults.
- Pytest integration/SIL tests and a small Playwright UI suite.
- Structured logs, independent invariant checks, failure bundles, and a readiness report.
- One documented injected defect, fix, and regression demonstration.

Default episodes have one passenger request. A targeted assignment-concurrency test may submit two requests to prove that a vehicle cannot be double-assigned. A fleet is not required.

### Defer

Deep RL, MDP optimization, C++ routing, ROS, CARLA, real maps, real traffic, payment processing, Kubernetes, production cloud deployment, native mobile apps, elaborate dashboards, full event-stream infrastructure, automated Jira integration, and exact simulator-state replay.

## 5. Architecture

### A. Passenger interface

A small browser application provides request creation, ride status, assigned pickup point, cancellation before boarding, connectivity/staleness messaging, and completion. Polling is sufficient initially. Use server revisions to avoid applying older responses after newer ones.

The UI must distinguish:

- Request pending versus assigned.
- Approaching versus ready for boarding.
- Cancellation requested versus vehicle-confirmed cancellation.
- Fresh vehicle status versus stale/unknown status.
- Ride completed versus exceptional failure.

Never display stale last-known position as live. The UI is part of the test scope, not a decorative dashboard.

### B. Ride-service backend

Use FastAPI/Pydantic and SQLite. The backend is authoritative for ride lifecycle, mission intent, assignment ownership, mission versions, cancellation intent, and operator actions. Vehicle execution is authoritative for actual vehicle progress; a requested transition is not proof it occurred.

Persistence includes rides, assignments, durable outgoing commands, processed incoming event IDs, audit events, idempotency records, and completion side-effect records. Commit state changes and outgoing commands in one transaction so a restart cannot persist one without the other.

Use a single backend process initially. Document that SQLite and this deployment are not evidence of production HA. Concurrency correctness still requires atomic transactions and constraints.

### C. Vehicle agent

A real application process receives commands, validates versions/expiry, maintains local mission state, controls SUMO, and emits progress/acknowledgement events. Persist active mission/version, processed command IDs, terminal tombstones, and unsent feedback so a restart does not erase ordering safeguards.

One agent owns the TraCI connection and advances SUMO. No test, UI, or other component independently steps the simulator. Control endpoints serialize access to the simulation owner; a threaded web server must not issue concurrent TraCI calls.

The agent polls commands and posts events through the relay using real HTTP. Acknowledgements occur only after required state is durably recorded. Retried commands/events are normal, not exceptional.

### D. SUMO simulation

Use a small synthetic neighborhood with an initial parking/holding position, pickup point A, alternative point B, and a drop-off point. Include valid routes and stops. SUMO supplies actual road motion, vehicle position, speed, and stop state.

Boarding/alighting are application-level dwell events guarded by vehicle arrival, suitable modeled point, and passenger readiness. Do not emit pickup/completion just because a timer elapsed or a command was accepted.

Synthetic curb occupancy is a lab model: it informs the agent and prevents service at a modeled unavailable location. If occupancy does not physically obstruct a SUMO lane, say so. Avoid claiming collision or curb-safety validation.

### E. Fault relay

A small separate service sits on the backend-agent message path. It can queue/delay delivery, duplicate, reorder, drop a message, suppress acknowledgements, and reject traffic for a simulated partition. Every injection is recorded with message ID, rule, start/end, and delivery attempt.

This is controllable application-message fault injection over a real process/HTTP boundary. It is not packet-level emulation of cellular networks. A real HTTP timeout test should actually interrupt a connection or make a process unavailable; do not equate a delayed queue entry with a TCP timeout.

Use deterministic rules such as 'delay first assignment until after cancellation is delivered' rather than brittle sleeps. Scope rules by run ID and direction so faulting telemetry does not accidentally break test-control access.

### F. Operator interface

Provide an exceptions list and ride timeline. Allow defined actions such as selecting an eligible alternative pickup, retrying an unacknowledged current command, or acknowledging an incident. Every action records operator identity (local demo identity is sufficient), reason, ride ID, expected revision, and outcome.

Operators change mission intent; they do not remotely steer the vehicle. Reject invalid or obsolete actions. Minimal local-only lab access is enough; do not expose control endpoints publicly or claim production authorization.

### G. Validation harness

Pytest launches isolated runs, creates requests, configures faults, advances the SIL loop, checks requirements, collects evidence, and cleans up. Playwright exercises a small set of passenger/operator UI workflows against the same integrated service.

The harness is independent of the implementation's state-transition functions. Use public APIs, relay evidence and simulator observations, rather than simply calling backend validation code again as the test oracle.

## 6. Mission and execution semantics

### Backend lifecycle

Normal: REQUESTED → ASSIGNED → APPROACHING → READY_FOR_BOARDING → IN_TRIP → DROPOFF_READY → COMPLETED.

Before boarding: a valid cancellation sets CANCEL_REQUESTED and emits a new-version revocation. CANCELLED is confirmed after the agent acknowledges quiescence, or after the applicable execution lease has expired with no remaining authorization under the defined model. In a partition, the UI must not imply instantaneous vehicle acknowledgement.

FAILED is an exceptional terminal outcome with a reason and evidence. Loss of telemetry alone marks vehicle status stale and may create an operator incident; it is not automatically proof that the ride failed or completed.

After boarding, ordinary cancellation is rejected with a documented conflict response. Supporting early drop-off is a separate feature and is not required initially.

### Required invariants

| ID | Requirement |
| --- | --- |
| R01 | Repeated creation with the same idempotency key and payload creates exactly one logical ride |
| R02 | A vehicle has at most one active assignment |
| R03 | A terminal mission cannot be reactivated by old commands or events |
| R04 | Only valid next lifecycle transitions occur; late events cannot regress ride state |
| R05 | Boarding occurs only after observed vehicle arrival, stop readiness, and passenger readiness |
| R06 | Completion occurs only after observed drop-off and alighting; completion effects occur once |
| R07 | Commands/events have durable identity and bounded, explicit retry behavior |
| R08 | A backend restart retains mission intent, outgoing commands, processed events, and audit history |
| R09 | Stale telemetry is visibly labeled and never presented as current |
| R10 | Eligible pickup updates converge across agent, backend, and UI after communication recovers |
| R11 | Confirmed cancellation prevents future execution of that mission |
| R12 | During disconnection the agent follows the specified bounded local fallback and stops accepting expired authorization |
| R13 | Operator actions validate current revision and record an audit trail |
| R14 | Unexpected simulator teleportation/removal or test infrastructure failure cannot yield a false pass |

Maintain a requirements-to-tests matrix. Several tests may exercise the same requirement under different boundaries.

## 7. Message ordering, idempotency, and partition behavior

### Identity and versions

- run_id: test isolation and evidence correlation.
- ride_id / mission_id / vehicle_id: domain identity.
- command_id / event_id: stable logical identity across retries.
- delivery_attempt_id: unique per transport attempt.
- mission_version: backend-issued monotonic intent revision.
- vehicle_command_sequence: persistent per-vehicle command ordering, including revocations.
- producer_sequence: persistent event ordering for an agent; record a boot/session ID for diagnostics.
- server_revision: backend state revision used by UI/operator updates.
- causation_id: event/command that caused the new event.

Use expected revisions for competing changes. Old telemetry can update a historical timeline but cannot overwrite current mission intent. Track seen event IDs and sequence high-water marks transactionally, while defining how intentionally late but useful events are handled.

Idempotency keys are scoped to the client/request endpoint. Same key and same payload returns the original result; same key and different payload returns conflict. Command retries reuse command_id. Event retries reuse event_id. Claim at-least-once delivery with idempotent application processing, not magical exactly-once network delivery.

### Cancellation and the unavoidable partition boundary

A vehicle cannot know about a cancellation it has not received. Do not promise that an isolated vehicle stops instantly when a passenger clicks cancel.

Use ordered cancellation/version tombstones and bounded execution authorization. Commands include an authorization expiry in the shared logical clock. When authorization expires or the vehicle loses connection beyond the configured interval, the local agent stops progressing the mission using a designated holding procedure supported by the scenario. The vehicle's actual motion must respect SUMO's normal safety behavior; do not teleport or force an instantaneous stop.

For the core stale-assignment demonstration, deliver the cancellation revocation first, receive its acknowledgement, then deliver the old assignment. It must be rejected without any new route execution. This isolates the ordering bug without falsely asserting knowledge across a partition.

For partition tests, define deadlines for detecting lost authorization, initiating holding behavior, reaching holding where possible, and eventual reconciliation after restoration. Report impossible holding/reachability as an explicit exceptional condition. Do not call the simplified behavior a certified minimal-risk maneuver.

Lease refresh follows current mission intent. A refresh for an obsolete/cancelled mission must not revive it. Agent restart must retain tombstones/high-water marks and reconcile against current backend intent before resuming.

## 8. Suggested APIs and data contracts

These are project interface proposals, not SUMO APIs. Finalize schemas early and keep them versioned.

| API | Purpose |
| --- | --- |
| POST /rides | Create a ride using an Idempotency-Key header |
| GET /rides/{id} | Current lifecycle, revision, pickup, telemetry freshness |
| POST /rides/{id}/cancel | Request pre-boarding cancellation with expected revision |
| POST /rides/{id}/pickup | Operator-selected eligible alternative with expected revision |
| GET /vehicles/{id}/commands | Retrieve unacknowledged durable commands |
| POST /vehicle-events | Submit acknowledgements/progress with stable event identity |
| GET /operations/incidents | List unresolved exceptions |
| GET /rides/{id}/timeline | Correlated domain audit trail |
| GET /health and /ready | Liveness and readiness, separately |

Local lab-control endpoints configure relay faults, step simulation, collect observations, and reset a run. Keep them separate from product APIs and unavailable in ordinary product mode.

Request fields: origin/destination IDs, passenger-ready flag or modeled readiness time, allowed walking limit, client ID. Command fields: kind, current mission version, sequence, validity deadline, target, and causation. Event fields: kind, mission version, sequence, simulator time, observed vehicle location, and current execution state.

Validate identifiers, route/stop references, enum values, nonnegative times, and expected revisions. Return clear conflicts for stale updates. Cap retries and queue growth, and record failures.

## 9. Simulation clock and deterministic orchestration

Use one explicit simulation clock for modeled travel, relay scheduling, heartbeats/authorization in deterministic SIL runs, and domain deadlines. The agent owns SUMO stepping; the harness requests a bounded number of steps through serialized lab control.

A step should have a documented order, for example:

1. Apply fault rules and release messages due at the current tick.
2. Process available commands and lease updates.
3. Advance SUMO one step.
4. Observe vehicle execution and create feedback.
5. Deliver due feedback and update backend projections.
6. Evaluate temporal assertions and record evidence.

Use bounded request timeouts and bounded 'advance-until' helpers. Do not let a blocked HTTP request freeze the step owner forever. If a service is intentionally down, that channel reports failure and the simulation can continue.

Wall-clock time separately measures API/computation latency, process startup/recovery, and test watchdogs. Every metric declares which clock it uses. A scenario reporting 'five seconds' must say whether it is simulated or wall time.

For realistic process-restart tests, terminate and relaunch the actual process with its database retained. Do not emulate a restart by clearing an in-memory flag. A replay from seed/config is a scenario rerun, not guaranteed exact simulation-state replay. Record event order as additional evidence and document reproducibility limits.

## 10. Test plan and scenario catalog

Each case specifies requirement IDs, preconditions, stimuli, fault boundary, expected outcomes, temporal bounds, forbidden outcomes, and required artifacts. Inject through product or lab-control interfaces; direct database edits are limited to explicit migration/corruption tests.

| Test ID | Scenario | Primary oracle |
| --- | --- | --- |
| T01 | Normal full ride | Actual vehicle reaches both stops; valid lifecycle; one completion record |
| T02 | Duplicate request after lost response | Same ride returned and no second mission |
| T03 | Two requests compete for one vehicle | At most one active assignment; other request handled explicitly |
| T04 | Cancel while approaching | Cancellation intent → agent quiescence → confirmed cancellation |
| T05 | Delayed assignment after acknowledged cancellation | Old command rejected; no route reactivation |
| T06 | Duplicate command / acknowledgement loss | One logical execution; retry identity preserved |
| T07 | Reordered progress events | Current lifecycle never moves backward |
| T08 | Communication partition during approach | UI staleness + bounded local fallback + reconciliation |
| T09 | Backend restart with an active mission | Durable state restored; no duplicate mission/completion |
| T10 | Agent restart after cancellation | Persistent tombstone rejects old assignment |
| T11 | Pickup A becomes occupied | Eligible update to B reflected across vehicle/backend/UI |
| T12 | Duplicate trip completion | One terminal transition and one receipt/audit side effect |
| T13 | Stale operator pickup update | Conflict; newer mission remains authoritative |
| T14 | Old heartbeat or lease after revocation | Cannot renew an obsolete mission |
| T15 | Cancellation races with boarding | Transaction ordering gives one defined outcome; no cancelled-and-onboard contradiction |
| T16 | Simulator exit or unexpected vehicle teleport | Explicit fail/error; no fabricated success |

Initial critical suite: T01, T02, T04, T05, T07, T08, T09, T12. Expand after the first full ride runs reliably. UI tests must cover normal status progression, cancellation pending/confirmed, stale telemetry, and changed pickup point.

### Example: T05

- Preconditions: vehicle idle; request created; assignment version 1 held by relay.
- Stimulus: cancel the ride; deliver revocation version 2; observe durable acknowledgement and cancellation confirmation.
- Fault release: deliver the old assignment version 1.
- Required outcome: agent logs obsolete-command rejection; backend remains CANCELLED; no new route/boarding occurs.
- Temporal check: observe over a configured number of simulation ticks sufficient for the bug to manifest.
- Artifacts: relay schedule, original/revocation command IDs, accepted/rejected versions, backend transitions, SUMO trajectory, agent state, UI screenshot.
- Failure example: vehicle begins pickup approach from the obsolete command.

### Oracles and negative evidence

Check behavior independently using simulator position/stop state and public domain state. An agent saying 'cancelled' is not by itself proof the vehicle stopped executing. Observe the relevant interval. Avoid equating 'no log line' with proof of no action unless capture completeness is verified.

Use eventual assertions with explicit time bounds and always/assert-never checks over a recorded interval. Account for intentionally delayed processing. Distinguish a product failure, simulator failure, fixture failure, and failed test assertion.

## 11. Logs, incident evidence, and defect lifecycle

Emit structured JSONL with run, scenario, build/version, component, ride, vehicle, command/event identity, mission version, sequence, causation, simulated time, wall time, and outcome/reason. Capture relay actions and simulator position samples. Avoid real personal information; use synthetic passengers.

Do not infer cross-process causality from timestamps alone. Sequence numbers and causation IDs support the timeline, including clock-offset experiments. Store both attempted delivery and successful application.

Each failure bundle contains scenario configuration/seed, tested commits/versions, dependency versions, commands, service logs, relay trace, SUMO outputs, assertion details, UI screenshot where applicable, and rerun instructions. Capture artifacts even when teardown or an assertion fails. Record artifact gaps.

Create one local defect report with: summary, severity rationale, requirement violated, expected/actual behavior, reproduction, evidence, confirmed root cause or explicitly tentative hypothesis, fix, regression test, and verification result. GitHub issue drafts are sufficient; publishing issues or sending messages requires separate authorization.

For the demonstration use a clearly labeled intentional fault implementation, such as a legacy agent that ignores revocation versions. Run it in an isolated test profile and show the suite failing, then show the corrected profile passing. Keep the defective mode off by default and out of readiness results for the corrected release. Never imply the seeded defect was an externally discovered production incident.

## 12. Metrics and readiness report

| Metric | Definition |
| --- | --- |
| Required scenario coverage | Executed required scenario cells / defined required cells, with missing cells listed |
| Outcomes | Pass, product failure, infrastructure error, skipped, and not run counted separately |
| Critical invariant violations | Count and evidence for specified R01–R14 violations |
| Command acknowledgement delay | Issue-to-durable-ack interval with declared clock |
| Reconciliation time | Restoration of delivery until required backend/agent agreement |
| Cancellation convergence | Cancel intent until confirmed quiescence, not just HTTP response time |
| Telemetry freshness | Current modeled time minus latest applicable observation time |
| Duplicate side effects | Extra completion/receipt records for a logical ride |
| UI convergence | Time until browser reflects the authoritative current revision |
| Test reproducibility | Results of explicit reruns of selected scenario/config combinations |

Give denominators, sample counts, seeds, timeouts, dependency versions and hardware. Mean/p95 are useful only with enough samples; report raw counts and ranges for small sets. Do not invent improvements or equate test count with completeness.

Set requirements and deadlines before the assessed run, based on the lab's model. A proposed initial gate: every critical required scenario executed, no critical invariant violations, no unresolved infrastructure errors in critical cases, and each specified recovery deadline met. Missing/skipped critical cases produce INCOMPLETE, not PASS. A real critical failure produces BLOCKED. Use PASS only for the scoped lab criteria.

Publish an HTML or Markdown readiness report with build identity, scope, traceability matrix, outcome table, timing metrics, incidents, and limitations. Do not call it a vehicle safety certification or evidence that a real robotaxi is road-ready.

## 13. Implementation milestones

### M1 — Environment and simulator smoke test

Inspect the repository/OS first. Pin supported Python/package and SUMO versions after confirming them. Create the synthetic network and a Python TraCI adapter. Drive, stop, replace a stop, and read actual position. Confirm a serialized step owner and headless mode; add optional GUI mode.

Acceptance: one documented command produces observable vehicle motion and valid stopping. Integration failure is diagnosed before more services are added.

### M2 — Complete ride vertical slice

Implement backend models, SQLite persistence, agent command/event exchange, and the complete lifecycle. Add a minimal passenger interface. Use SUMO's routing initially. Require observed arrival and passenger readiness before boarding.

Acceptance: T01 passes across separate processes with real HTTP and SUMO. No mocked movement or timer-only completion. Store the first complete trace.

### M3 — Durable protocol and cancellation

Add request idempotency, atomic state/outbox writes, deduplication, mission versions, vehicle sequence/tombstones, acknowledgement retries, and cancellation pending/confirmed states. Add safe restart reconciliation.

Acceptance: duplicate requests, old commands, duplicate events, and actual backend/agent restart tests behave as specified. No terminal resurrection.

### M4 — Fault relay and temporal tests

Add scheduled delays/duplicates/reordering/partitions and bounded local authorization behavior. Build reusable Pytest fixtures, advance-until helpers, reset isolation, and independent assertions. Keep product and infrastructure errors distinct.

Acceptance: T05, T07, T08 and related cases reproduce reliably without arbitrary sleeps; a real process-down test also runs.

### M5 — Pickup change, operator flow, and UI validation

Add one modeled unavailable pickup and eligible alternative. Validate walking/access constraints using manually annotated fixture data. Maintain passenger readiness when location changes; don't silently teleport the passenger. Test browser state revisions and operator conflicts/audit.

Acceptance: changed pickup reaches all components; stale update rejected; Playwright checks visible cancellation/staleness/location behavior.

### M6 — Evidence, regression proof, and readiness report

Implement correlated timeline, failure bundles, traceability matrix, defect report, seeded defective profile and corrected rerun. Generate measured readiness results.

Acceptance: reviewer can reproduce a failure, follow its evidence, inspect the fix, and rerun the regression. Readiness distinguishes blocked and incomplete runs.

### M7 — CI and portfolio packaging

Run fast tests on commits and a small headless SIL suite in CI. Run browser tests in a separate job if needed. Upload failure artifacts. Provide optional nightly/manual expanded suites only if useful.

Acceptance: fresh environment follows README commands; required dependencies fail clearly if missing; process/port cleanup works; demo is reproducible.

Estimate roughly 2–3 focused working weeks for the full scoped lab. A convincing first slice may be faster. Use acceptance gates rather than promising completion by a fixed date.

## 14. Repository structure and proposed commands

- `services/ride_service/`: API, domain transitions, persistence, outbox/inbox
- `services/vehicle_agent/`: durable command handling, local state, TraCI adapter
- `services/fault_relay/`: scoped faults and delivery evidence
- `web/`: minimal passenger/operator pages
- `contracts/`: schemas and protocol documentation
- `simulation/`: network sources, routes, stops, SUMO configuration
- `scenarios/`: versioned scenarios and fault schedules
- `tests/unit/`, `tests/integration/`, `tests/sil/`, `tests/ui/`
- `validation/`: requirements, independent oracles, report generation
- `scripts/`: environment setup, run control, demo and artifact collection
- `docs/`: architecture, protocol, assumptions, defect example, results
- `.github/workflows/`: CI
- `README.md`, dependency lock/config, optional `compose.yaml`

Proposed interface to implement (not commands already verified):

```bash
python -m lab doctor
python -m lab run --scenario happy_path --gui
pytest tests/unit tests/integration
pytest tests/sil -m critical
pytest tests/ui
python -m lab run --scenario stale_assignment --profile defective
python -m lab run --scenario stale_assignment --profile corrected
python -m lab report --run-dir artifacts/<run-id>
```

The final README must provide commands actually supported and tested. A run directory is unique; use separate databases, ports, relay rules and SUMO instances per run. Start sequential execution before parallelizing. Never share a TraCI connection or active mission database between independent tests.

## 15. Reliability of the test framework

Fixtures must start processes, wait on bounded readiness checks, and always clean up through teardown/finalizers. Retain databases across deliberate restarts, but isolate/reset them between episodes. Capture logs before removing temporary directories. Detect leftover processes and occupied ports.

No unbounded retries, long blind sleeps, test-result rewriting, or blanket 'rerun until green'. A retry may diagnose flakes, but the original result remains visible. Missing SUMO produces an explicit infrastructure outcome; it cannot mark the SIL gate passed.

Distinguish simulated communication delays from host scheduling instability. Pin tested versions, seeds and simulation step size. Test synchronization must use domain milestones and logical barriers. Keep wall-clock watchdogs generous enough for CI while preserving modeled timing requirements.

## 16. Visual demonstration and deliverables

A 2–3 minute demo should show a passenger request, simulated vehicle approach, injected fault, failing assertion, correlated timeline, fix/regression result, and scoped readiness report. The recruiter sees the scenario; the technical reviewer can inspect how it was validated.

Final deliverables:

1. Runnable backend, agent, relay, web interface and SUMO scenario.
2. Requirements/test-plan matrix and scenario definitions.
3. Pytest SIL suite and selected Playwright workflows.
4. Durable protocol and partition/cancellation semantics documentation.
5. Failure artifact bundles and a correlated incident timeline.
6. One complete defect-to-fix-to-regression example.
7. Measured readiness report, with honest limitations.
8. CI configuration, setup guide, demo script and optionally a recording.

## 17. Official references and interpretation

- SUMO overview: https://eclipse.dev/sumo/
- TraCI client/server control: https://sumo.dlr.de/docs/TraCI/
- Vehicle routing/stopping APIs: https://sumo.dlr.de/docs/TraCI/Change_Vehicle_State.html
- Network creation: https://sumo.dlr.de/docs/Networks/PlainXML.html
- Pytest fixtures: https://docs.pytest.org/en/stable/how-to/fixtures.html
- Playwright/Pytest integration: https://playwright.dev/python/docs/test-runners
- FastAPI documentation: https://fastapi.tiangolo.com/

Use current official documentation for implementation, then record the tested versions. SUMO supports routing and stopping a simulated vehicle, Pytest supports test fixtures, and Playwright supports browser testing. The ride protocol, relay, requirements, holding policy, logical passenger model and readiness criteria are our project design choices.
