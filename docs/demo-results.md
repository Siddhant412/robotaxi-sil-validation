# Scoped SIL readiness

Gate: **INCOMPLETE**

Required scenario coverage: 2/24 defined cells. Missing: test_HTTP_validation_and_idempotency_scope, test_HTTP_walking_constraint, test_T02_duplicate_request, test_T03_assignment_concurrency, test_T04_cancel_approaching, test_T06_duplicate_ack_loss, test_T07_reordered_events, test_T08_partition, test_T08_partition_cancel, test_T09_backend_restart, test_T10_agent_restart_tombstone, test_T11_pickup_change, test_T12_duplicate_completion, test_T13_stale_operator, test_T14_old_lease, test_T15_cancel_after_boarding, test_T15_cancel_boarding_race, test_T16_simulator_exit, test_UI_cancel_pending_confirmed, test_UI_normal, test_UI_pickup_revision_operator, test_UI_stale.

All attempts in the selected group are counted. A subsequent pass does not erase an earlier failure. Seeded defective runs are listed separately.

| Outcome | Count |
|---|---:|
| pass | 2 |
| product_failure | 0 |
| infrastructure_error | 0 |
| skipped | 0 |
| not_run | 22 |

| Scenario / requirements | Outcome(s) | Evidence |
|---|---|---|
| test_T01_full_ride (R04, R05, R06, R14) | pass | [happy_path-corrected-29544172](/Users/siddhantraje/Documents/PersonalWork/Projects/robotaxi-sil-validation/artifacts/happy_path-corrected-29544172) |
| test_T02_duplicate_request (R01, R02) | not_run | — |
| test_T03_assignment_concurrency (R02) | not_run | — |
| test_T04_cancel_approaching (R11) | not_run | — |
| test_T05_stale_assignment (R03, R11) | pass | [stale_assignment-corrected-9ee1e107](/Users/siddhantraje/Documents/PersonalWork/Projects/robotaxi-sil-validation/artifacts/stale_assignment-corrected-9ee1e107) |
| test_T06_duplicate_ack_loss (R07) | not_run | — |
| test_T07_reordered_events (R04) | not_run | — |
| test_T08_partition (R09, R12) | not_run | — |
| test_T09_backend_restart (R08) | not_run | — |
| test_T10_agent_restart_tombstone (R03, R07) | not_run | — |
| test_T11_pickup_change (R05, R10) | not_run | — |
| test_T12_duplicate_completion (R06) | not_run | — |
| test_T13_stale_operator (R13) | not_run | — |
| test_T14_old_lease (R03, R12) | not_run | — |
| test_T15_cancel_boarding_race (R04, R05, R11) | not_run | — |
| test_T15_cancel_after_boarding (R04, R05, R11) | not_run | — |
| test_T16_simulator_exit (R14) | not_run | — |
| test_UI_normal (R04, R09) | not_run | — |
| test_UI_cancel_pending_confirmed (R11) | not_run | — |
| test_UI_stale (R09) | not_run | — |
| test_UI_pickup_revision_operator (R10, R13) | not_run | — |
| test_HTTP_validation_and_idempotency_scope (R01) | not_run | — |
| test_HTTP_walking_constraint (R10) | not_run | — |
| test_T08_partition_cancel (R09, R12) | not_run | — |

## Observed metrics

| Metric / clock | Samples | Range |
|---|---:|---|
| ack_delay_sim_seconds | 3 | 0.0000–2.0000 |
| telemetry_age_sim_seconds | 109 | 0.0000–0.0000 |
| cancel_convergence_sim_seconds | 1 | 1.0000–1.0000 |
| reconciliation_sim_seconds | 0 | not measured |
| ui_convergence_wall_seconds | 0 | not measured |
| api_wall_seconds | 384 | 0.0008–0.0646 |
| duplicate_completion_effects | 1 | 0.0000–0.0000 |
| ride_completion_sim_seconds | 1 | 106.0000–106.0000 |

Failed scenario assertions: 0. This is not an exhaustive count of all possible invariant violations.
Artifact gaps: 0.

## Build and scope

- Source SHA256: `9f2aff3da07a562ac72ea8c79e1b6e77d5e3493ada32c41f684561d600f1fe07`
- Base commit: `e566339f3f91a0747a0438fa15e5a3d020d8bebe` (working source digest above includes local implementation).
- Host: macOS-26.6.2-arm64-arm-64bit; arm64; Python 3.11.11 (main, Dec 16 2024, 14:27:05) [Clang 16.0.0 (clang-1600.0.26.4)].
- Seeds: [42].
- Dependencies and predeclared deadlines: per-run `configuration.json`.

## Seeded defect profiles

- stale_assignment-defective-29dad385: defective, product_failure; excluded from corrected release coverage.

## Limitations

One synthetic vehicle, one mission, one seed in the acceptance batch. Application-message faults, logical passengers/doors, annotated walking access, and modeled curb occupancy. No perception, controller, physical curb, cellular packet, vehicle-safety or production HA validation.
Agent restarts are tested at completed step checkpoints; SQLite and SUMO cannot commit atomically. Arbitrary mid-step crashes are outside the demonstrated recovery scope. GUI mode is optional and is not a headless acceptance result. CI configuration is supplied but remote CI was not executed locally.
UI timings measure observation-to-browser assertion wall time, not network latency alone. Raw ranges are used; no small-sample p95 claims. Selected reruns demonstrate only the selected scenario and seed.
