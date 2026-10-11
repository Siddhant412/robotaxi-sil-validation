"""Measured reports retain failure/infrastructure/skipped/not-run denominators."""

import json
from collections import Counter
from pathlib import Path
from lab.simulator import ROOT


def read(path, default):
    return json.loads(path.read_text()) if path.exists() else default


def jsonl(path):
    return (
        [json.loads(x) for x in path.read_text().splitlines()] if path.exists() else []
    )


def generate(directory=None, group=None, output=None):
    catalog = read(ROOT / "scenarios/catalog.json", {})["required"]
    directories = (
        [Path(directory)] if directory else sorted((ROOT / "artifacts").iterdir())
    )
    runs = []
    for d in directories:
        if not d.is_dir():
            continue
        config = read(d / "configuration.json", {})
        if not config:
            continue
        if group and config.get("group", "development") != group:
            continue
        result = read(
            d / "result.json",
            {"test": config.get("scenario", "unknown"), "outcome": "not_run"},
        )
        runs.append((d, config, result))
    corrected = [r for r in runs if r[1].get("profile") == "corrected"]
    excluded = [r for r in runs if r[1].get("profile") != "corrected"]
    by_test = {}
    for d, c, r in corrected:
        by_test.setdefault(r["test"], []).append((d, c, r))
    defined = {x["id"] for x in catalog}
    executed = defined & {
        name
        for name, matches in by_test.items()
        if any(
            r.get("scenario_executed", r["outcome"] in {"pass", "product_failure"})
            for _, _, r in matches
        )
    }
    counts = Counter(r["outcome"] for _, _, r in corrected)
    supporting = []
    junit = ROOT / "artifacts" / f"{group}.xml" if group else None
    if junit and junit.exists():
        import xml.etree.ElementTree as ET

        for cell in ET.parse(junit).getroot().iter("testcase"):
            name = cell.attrib["name"]
            if name not in by_test:
                result = (
                    "infrastructure_error"
                    if cell.find("error") is not None
                    else "product_failure"
                    if cell.find("failure") is not None
                    else "skipped"
                    if cell.find("skipped") is not None
                    else "pass"
                )
                counts[result] += 1
                supporting.append(
                    {"test": name, "outcome": result, "evidence": str(junit)}
                )
    missing = sorted(defined - executed)
    counts["not_run"] += sum(name not in by_test for name in missing)
    blocked = any(r["outcome"] == "product_failure" for _, _, r in corrected)
    incomplete = bool(missing) or any(
        r["outcome"] in {"infrastructure_error", "skipped", "not_run"}
        for _, _, r in corrected
    )
    blocked = blocked or any(x["outcome"] == "product_failure" for x in supporting)
    incomplete = incomplete or any(
        x["outcome"] in {"infrastructure_error", "skipped"} for x in supporting
    )
    gate = "BLOCKED" if blocked else ("INCOMPLETE" if incomplete else "PASS")
    lines = [
        "# Scoped SIL readiness",
        "",
        f"Gate: **{gate}**",
        "",
        f"Required scenario coverage: {len(executed)}/{len(defined)} defined cells. Missing: {', '.join(missing) or 'none'}.",
        "",
        "All attempts in the selected group are counted. A subsequent pass does not erase an earlier failure. Seeded defective runs are listed separately.",
        "",
        "| Outcome | Count |",
        "|---|---:|",
    ]
    for key in [
        "pass",
        "product_failure",
        "infrastructure_error",
        "skipped",
        "not_run",
    ]:
        lines.append(f"| {key} | {counts[key]} |")
    lines += [
        "",
        "| Scenario / requirements | Outcome(s) | Evidence |",
        "|---|---|---|",
    ]
    for x in catalog:
        matches = by_test.get(x["id"], [])
        outcomes = ", ".join(r["outcome"] for _, _, r in matches) or "not_run"
        evidence = ", ".join(f"[{d.name}]({d.resolve()})" for d, _, _ in matches) or "—"
        lines.append(
            f"| {x['id']} ({', '.join(x['requirements'])}) | {outcomes} | {evidence} |"
        )
    for test, matches in by_test.items():
        if test not in defined:
            lines.append(
                f"| {test} (supporting) | {', '.join(r['outcome'] for _, _, r in matches)} | {', '.join(d.name for d, _, _ in matches)} |"
            )
    for item in supporting:
        lines.append(
            f"| {item['test']} (supporting) | {item['outcome']} | {item['evidence']} |"
        )
    metrics = {
        "ack_delay_sim_seconds": [],
        "telemetry_age_sim_seconds": [],
        "cancel_convergence_sim_seconds": [],
        "reconciliation_sim_seconds": [],
        "ui_convergence_wall_seconds": [],
        "api_wall_seconds": [],
        "duplicate_completion_effects": [],
        "ride_completion_sim_seconds": [],
    }
    artifact_gaps = []
    violations = []
    for d, c, result in corrected:
        timeline = read(d / "timeline.json", [])
        commands = {
            x["command"]["command_id"]: x["command"]
            for x in timeline
            if x["kind"] == "COMMAND_ISSUED"
        }
        acked = set()
        for x in timeline:
            if x["kind"] == "EVENT_RECEIVED" and x["event"]["kind"] == "ACK":
                e = x["event"]
                cid = e.get("command_id")
                if cid in commands and cid not in acked:
                    metrics["ack_delay_sim_seconds"].append(
                        e["time"] - commands[cid]["issued_at"]
                    )
                    acked.add(cid)
        cancel = next(
            (x["time"] for x in timeline if x["kind"] == "CANCEL_REQUESTED"), None
        )
        confirm = next((x["time"] for x in timeline if x["kind"] == "CANCELLED"), None)
        if cancel is not None and confirm is not None:
            metrics["cancel_convergence_sim_seconds"].append(confirm - cancel)
        completion = next(
            (x["time"] for x in timeline if x["kind"] == "COMPLETED"), None
        )
        start = next((x["time"] for x in timeline if x["kind"] == "REQUESTED"), None)
        if completion is not None and start is not None:
            metrics["ride_completion_sim_seconds"].append(completion - start)
        ride = read(d / "ride.json", {})
        if ride.get("state") == "COMPLETED":
            metrics["duplicate_completion_effects"].append(
                max(0, ride.get("completion_effects", 0) - 1)
            )
        for h in jsonl(d / "harness.jsonl"):
            if h["kind"] == "TELEMETRY_FRESHNESS" and h["age"] is not None:
                metrics["telemetry_age_sim_seconds"].append(h["age"])
            if h["kind"] == "PARTITION_METRIC":
                metrics["reconciliation_sim_seconds"].append(
                    h["reconciled"] - h["restored"]
                )
            if h["kind"] == "UI_CONVERGENCE":
                metrics["ui_convergence_wall_seconds"].append(h["wall_seconds"])
            if h["kind"] == "HTTP":
                metrics["api_wall_seconds"].append(h["wall_latency"])
            if h["kind"] == "ARTIFACT_GAP":
                artifact_gaps.append({"run": d.name, **h})
        if result["outcome"] == "product_failure":
            violations.append(
                {
                    "run": d.name,
                    "test": result["test"],
                    "assertion": result.get("details"),
                }
            )
    lines += [
        "",
        "## Observed metrics",
        "",
        "| Metric / clock | Samples | Range |",
        "|---|---:|---|",
    ]
    for name, values in metrics.items():
        lines.append(
            f"| {name} | {len(values)} | {min(values):.4f}–{max(values):.4f} |"
            if values
            else f"| {name} | 0 | not measured |"
        )
    lines += [
        "",
        f"Failed scenario assertions: {len(violations)}. This is not an exhaustive count of all possible invariant violations.",
        f"Artifact gaps: {len(artifact_gaps)}.",
        "",
        "## Build and scope",
        "",
    ]
    for digest in sorted({c.get("source_digest", "unknown") for _, c, _ in corrected}):
        lines.append(f"- Source SHA256: `{digest}`")
    if corrected:
        c = corrected[0][1]
        lines.extend(
            [
                f"- Base commit: `{c.get('commit')}` (working source digest above includes local implementation).",
                f"- Host: {c.get('platform')}; {c.get('hardware')}; Python {c.get('python', '').splitlines()[0]}.",
                f"- Seeds: {sorted({c.get('seed') for _, c, _ in corrected})}.",
                "- Dependencies and predeclared deadlines: per-run `configuration.json`.",
            ]
        )
    lines += ["", "## Seeded defect profiles", ""]
    for d, c, r in excluded:
        lines.append(
            f"- {d.name}: {c.get('profile')}, {r['outcome']}; excluded from corrected release coverage."
        )
    if not excluded:
        lines.append(
            "None in this selected group; see separate defect demonstration artifacts."
        )
    lines += [
        "",
        "## Limitations",
        "",
        "One synthetic vehicle, one mission, one seed in the acceptance batch. Application-message faults, logical passengers/doors, annotated walking access, and modeled curb occupancy. No perception, controller, physical curb, cellular packet, vehicle-safety or production HA validation.",
        "Agent restarts are tested at completed step checkpoints; SQLite and SUMO cannot commit atomically. Arbitrary mid-step crashes are outside the demonstrated recovery scope. GUI mode is optional and is not a headless acceptance result. CI configuration is supplied but remote CI was not executed locally.",
        "UI timings measure observation-to-browser assertion wall time, not network latency alone. Raw ranges are used; no small-sample p95 claims. Selected reruns demonstrate only the selected scenario and seed.",
    ]
    if artifact_gaps and gate == "PASS":
        gate = "INCOMPLETE"
        lines[2] = f"Gate: **{gate}**"
    import hashlib

    report_digest = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    lines.extend(
        [
            "",
            f"Report generator SHA256: `{report_digest}`. Supporting tests without episode directories are counted from the selected group JUnit file when available.",
        ]
    )
    summary = {
        "report_generator_sha256": report_digest,
        "supporting_tests": supporting,
        "gate": gate,
        "coverage": {
            "executed": len(executed),
            "defined": len(defined),
            "missing": missing,
        },
        "outcomes": dict(counts),
        "metrics": metrics,
        "failures": violations,
        "artifact_gaps": artifact_gaps,
        "runs": [{"directory": str(d), "config": c, "result": r} for d, c, r in runs],
    }
    out = (
        Path(output)
        if output
        else (
            Path(directory) / "readiness.md"
            if directory
            else ROOT / "docs/readiness.md"
        )
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n")
    out.with_suffix(".json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary, out
