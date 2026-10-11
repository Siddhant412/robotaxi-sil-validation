# Seeded defect: obsolete assignment resumes a cancelled mission

This is an intentionally injected local defect, not a discovered production incident. Severity is high within this lab model: it violates R03/R11 by resuming pickup after durable revocation and confirmed holding.

Reproduction:

```bash
python -m lab run --scenario stale_assignment --profile defective
# Nonzero exit; product_failure: R11 cancelled vehicle resumed motion.
python -m lab run --scenario stale_assignment --profile corrected
# Zero exit; old command rejected; every observation in the negative interval is stopped.
```

The relay holds assignment version 1 without letting the agent execute it. The passenger cancels, producing revocation version 2 with a higher vehicle sequence. The agent persists its tombstone, acknowledges revocation and reports observed holding at H. The relay then releases the obsolete assignment before its grant expires. This ordering isolates the revocation bug from the inability to know about undelivered cancellation during a partition.

Observed first demonstration (seed 42, one-second simulation steps):

| Simulated time | Defective profile | Corrected profile |
|---|---|---|
| 2 s | Revocation v2 durably acknowledged | Revocation v2 durably acknowledged |
| 3 s | CANCELLED, stopped at H, position 30 m | CANCELLED, stopped at H, position 30 m |
| 3 s, after relay release | ASSIGN v1 accepted; APPROACHING emitted | ASSIGN v1 rejected using its command ID, sequence and tombstone |
| 23 s, end of 20-tick interval | Position 190.526 m; speed 9.246 m/s; not stopped | Position 30 m; speed 0; stopped for all 20 ticks |

The backend remains CANCELLED even in the defective run, because it rejects obsolete-version execution events. Checking only the backend would therefore miss this bug. The independent oracle checks actual SUMO motion and agent execution throughout the observation interval. It records all twenty samples before failing, preserving the negative evidence interval.

Confirmed root cause: the explicit `defective` branch in `services/vehicle_agent/main.py` bypasses command ordering/tombstone checks for ASSIGN. It is selected only by the test profile; the CLI restricts that profile to this one scenario. Corrected behavior is the default. The corrected handler enforces persisted per-vehicle sequence, same-mission version ordering, terminal tombstones and grant expiry before touching the route. Revocations remain applicable after expiry because they reduce authority.

Verification: first defective command exited 1 with a real product-failure assertion; first corrected command exited 0. Both complete bundles are preserved below. Final release T05 and the actual agent-restart T10 exercise corrected behavior too. The isolated defective result is excluded from corrected release coverage and explicitly listed in historical reports.

Portable evidence archives contain configuration/dependency identities, databases, correlated message logs, committed backend timeline, SUMO samples, screenshot, and assertion result:

- [Defective first run](evidence/seeded-defect-v1.tar.gz)
- [Corrected first run](evidence/seeded-defect-corrected-v1.tar.gz)

Original local directories are `artifacts/seeded-defect-v1` and `artifacts/seeded-defect-corrected-v1`. Each archive is an observed run, not an exact-state replay promise. Follow the reproduction commands above to create a new isolated episode.
