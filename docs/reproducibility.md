# Selected scenario reproducibility

Explicit final-suite and CLI-demo reruns, using seed 42 and the same tested source digest. These are new episodes with different IDs/ports; exact event-identity or simulator-state replay is not claimed.

| Scenario | Profile | Seed | Outcome | Run |
|---|---|---:|---|---|
| test_T01_full_ride | corrected | 42 | pass | happy_path-corrected-29544172 |
| test_T01_full_ride | corrected | 42 | pass | test_T01_full_ride-f44d19c6 |
| test_T05_stale_assignment | corrected | 42 | pass | stale_assignment-corrected-9ee1e107 |
| test_T05_stale_assignment | corrected | 42 | pass | test_T05_stale_assignment-68fd8aaa |
| test_T05_stale_assignment | defective | 42 | product_failure | stale_assignment-defective-29dad385 |

Tested source SHA256: `9f2aff3da07a562ac72ea8c79e1b6e77d5e3493ada32c41f684561d600f1fe07`.

T01: two corrected executions passed. T05: two corrected executions passed; one isolated defective execution failed as intended. These small samples do not establish a flake rate or broad seed coverage. The original developmental failures remain in `development-history.md`. Report generation was separately checked after adding supporting-test JUnit accounting; its own digest is recorded in each generated report.
