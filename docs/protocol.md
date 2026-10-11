# Protocol v1 and modeling decisions

The brief in `robotaxi-sil-validation-project-context.md` is the scope authority. Python application code executes in three separate processes; SUMO replaces road motion. SQLite is local durable storage, not production HA evidence.

| Decision | Model and reason |
|---|---|
| Clock | One-second SUMO ticks; agent alone steps. Commands precede stepping, then observation, progress, telemetry, feedback, and checkpoint. Backend lab clock is independently observed by the harness so UI freshness still ages during a partition. Wall time is used for HTTP timeouts and watchdogs only. |
| Identity | Protocol schema 1, run/ride/mission/vehicle identities, stable command/event IDs, per-attempt relay IDs, persistent vehicle command sequence and producer sequence, diagnostic boot ID, mission version, server revision, causation ID. |
| Durability | Backend `BEGIN IMMEDIATE` commits state, assignment constraint, audit, and outbox together. Inbox IDs and event sequence watermark are transactional. Agent stores state, command IDs, tombstones, and unsent feedback before acknowledgement delivery. |
| Delivery | At least once, with idempotent command/event processing. Command IDs remain stable; relay attempt IDs are unique. Outbox polling is capped at 64 attempts per command; feedback at 256 attempts per event and 512 pending events. Exceeding an agent budget produces an explicit infrastructure error, never completion. |
| Cancellation | Before boarding, intent changes to CANCEL_REQUESTED and emits a higher-version revocation. Agent drives normally to H; CANCELLED requires observed stopped-at-H evidence. Revocations do not expire: they reduce authority. Expired grants are rejected. The backend does not infer cancellation from stale telemetry. |
| Tombstones | Persist across agent restarts. Sequence ordering is per vehicle; a cancelled/completed ride cannot be assigned again. Duplicate commands re-acknowledge without route execution. Default profile enforces this. |
| Lease | Each successful command poll carries current intent and a simulated expiry 12 seconds ahead. Renewal requires matching mission identity/version and active backend intent. Expiry initiates a reachable H holding route; motion remains governed by SUMO. Holding reach deadline is 160 steps. This is a simplified holding procedure, not a certified minimal-risk maneuver. |
| Partition | Relay returns HTTP 503 at the application boundary; the control channel is unaffected. No instant knowledge of unreceived cancellation is claimed. Restoration reconciles current intent. A separate test stops the backend process and observes real connection refusal. No TCP blackhole/timeout experiment is claimed. |
| Arrival | Service requires matching road edge/position within 1 m, SUMO stopped flag, and speed below 0.01 m/s. Boarding additionally requires passenger readiness and two simulated seconds of observed dwell. Drop-off/alighting uses the same observation guard and dwell. Doors/passengers are logical abstractions. |
| Late events | Durable identity deduplication first. Late telemetry cannot overwrite a newer projection. Useful late progress is retained in the inbox and reconciled only through legal next transitions, using its observation evidence. Old mission versions remain historical only. |
| Pickup | A→B walking distance is manually annotated as 120 m with accessible access. Walking limits are checked. Changing pickup clears readiness: the passenger explicitly confirms presence at B. Occupancy is an agent application constraint, not a lane obstruction. Agent refuses boarding at an occupied modeled point and raises an incident. |
| Operator | Local demo identity and reason, expected server revision, pickup action result and timeline. Rejections are separately audited after transaction rollback. No public authorization/security claim. |
| UI | Plain HTML and polling; lower server revisions are ignored. Same revision may render freshness updates because freshness is a clock-derived value. UI refreshes current revision before a user mutation; backend still rejects stale explicit requests. No map displays a last position as live. |

## Restart boundary and deviations

The tested backend restart terminates/relaunches the real process with SQLite retained while the agent/SUMO continue. The agent restart terminates its process group (including SUMO), then restores its SQLite and a TraCI saveState checkpoint from a completed step. Its lease is invalidated until reconciliation. RNG state is saved, but this is not a promise of exact state replay.

SQLite and SUMO cannot commit atomically. Mid-step process failure between a route action, a database commit, and a checkpoint is **not** covered by the checkpoint restart test; general crash-consistent agent recovery remains future work. The brief's actual agent restart requirement is demonstrated at the documented checkpoint boundary.

The initial transaction assigns immediately; REQUESTED is a durable audit event, while the UI displays request pending during HTTP creation. There is no queue for a second passenger: a competing request receives explicit 409. Health/readiness verify the running component and its local dependencies, not complete distributed readiness.

Services use one local process each and bind loopback. Backend handlers serialize SQLite access on the event loop; the agent uses a single-threaded HTTPServer. Blocking HTTP operations are bounded at 0.5 seconds per attempt. No containers, dashboards, distributed queues, or branding were added.

The synthetic loop can always reach H under this fixture. General networks with inaccessible holding locations and occupied B are outside the assessed scenario cells. Feedback queues are bounded; prolonged partitions beyond the configured episode bounds can exhaust their budget and must fail explicitly. Timeline JSON from SQLite is authoritative for committed domain events; JSONL may also contain attempted actions from a rolled-back transaction.

## Confirmed SUMO APIs

Installed SUMO/TraCI 1.28.0 signatures are printed by `python -m lab doctor`. Official references consulted:

- [Python TraCI interface](https://sumo.dlr.de/docs/TraCI/Interfacing_TraCI_from_Python.html)
- [Vehicle state changes](https://sumo.dlr.de/docs/TraCI/Change_Vehicle_State.html): replaceStop, resume, changeTarget, setStop; reached stops must be resumed rather than replaced.
- [Save and load state](https://sumo.dlr.de/docs/Simulation/SaveAndLoad.html): simulation.saveState/loadState and RNG limitations.
- [Simulation retrieval](https://sumo.dlr.de/docs/TraCI/Simulation_Value_Retrieval.html): time and teleport detection.
- [PlainXML network sources](https://sumo.dlr.de/docs/Networks/PlainXML.html).
