"""The agent's single-threaded loop is the sole TraCI owner."""

from pathlib import Path
import json
import shutil
import subprocess
import traci

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / "simulation/points.json").read_text())
POINTS = {k: (v["edge"], v["position"]) for k, v in FIXTURE["points"].items()}


def build_network():
    subprocess.run(
        [
            shutil.which("netconvert")
            or str(Path(__import__("sumo").__file__).parent / "bin/netconvert"),
            "--node-files",
            str(ROOT / "simulation/neighborhood.nod.xml"),
            "--edge-files",
            str(ROOT / "simulation/neighborhood.edg.xml"),
            "--output-file",
            str(ROOT / "simulation/neighborhood.net.xml"),
            "--no-turnarounds",
            "true",
        ],
        check=True,
        capture_output=True,
    )


class Simulator:
    def __init__(self, directory, gui=False, seed=42, port=None):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        binary = shutil.which("sumo-gui" if gui else "sumo")
        if not binary:
            binary = str(
                Path(__import__("sumo").__file__).parent
                / ("bin/sumo-gui" if gui else "bin/sumo")
            )
        kwargs = {"port": port} if port else {}
        traci.start(
            [
                binary,
                "-n",
                str(ROOT / "simulation/neighborhood.net.xml"),
                "--step-length",
                "1",
                "--seed",
                str(seed),
                "--save-state.rng",
                "true",
                "--time-to-teleport",
                "-1",
                "--no-step-log",
                "true",
                "--log",
                str(self.directory / "sumo.log"),
                "--error-log",
                str(self.directory / "sumo-errors.log"),
                "--fcd-output",
                str(self.directory / "trajectory.xml"),
            ],
            **kwargs,
        )
        self.c = traci.getConnection("default")
        self.c.route.add("loop", ["e0", "e1", "e2", "e3", "e0"])
        self.c.vehicle.add("taxi", "loop", departPos="30", departSpeed="0")
        self.c.vehicle.setStop("taxi", "e0", pos=30, duration=100000.0)
        self.c.simulationStep()
        self.time = self.c.simulation.getTime()

    def target(self, point):
        edge, pos = POINTS[point]
        if self.at(point, self.observe()):
            return
        # replaceStop removes/replaces the currently planned stop and reroutes normally.
        if self.c.vehicle.isStopped("taxi"):
            self.c.vehicle.resume("taxi")
            self.c.vehicle.changeTarget("taxi", edge)
            self.c.vehicle.setStop("taxi", edge, pos=pos, duration=100000.0)
        else:
            self.c.vehicle.replaceStop(
                "taxi", 0, edge, pos=pos, duration=100000.0, teleport=0
            )

    def holding(self):
        # A reachable designated holding point is the next occurrence of H on the loop.
        self.target("H")

    def observe(self):
        if "taxi" not in self.c.vehicle.getIDList():
            raise RuntimeError("simulator vehicle unexpectedly removed")
        return {
            "time": self.c.simulation.getTime(),
            "edge": self.c.vehicle.getRoadID("taxi"),
            "lane_pos": self.c.vehicle.getLanePosition("taxi"),
            "xy": self.c.vehicle.getPosition("taxi"),
            "speed": self.c.vehicle.getSpeed("taxi"),
            "stopped": self.c.vehicle.isStopped("taxi"),
            "stop_state": self.c.vehicle.getStopState("taxi"),
        }

    def at(self, point, obs):
        edge, pos = POINTS[point]
        return (
            obs["edge"] == edge
            and abs(obs["lane_pos"] - pos) < 1
            and obs["stopped"]
            and obs["speed"] < 0.01
        )

    def step(self):
        self.c.simulationStep()
        if self.c.simulation.getStartingTeleportIDList():
            raise RuntimeError("unexpected simulator teleportation")
        self.time = self.c.simulation.getTime()
        obs = self.observe()
        with (self.directory / "observations.jsonl").open("a") as f:
            f.write(json.dumps(obs) + "\n")
        return obs

    def close(self):
        self.c.close()


def smoke(directory):
    build_network()
    s = Simulator(directory)
    try:
        s.target("A")
        s.target("B")  # Demonstrate replacement before reaching A.
        samples = [s.step() for _ in range(90)]
        assert any(o["speed"] > 1 for o in samples), "no observed motion"
        assert s.at("B", samples[-1]), samples[-1]
        print(
            json.dumps({"smoke": "PASS", "steps": len(samples), "final": samples[-1]})
        )
    finally:
        s.close()
