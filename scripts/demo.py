"""Local portfolio demo; all results remain real outcomes and artifacts."""

import subprocess
import sys

commands = [
    (["doctor"], 0),
    (["run", "--scenario", "happy_path"], 0),
    (["run", "--scenario", "stale_assignment", "--profile", "defective"], 1),
    (["run", "--scenario", "stale_assignment", "--profile", "corrected"], 0),
]
for args, expected in commands:
    print("\nExecuting:", "python -m lab", *args, flush=True)
    result = subprocess.run([sys.executable, "-m", "lab", *args], check=False)
    if result.returncode != expected:
        raise SystemExit(
            f"Unexpected exit {result.returncode}; expected {expected}. Evidence remains in artifacts."
        )
print(
    "Demo verified: complete ride, actual seeded failure, corrected regression. Inspect the printed evidence directories."
)
