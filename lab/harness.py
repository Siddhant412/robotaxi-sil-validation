"""Reusable isolated process fixture. Observations are collected through agent lab HTTP."""

import json
import os
import platform
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
import httpx
from lab.simulator import ROOT


def source_digest():
    import hashlib

    h = hashlib.sha256()
    for folder in (
        "lab",
        "services",
        "web",
        "validation",
        "tests",
        "scenarios",
        "simulation",
    ):
        for p in sorted((ROOT / folder).rglob("*")):
            if (
                p.is_file()
                and "__pycache__" not in str(p)
                and not p.name.endswith(".net.xml")
            ):
                h.update(str(p.relative_to(ROOT)).encode())
                h.update(p.read_bytes())
    return h.hexdigest()


def port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class InfrastructureError(RuntimeError):
    pass


class Episode:
    def __init__(self, directory, profile="corrected", seed=42, gui=False, case=None):
        if profile not in {"corrected", "defective"}:
            raise ValueError("unknown agent profile")
        self.group = os.environ.get("ASSESSMENT_GROUP", "development")
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.config = json.loads((ROOT / "scenarios/catalog.json").read_text())
        self.ports = {k: port() for k in ("backend", "relay", "agent", "traci")}
        self.urls = {k: f"http://127.0.0.1:{v}" for k, v in self.ports.items()}
        self.processes = {}
        self.files = []
        self.samples = []
        self.ride_id = None
        self.client = httpx.Client(timeout=30)
        self.env = {
            **os.environ,
            "RUN_ID": self.directory.name,
            "RUN_DIR": str(self.directory),
            "LAB_MODE": "1",
            "BACKEND_URL": self.urls["backend"],
            "RELAY_URL": self.urls["relay"],
            "AGENT_PORT": str(self.ports["agent"]),
            "TRACI_PORT": str(self.ports["traci"]),
            "PROFILE": profile,
            "SUMO_GUI": "1" if gui else "0",
            "PYTHONUNBUFFERED": "1",
            "SUMO_SEED": str(seed),
        }
        metadata = {
            "group": self.group,
            "run_id": self.directory.name,
            "seed": seed,
            "profile": profile,
            "ports": self.ports,
            "python": sys.version,
            "platform": platform.platform(),
            "hardware": platform.machine(),
            "source_digest": source_digest(),
            "commit": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip(),
            "scenario": case,
            "scenario_definition": next(
                (x for x in self.config["required"] if x["id"] == case), None
            ),
            "clock": "simulation seconds, 1 second step; wall watchdog separately",
            "deadlines": {
                "lease": 12,
                "stale": 4,
                "holding": 160,
                "advance_until_steps": 220,
                "cancel": 160,
            },
            "dependencies": subprocess.check_output(
                [sys.executable, "-m", "pip", "freeze"], text=True
            ).splitlines(),
        }
        names = json.loads((ROOT / "scenarios/runs.json").read_text())
        alias = next((k for k, v in names.items() if v == case), None)
        command = (
            f"python -m lab run --scenario {alias} --profile {profile} --seed {seed}"
            if alias
            else f"pytest -k {case}"
        )
        (self.directory / "rerun.txt").write_text(
            command
            + "\nNew episode; original source digest and versions are in configuration.json.\n"
        )
        (self.directory / "configuration.json").write_text(
            json.dumps(metadata, indent=2)
        )

    def start(self):
        for name in ("backend", "relay", "agent"):
            self.launch(name)
        return self

    def launch(self, name):
        f = (self.directory / f"{name}.process.log").open("a")
        self.files.append(f)
        cmd = (
            [sys.executable, "-m", "services.vehicle_agent.main"]
            if name == "agent"
            else [
                sys.executable,
                "-m",
                "uvicorn",
                {
                    "backend": "services.ride_service.app:app",
                    "relay": "services.fault_relay.app:app",
                }[name],
                "--host",
                "127.0.0.1",
                "--port",
                str(self.ports[name]),
                "--log-level",
                "warning",
            ]
        )
        p = subprocess.Popen(
            cmd,
            cwd=ROOT,
            env=self.env,
            stdout=f,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        self.processes[name] = p
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            if p.poll() is not None:
                raise InfrastructureError(
                    f"{name} exited {p.returncode}; inspect {f.name}"
                )
            try:
                r = self.client.get(self.urls[name] + "/ready", timeout=0.3)
                if r.status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            time.sleep(
                0.05
            )  # bounded process readiness, never a simulation synchronization sleep
        raise InfrastructureError(f"{name} readiness timed out")

    def stop(self, name):
        p = self.processes.get(name)
        if not p:
            return
        try:
            os.killpg(p.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGKILL)
            p.wait(timeout=5)
        # SUMO is in the same process group, including on a deliberate agent restart.
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    def restart(self, name):
        before = self.processes[name].pid
        self.stop(name)
        self.launch(name)
        assert self.processes[name].pid != before
        self.record(
            "PROCESS_RESTART",
            component=name,
            before=before,
            after=self.processes[name].pid,
        )

    def record(self, kind, **data):
        with (self.directory / "harness.jsonl").open("a") as f:
            f.write(json.dumps({"kind": kind, "wall_time": time.time(), **data}) + "\n")

    def request(
        self, method, path, data=None, service="backend", expected=200, headers=None
    ):
        started = time.monotonic()
        try:
            r = self.client.request(
                method, self.urls[service] + path, json=data, headers=headers
            )
        except httpx.HTTPError as exc:
            raise InfrastructureError(str(exc)) from exc
        self.record(
            "HTTP",
            method=method,
            path=path,
            status=r.status_code,
            wall_latency=time.monotonic() - started,
        )
        if r.status_code >= 500 and expected < 500:
            raise InfrastructureError(f"{path}: {r.status_code} {r.text}")
        assert r.status_code == expected, (path, r.status_code, r.text)
        return r.json()

    def create(self, **data):
        r = self.request(
            "POST", "/rides", data, headers={"Idempotency-Key": "request-1"}
        )
        self.ride_id = r["ride_id"]
        return r

    def ride(self):
        r = self.request("GET", f"/rides/{self.ride_id}")
        self.record(
            "TELEMETRY_FRESHNESS",
            age=r["telemetry_age"],
            time=r["clock"],
            clock="simulation",
        )
        return r

    def action(self, kind, **extra):
        r = self.ride()
        return self.request(
            "POST",
            f"/rides/{self.ride_id}/{kind}",
            {"expected_revision": r["server_revision"], **extra},
        )

    def faults(self, **rules):
        return self.request("POST", "/lab/faults", rules, service="relay")

    def agent(self):
        return self.request("GET", "/lab/state", service="agent")

    def step(self, n=1):
        r = self.request("POST", "/lab/step", {"steps": n}, service="agent")
        samples = r["samples"]
        self.samples.extend(samples)
        # Independent observer clock reaches the UI even when vehicle channel is partitioned.
        try:
            self.request(
                "POST", "/lab/clock", {"time": samples[-1]["observation"]["time"]}
            )
        except InfrastructureError:
            pass
        with (self.directory / "samples.jsonl").open("a") as f:
            for sample in samples:
                f.write(json.dumps(sample) + "\n")
        return samples[-1]

    def until(self, predicate, bound=None):
        bound = bound or self.config["required"][0]["bounds"]["ride_steps"]
        for _ in range(bound):
            if predicate():
                return
            self.step()
        raise AssertionError(f"condition not reached within {bound} simulation steps")

    def screenshot(self):
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page()
                page.goto(self.urls["backend"])
                page.evaluate("(id)=>{rideId=id;return poll()}", self.ride_id)
                page.screenshot(path=str(self.directory / "ui.png"), full_page=True)
                browser.close()
        except Exception as exc:
            self.record("ARTIFACT_GAP", artifact="ui.png", reason=str(exc))

    def capture(self):
        for name, path in [
            ("ride", f"/rides/{self.ride_id}"),
            ("timeline", f"/rides/{self.ride_id}/timeline"),
            ("incidents", "/operations/incidents"),
        ]:
            if not self.ride_id and name != "incidents":
                continue
            try:
                (self.directory / f"{name}.json").write_text(
                    json.dumps(self.request("GET", path), indent=2)
                )
            except Exception as exc:
                self.record("ARTIFACT_GAP", artifact=name, reason=str(exc))
        try:
            (self.directory / "relay-state.json").write_text(
                json.dumps(
                    self.request("GET", "/lab/evidence", service="relay"), indent=2
                )
            )
        except Exception as exc:
            self.record("ARTIFACT_GAP", artifact="relay", reason=str(exc))

    def close(self):
        try:
            self.capture()
        finally:
            for name in reversed(list(self.processes)):
                self.stop(name)
            for f in self.files:
                f.close()
            self.client.close()
            leftovers = [name for name, p in self.processes.items() if p.poll() is None]
            if leftovers:
                raise InfrastructureError(f"leftover processes: {leftovers}")
