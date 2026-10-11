# Acceptance plan and independent evidence

`scenarios/catalog.json` is the versioned requirements-to-test matrix and defines required cells before the assessed run. Tests are isolated episodes. Seeds, deadlines and build/dependency identities are in each run configuration.

Normal arrival/completion is checked from actual SUMO observations, plus an independently specified lifecycle sequence and one receipt from public APIs. Cancellation regression checks every observation for a configured interval after revocation acknowledgement/holding confirmation. Neither an agent acknowledgement alone nor absence of a log line is treated as motion evidence.

| Cell | Stimulus / primary evidence |
|---|---|
| T01 | Full ride; stopped at A and D, valid lifecycle, observed boarding/alighting dwell, one receipt |
| T02 | Same idempotency key after discarded first result; same ride and command; changed payload conflicts |
| T03 | Concurrent real HTTP requests; one assignment, explicit 409 for the other |
| T04 | Cancel during observed motion; pending until observed H stop, negative motion interval |
| T05 | Hold old grant; deliver newer revocation; confirm cancellation; release obsolete grant; every subsequent observation remains stopped |
| T06 | Duplicate command delivery, acknowledgement suppression/retry and duplicate event delivery; no second approach or receipt |
| T07 | Late telemetry and delayed READY_FOR_BOARDING overtaken by IN_TRIP; projection reconciles legally without regression |
| T08 | Partition; freshness ages, lease fallback begins within 13 ticks of loss, reachable H within 160 ticks, restoration reconciles; additional cancellation-during-partition cell |
| T09 | Stop actual backend process during approach; connection refusal recorded, persisted intent/audit restored, ride completes once |
| T10 | Restart actual agent/SUMO process group after cancellation using retained checkpoint/database; old grant rejected |
| T11 | Modeled A occupancy, agent blocks service, operator chooses accessible B, readiness cleared, observed B stop, passenger confirmation, completion |
| T12 | Duplicate completion event identity; one transition/receipt |
| T13 | Stale operator revision conflicts; accepted/rejected actions audited |
| T14 | Relay deliberately supplies old active intent/lease after revocation; no lease revival or motion |
| T15 | Deterministic cancellation-before-boarding and boarding-before-cancellation orders; rejection after boarding |
| T16 | SUMO connection deliberately closed; explicit infrastructure error returned, ride cannot become complete |
| UI | Normal lifecycle, cancellation pending/confirmed, stale telemetry, changed pickup/readiness/operator timeline and outdated browser response |

Expected fault detection is a passing test only when its stated oracle detects that fault. An unexpected simulator error is an infrastructure outcome. The seeded defective T05 run must remain an actual product-failure result and exit nonzero; it is never an expected-failure mark that turns release coverage green.

Gate: execute every defined required cell, no failed scenario assertion, no infrastructure errors/skips/missing cells, and explicit scenario deadlines met. A failure blocks; omissions yield incomplete. Supporting oracle tests are counted separately from required scenario cells. This gate applies only to the local lab model.

Browser screenshots/traces are retained even after failed assertions. T05 takes a passenger screenshot too. SUMO FCD output may be overwritten on an agent restart, so `samples.jsonl` and `observations.jsonl` preserve the cross-restart observation interval; this artifact limitation is explicit. Process logs append across restart.
