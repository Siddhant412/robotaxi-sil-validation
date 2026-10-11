# Scoped SIL readiness

Gate: **BLOCKED**

Required scenario coverage: 23/24 defined cells. Missing: test_T08_partition_cancel.

All attempts in the selected group are counted. A subsequent pass does not erase an earlier failure. Seeded defective runs are listed separately.

| Outcome | Count |
|---|---:|
| pass | 27 |
| product_failure | 1 |
| infrastructure_error | 2 |
| skipped | 0 |
| not_run | 1 |

| Scenario / requirements | Outcome(s) | Evidence |
|---|---|---|
| test_T01_full_ride (R04, R05, R06, R14) | infrastructure_error, infrastructure_error, pass, pass | [test_T01_full_ride-11f2e594](/Users/siddhantraje/Documents/PersonalWork/Projects/robotaxi-sil-validation/artifacts/test_T01_full_ride-11f2e594), [test_T01_full_ride-7bbedca7](/Users/siddhantraje/Documents/PersonalWork/Projects/robotaxi-sil-validation/artifacts/test_T01_full_ride-7bbedca7), [test_T01_full_ride-dda77762](/Users/siddhantraje/Documents/PersonalWork/Projects/robotaxi-sil-validation/artifacts/test_T01_full_ride-dda77762), [test_T01_full_ride-e82e7572](/Users/siddhantraje/Documents/PersonalWork/Projects/robotaxi-sil-validation/artifacts/test_T01_full_ride-e82e7572) |
| test_T02_duplicate_request (R01, R02) | pass | [test_T02_duplicate_request-8703fe3c](/Users/siddhantraje/Documents/PersonalWork/Projects/robotaxi-sil-validation/artifacts/test_T02_duplicate_request-8703fe3c) |
| test_T03_assignment_concurrency (R02) | pass | [test_T03_assignment_concurrency-12992c35](/Users/siddhantraje/Documents/PersonalWork/Projects/robotaxi-sil-validation/artifacts/test_T03_assignment_concurrency-12992c35) |
| test_T04_cancel_approaching (R11) | pass | [test_T04_cancel_approaching-eedf7d0c](/Users/siddhantraje/Documents/PersonalWork/Projects/robotaxi-sil-validation/artifacts/test_T04_cancel_approaching-eedf7d0c) |
| test_T05_stale_assignment (R03, R11) | pass, pass | [seeded-defect-corrected-v1](/Users/siddhantraje/Documents/PersonalWork/Projects/robotaxi-sil-validation/artifacts/seeded-defect-corrected-v1), [test_T05_stale_assignment-bd945797](/Users/siddhantraje/Documents/PersonalWork/Projects/robotaxi-sil-validation/artifacts/test_T05_stale_assignment-bd945797) |
| test_T06_duplicate_ack_loss (R07) | pass | [test_T06_duplicate_ack_loss-17840e58](/Users/siddhantraje/Documents/PersonalWork/Projects/robotaxi-sil-validation/artifacts/test_T06_duplicate_ack_loss-17840e58) |
| test_T07_reordered_events (R04) | pass, pass | [test_T07_reordered_events-1c3bab3b](/Users/siddhantraje/Documents/PersonalWork/Projects/robotaxi-sil-validation/artifacts/test_T07_reordered_events-1c3bab3b), [test_T07_reordered_events-74db5439](/Users/siddhantraje/Documents/PersonalWork/Projects/robotaxi-sil-validation/artifacts/test_T07_reordered_events-74db5439) |
| test_T08_partition (R09, R12) | pass | [test_T08_partition-729c65e4](/Users/siddhantraje/Documents/PersonalWork/Projects/robotaxi-sil-validation/artifacts/test_T08_partition-729c65e4) |
| test_T09_backend_restart (R08) | pass | [test_T09_backend_restart-ba085b10](/Users/siddhantraje/Documents/PersonalWork/Projects/robotaxi-sil-validation/artifacts/test_T09_backend_restart-ba085b10) |
| test_T10_agent_restart_tombstone (R03, R07) | pass | [test_T10_agent_restart_tombstone-76f50f9c](/Users/siddhantraje/Documents/PersonalWork/Projects/robotaxi-sil-validation/artifacts/test_T10_agent_restart_tombstone-76f50f9c) |
| test_T11_pickup_change (R05, R10) | pass | [test_T11_pickup_change-73c54dd6](/Users/siddhantraje/Documents/PersonalWork/Projects/robotaxi-sil-validation/artifacts/test_T11_pickup_change-73c54dd6) |
| test_T12_duplicate_completion (R06) | pass | [test_T12_duplicate_completion-3a366feb](/Users/siddhantraje/Documents/PersonalWork/Projects/robotaxi-sil-validation/artifacts/test_T12_duplicate_completion-3a366feb) |
| test_T13_stale_operator (R13) | pass | [test_T13_stale_operator-7f4f19d1](/Users/siddhantraje/Documents/PersonalWork/Projects/robotaxi-sil-validation/artifacts/test_T13_stale_operator-7f4f19d1) |
| test_T14_old_lease (R03, R12) | pass, pass | [test_T14_old_lease-07e55482](/Users/siddhantraje/Documents/PersonalWork/Projects/robotaxi-sil-validation/artifacts/test_T14_old_lease-07e55482), [test_T14_old_lease-3896d0eb](/Users/siddhantraje/Documents/PersonalWork/Projects/robotaxi-sil-validation/artifacts/test_T14_old_lease-3896d0eb) |
| test_T15_cancel_boarding_race (R04, R05, R11) | pass | [test_T15_cancel_boarding_race-01d21c1e](/Users/siddhantraje/Documents/PersonalWork/Projects/robotaxi-sil-validation/artifacts/test_T15_cancel_boarding_race-01d21c1e) |
| test_T15_cancel_after_boarding (R04, R05, R11) | pass | [test_T15_cancel_after_boarding-a673aab5](/Users/siddhantraje/Documents/PersonalWork/Projects/robotaxi-sil-validation/artifacts/test_T15_cancel_after_boarding-a673aab5) |
| test_T16_simulator_exit (R14) | pass | [test_T16_simulator_exit-bed7c6c1](/Users/siddhantraje/Documents/PersonalWork/Projects/robotaxi-sil-validation/artifacts/test_T16_simulator_exit-bed7c6c1) |
| test_UI_normal (R04, R09) | pass | [test_UI_normal-9873a62d](/Users/siddhantraje/Documents/PersonalWork/Projects/robotaxi-sil-validation/artifacts/test_UI_normal-9873a62d) |
| test_UI_cancel_pending_confirmed (R11) | pass | [test_UI_cancel_pending_confirmed-e0840ba1](/Users/siddhantraje/Documents/PersonalWork/Projects/robotaxi-sil-validation/artifacts/test_UI_cancel_pending_confirmed-e0840ba1) |
| test_UI_stale (R09) | pass | [test_UI_stale-f602f450](/Users/siddhantraje/Documents/PersonalWork/Projects/robotaxi-sil-validation/artifacts/test_UI_stale-f602f450) |
| test_UI_pickup_revision_operator (R10, R13) | pass, product_failure | [test_UI_pickup_revision_operator-a954ac3c](/Users/siddhantraje/Documents/PersonalWork/Projects/robotaxi-sil-validation/artifacts/test_UI_pickup_revision_operator-a954ac3c), [test_UI_pickup_revision_operator-f5d9aa85](/Users/siddhantraje/Documents/PersonalWork/Projects/robotaxi-sil-validation/artifacts/test_UI_pickup_revision_operator-f5d9aa85) |
| test_HTTP_validation_and_idempotency_scope (R01) | pass | [test_HTTP_validation_and_idempotency_scope-0029c41a](/Users/siddhantraje/Documents/PersonalWork/Projects/robotaxi-sil-validation/artifacts/test_HTTP_validation_and_idempotency_scope-0029c41a) |
| test_HTTP_walking_constraint (R10) | pass | [test_HTTP_walking_constraint-c34b01d7](/Users/siddhantraje/Documents/PersonalWork/Projects/robotaxi-sil-validation/artifacts/test_HTTP_walking_constraint-c34b01d7) |
| test_T08_partition_cancel (R09, R12) | not_run | — |

