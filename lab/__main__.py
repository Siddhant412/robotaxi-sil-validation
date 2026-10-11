import argparse
import importlib.metadata
import json
import platform
import sys
import uuid
from pathlib import Path
from lab.simulator import ROOT, build_network, smoke


def main():
    parser = argparse.ArgumentParser(description="Local real-SUMO ride validation lab")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor")
    sm = sub.add_parser("smoke")
    sm.add_argument("--run-dir", default="artifacts/smoke-" + uuid.uuid4().hex[:8])
    run = sub.add_parser("run")
    run.add_argument(
        "--scenario",
        choices=json.loads((ROOT / "scenarios/runs.json").read_text()),
        default="happy_path",
    )
    run.add_argument(
        "--profile", choices=["corrected", "defective"], default="corrected"
    )
    run.add_argument("--gui", action="store_true")
    run.add_argument("--seed", type=int, default=42)
    run.add_argument("--run-dir")
    report = sub.add_parser("report")
    report.add_argument("--run-dir")
    report.add_argument("--group")
    report.add_argument("--output")
    args = parser.parse_args()
    if args.command == "doctor":
        import inspect, traci, sumo, subprocess

        print(platform.platform(), sys.version)
        for p in [
            "eclipse-sumo",
            "traci",
            "fastapi",
            "uvicorn",
            "httpx",
            "pytest",
            "playwright",
        ]:
            print(p, importlib.metadata.version(p))
        binary = Path(sumo.__file__).parent / "bin/sumo"
        subprocess.run([str(binary), "--version"], check=True)
        for method in [
            "replaceStop",
            "setStop",
            "resume",
            "changeTarget",
            "isStopped",
            "getPosition",
        ]:
            print(
                "vehicle." + method, inspect.signature(getattr(traci.vehicle, method))
            )
        for method in ["saveState", "loadState"]:
            print(
                "simulation." + method,
                inspect.signature(getattr(traci.simulation, method)),
            )
        build_network()
        print("Network build PASS; doctor is not a SIL run")
        return 0
    if args.command == "smoke":
        smoke(args.run_dir)
        return 0
    if args.command == "report":
        from lab.report import generate

        summary, path = generate(args.run_dir, args.group, args.output)
        print(summary["gate"], path)
        return 0 if summary["gate"] == "PASS" else 1
    if args.profile == "defective" and args.scenario != "stale_assignment":
        parser.error("defective profile is isolated to stale_assignment")
    from lab.harness import Episode, InfrastructureError
    from validation import scenarios
    from lab.report import generate

    name = json.loads((ROOT / "scenarios/runs.json").read_text())[args.scenario]
    directory = Path(
        args.run_dir
        or (
            "artifacts/"
            + args.scenario
            + "-"
            + args.profile
            + "-"
            + uuid.uuid4().hex[:8]
        )
    )
    if directory.exists():
        parser.error(
            "run directory must be new; previous evidence is never overwritten"
        )
    e = Episode(directory, args.profile, args.seed, args.gui, case=name)
    result = {"test": name, "outcome": "not_run", "details": None}
    build_network()
    try:
        e.start()
        getattr(scenarios, name)(e)
        result["outcome"] = "pass"
    except InfrastructureError as exc:
        result.update(outcome="infrastructure_error", details=repr(exc))
    except AssertionError as exc:
        result.update(outcome="product_failure", details=repr(exc))
    except Exception as exc:
        result.update(outcome="infrastructure_error", details=repr(exc))
    finally:
        try:
            e.close()
        except Exception as exc:
            result.update(
                outcome="infrastructure_error", details="teardown: " + repr(exc)
            )
        (e.directory / "result.json").write_text(json.dumps(result, indent=2))
    summary, path = generate(e.directory)
    print(json.dumps(result))
    print("Evidence:", e.directory, "; report:", path)
    return 0 if result["outcome"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
