# Robotaxi ride-service SIL validation lab

A local Python ride service and validation harness. The backend, fault relay, vehicle agent and SUMO run as separate processes. Real road motion and stop observations guard boarding and completion. A small passenger/operator browser interface is tested with Playwright. This is mission-execution SIL, with logical passengers and application-message faults.

Setup from the repository root (tested on Python 3.11.11, macOS arm64; headless SUMO/TraCI 1.28.0):

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock
python -m playwright install chromium
python -m lab doctor
python -m lab smoke
python -m lab run --scenario happy_path
```

The pip SUMO package supplies SUMO/netconvert binaries; no system SUMO install is needed. Linux CI uses `playwright install --with-deps chromium`. Missing simulator/browser dependencies fail explicitly; no mock simulator is substituted. Python 3.12 and GUI mode are allowed but were not part of the local acceptance batch.

Run checks and preserve the complete assessment:

```bash
pytest tests/unit tests/integration
pytest tests/sil -m critical
pytest tests/ui
ASSESSMENT_GROUP=my-assessment pytest tests/unit tests/integration tests/sil tests/ui --junitxml=artifacts/my-assessment.xml
python -m lab report --group my-assessment --output artifacts/my-assessment.md
```

The report uses the required scenario denominator, retains all selected attempts, and returns nonzero for BLOCKED/INCOMPLETE. A single successful scenario run produces an INCOMPLETE full-scope report, while the scenario command itself exits zero. Report production needs the run artifacts; checked-in summary documents are the portable review entry point.

Reproduce the intentional stale-assignment defect and verify the corrected default:

```bash
python -m lab run --scenario stale_assignment --profile defective
# Expected exit 1: observed cancelled vehicle resumes motion.
python -m lab run --scenario stale_assignment --profile corrected
```

Each command prints its new run directory. Existing explicit `--run-dir` destinations are rejected. Artifacts include configuration/build identities, SQLite state, product timeline, message attempts/deliveries, SUMO observations/FCD, assertions and screenshots where applicable. The defective profile is restricted by the CLI to this scenario and excluded from corrected readiness results.

The scripted local demonstration is `python scripts/demo.py`; it checks the expected failing exit without changing the underlying failed result.

Other runnable scenarios: `cancellation`, `partition`, `pickup_change`, `backend_restart`, `agent_restart`. Optional `--gui` selects SUMO GUI; it was not locally verified. `python -m lab run --help` describes supported options. Services bind loopback; lab controls are local only. The test harness starts services, waits on bounded readiness, and terminates process groups including SUMO.

Read [architecture](docs/architecture.md), [protocol/modeling decisions](docs/protocol.md), [test plan](docs/test-plan.md), [milestone record](docs/milestones.md), [seeded defect](docs/defect-stale-assignment.md), and [measured readiness](docs/readiness.md). The complete original brief is retained in `robotaxi-sil-validation-project-context.md`.

Scope limitations include one vehicle/network, one acceptance seed, logical boarding/doors, annotated walking access, modeled occupancy, and checkpoint-boundary agent restarts. General mid-step crash recovery, production HA, perception/controllers and physical robotaxi safety are outside the demonstrated gate. CI is configured locally; its remote execution is not claimed.