## Observed metrics

| Metric / clock | Samples | Range |
|---|---:|---|
| ack_delay_sim_seconds | 38 | 0.0000–2.0000 |
| telemetry_age_sim_seconds | 0 | not measured |
| cancel_convergence_sim_seconds | 8 | 1.0000–150.0000 |
| reconciliation_sim_seconds | 1 | 1.0000–1.0000 |
| ui_convergence_wall_seconds | 1 | 0.1788–0.1788 |
| api_wall_seconds | 7210 | 0.0007–0.3163 |
| duplicate_completion_effects | 13 | 0.0000–0.0000 |
| ride_completion_sim_seconds | 13 | 105.0000–258.0000 |

Failed scenario assertions: 1. This is not an exhaustive count of all possible invariant violations.
Artifact gaps: 2.

## Build and scope

- Source SHA256: `81384be3b894fa0d8dbd7647804a8a0c370d68696f064d43eb1d0992b72e1b46`
- Source SHA256: `unknown`
- Base commit: `e566339f3f91a0747a0438fa15e5a3d020d8bebe` (working source digest above includes local implementation).
- Host: macOS-26.6.2-arm64-arm-64bit; arm64; Python 3.11.11 (main, Dec 16 2024, 14:27:05) [Clang 16.0.0 (clang-1600.0.26.4)].
- Seeds: [42].
- Dependencies and predeclared deadlines: per-run `configuration.json`.

## Seeded defect profiles

- seeded-defect-v1: defective, product_failure; excluded from corrected release coverage.

## Limitations

One synthetic vehicle, one mission, one seed in the acceptance batch. Application-message faults, logical passengers/doors, annotated walking access, and modeled curb occupancy. No perception, controller, physical curb, cellular packet, vehicle-safety or production HA validation.
Agent restarts are tested at completed step checkpoints; SQLite and SUMO cannot commit atomically. Arbitrary mid-step crashes are outside the demonstrated recovery scope. GUI mode is optional and is not a headless acceptance result. CI configuration is supplied but remote CI was not executed locally.
UI timings measure observation-to-browser assertion wall time, not network latency alone. Raw ranges are used; no small-sample p95 claims. Selected reruns demonstrate only the selected scenario and seed.

Report generator SHA256: `456898c32c8c38018eab62df56dcdf765b51c6f854c15988bba4b273ec42eaae`. Supporting tests without episode directories are counted from the selected group JUnit file when available.
