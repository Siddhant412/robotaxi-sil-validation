"""Single HTTPServer thread owns commands, state transactions, and all TraCI calls."""

import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
import httpx
from lab.common import DIR, RUN, db, log, uid
from lab.simulator import Simulator

conn = db("agent")
conn.executescript("""CREATE TABLE IF NOT EXISTS state(id INTEGER PRIMARY KEY,data TEXT);
CREATE TABLE IF NOT EXISTS processed(id TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS tombstones(ride TEXT PRIMARY KEY,version INTEGER);
CREATE TABLE IF NOT EXISTS feedback(id TEXT PRIMARY KEY,data TEXT,attempts INTEGER DEFAULT 0);
""")
row = conn.execute("SELECT data FROM state WHERE id=1").fetchone()
state = (
    json.loads(row[0])
    if row
    else {
        "sequence": 0,
        "producer": 0,
        "mission": None,
        "execution": "IDLE",
        "lease": 0,
        "dwell": 0,
        "occupied": [],
    }
)
boot = uid()
profile = os.environ.get("PROFILE", "corrected")
client = httpx.Client(timeout=0.5)
relay = os.environ["RELAY_URL"]
sim = Simulator(
    DIR,
    seed=int(os.environ.get("SUMO_SEED", "42")),
    gui=os.environ.get("SUMO_GUI") == "1",
    port=int(os.environ["TRACI_PORT"]),
)
snapshot = DIR / "sumo-state.xml"
if row:
    if not snapshot.exists():
        raise RuntimeError("agent restart requires retained SUMO snapshot")
    sim.c.simulation.loadState(str(snapshot))
    sim.time = sim.c.simulation.getTime()
    state["lease"] = 0  # No resumed execution before current intent reconciliation.


def persist():
    conn.execute("INSERT OR REPLACE INTO state VALUES(1,?)", (json.dumps(state),))


def emit(kind, command_id=None, reason=None, obs=None):
    m = state["mission"]
    if not m:
        return
    if conn.execute("SELECT count(*) FROM feedback").fetchone()[0] >= 512:
        raise RuntimeError("feedback queue capacity exhausted")
    state["producer"] += 1
    e = dict(
        schema_version=1,
        run_id=RUN,
        event_id=uid(),
        ride_id=m["ride_id"],
        mission_version=m["mission_version"],
        producer_sequence=state["producer"],
        boot_id=boot,
        kind=kind,
        time=sim.time,
        observation=obs or sim.observe(),
        execution=state["execution"],
        causation_id=command_id or m["command_id"],
        command_id=command_id,
        reason=reason,
    )
    conn.execute(
        "INSERT INTO feedback(id,data) VALUES(?,?)", (e["event_id"], json.dumps(e))
    )
    persist()
    log("agent", kind, event=e)


def apply(c):
    if c["run_id"] != RUN:
        raise RuntimeError("cross-run command")
    cid = c["command_id"]
    if conn.execute("SELECT 1 FROM processed WHERE id=?", (cid,)).fetchone():
        # Retry acknowledgement without executing route again.
        emit("ACK", cid)
        return
    tomb = conn.execute(
        "SELECT version FROM tombstones WHERE ride=?", (c["ride_id"],)
    ).fetchone()
    obsolete = (
        bool(
            state["mission"]
            and state["mission"]["ride_id"] == c["ride_id"]
            and c["mission_version"] < state["mission"]["mission_version"]
        )
        or c["vehicle_command_sequence"] <= state["sequence"]
    ) or bool(tomb and c["kind"] != "CANCEL")
    if profile == "defective" and c["kind"] == "ASSIGN":
        obsolete = False
    if obsolete or (c["kind"] != "CANCEL" and c["expires_at"] < sim.time):
        emit(
            "REJECTED",
            cid,
            reason="obsolete sequence, tombstone, or expired authorization",
        )
        # Rejections are durably consumed too; no infinite command retry.
        conn.execute("INSERT OR IGNORE INTO processed VALUES(?)", (cid,))
        emit("ACK", cid)
        return
    state["sequence"] = max(state["sequence"], c["vehicle_command_sequence"])
    if c["kind"] == "CANCEL":
        state["mission"] = c
        conn.execute(
            "INSERT OR REPLACE INTO tombstones VALUES(?,?)",
            (c["ride_id"], c["mission_version"]),
        )
        state["execution"] = "CANCELLING"
        sim.holding()
    elif c["kind"] in {"ASSIGN", "PICKUP"}:
        state["mission"] = c
        state["execution"] = "APPROACHING"
        state["dwell"] = 0
        sim.target(c["pickup"])
        emit("APPROACHING", cid)
    elif c["kind"] == "READY":
        state["mission"] = c
    state["lease"] = c["expires_at"]
    conn.execute("INSERT INTO processed VALUES(?)", (cid,))
    persist()
    emit("ACK", cid)


def flush():
    for eid, data, attempts in conn.execute(
        "SELECT id,data,attempts FROM feedback ORDER BY rowid"
    ).fetchall():
        if attempts >= 256:
            raise RuntimeError("feedback retry budget exhausted")
        conn.execute("UPDATE feedback SET attempts=attempts+1 WHERE id=?", (eid,))
        try:
            response = client.post(relay + "/vehicle-events", json=json.loads(data))
            response.raise_for_status()
            conn.execute("DELETE FROM feedback WHERE id=?", (eid,))
        except httpx.HTTPError as exc:
            log(
                "agent",
                "EVENT_RETRY",
                event_id=eid,
                reason=str(exc),
                attempt=attempts + 1,
            )
            # Continue: later observations may overtake a delayed event.


def step():
    try:
        response = client.get(
            relay + "/vehicles/taxi/commands", params={"time": sim.time}
        )
        response.raise_for_status()
        p = response.json()
        conn.execute("BEGIN IMMEDIATE")
        try:
            for c in p["commands"]:
                apply(c)
            m = state["mission"]
            intent = p["intent"]
            if (
                m
                and intent
                and intent["ride_id"] == m["ride_id"]
                and intent["mission_version"] == m["mission_version"]
                and intent["state"]
                not in {"CANCELLED", "COMPLETED", "FAILED", "CANCEL_REQUESTED"}
            ):
                state["lease"] = p["lease_until"]
                if state["execution"] == "HOLDING":
                    state["execution"] = (
                        "APPROACHING" if not state.get("onboard") else "IN_TRIP"
                    )
                    sim.target(m["pickup"] if not state.get("onboard") else "D")
            persist()
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
    except httpx.HTTPError as exc:
        log("agent", "CHANNEL_UNAVAILABLE", time=sim.time, reason=str(exc))
    m = state["mission"]
    if (
        m
        and state["execution"] in {"APPROACHING", "READY_FOR_BOARDING"}
        and m["pickup"] in state.get("occupied", [])
    ):
        state["execution"] = "BLOCKED_PICKUP"
        sim.holding()
        emit("HOLDING", reason="modeled pickup occupied; operator alternative required")
    if (
        m
        and sim.time >= state["lease"]
        and state["execution"]
        in {"APPROACHING", "READY_FOR_BOARDING", "IN_TRIP", "DROPOFF_READY"}
    ):
        state["execution"] = "HOLDING"
        sim.holding()
        emit(
            "HOLDING", reason="execution lease expired; designated H holding initiated"
        )
    obs = sim.step()
    if m:
        execution = state["execution"]
        if execution == "APPROACHING" and sim.at(m["pickup"], obs):
            state["execution"] = "READY_FOR_BOARDING"
            state["dwell"] = sim.time
            emit("READY_FOR_BOARDING", obs=obs)
        elif (
            execution == "READY_FOR_BOARDING"
            and m["passenger_ready"]
            and sim.at(m["pickup"], obs)
            and sim.time - state["dwell"] >= 2
        ):
            state["execution"] = "IN_TRIP"
            state["onboard"] = True
            emit("IN_TRIP", obs=obs)
            sim.target("D")
        elif execution == "IN_TRIP" and sim.at("D", obs):
            state["execution"] = "DROPOFF_READY"
            state["dwell"] = sim.time
            emit("DROPOFF_READY", obs=obs)
        elif (
            execution == "DROPOFF_READY"
            and sim.at("D", obs)
            and sim.time - state["dwell"] >= 2
        ):
            state["execution"] = "COMPLETED"
            state["onboard"] = False
            conn.execute(
                "INSERT OR REPLACE INTO tombstones VALUES(?,?)",
                (m["ride_id"], m["mission_version"]),
            )
            emit("COMPLETED", obs=obs)
        elif execution == "CANCELLING" and sim.at("H", obs):
            state["execution"] = "CANCELLED"
            emit("CANCELLED", obs=obs)
        emit("TELEMETRY", obs=obs)
    persist()
    flush()
    # Checkpoint is a lab recovery artifact, not a claim of exact crash-state replay.
    sim.c.simulation.saveState(str(snapshot))
    return {"observation": obs, "agent": state.copy()}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path == "/lab/state" and os.environ.get("LAB_MODE") != "1":
            return self.reply(404, {})
        if self.path in {"/health", "/ready", "/lab/state"}:
            self.reply(
                200,
                {
                    "ready": True,
                    "boot_id": boot,
                    "state": state,
                    "observation": sim.observe(),
                },
            )
        else:
            self.reply(404, {})

    def do_POST(self):
        try:
            if os.environ.get("LAB_MODE") != "1":
                return self.reply(404, {})
            data = json.loads(
                self.rfile.read(int(self.headers.get("Content-Length", "0"))) or b"{}"
            )
            if self.path == "/lab/step":
                n = data.get("steps", 1)
                if not isinstance(n, int) or not 1 <= n <= 20:
                    return self.reply(422, {"error": "steps must be 1..20"})
                results = [step() for _ in range(n)]
                self.reply(200, {"samples": results})
            elif self.path == "/lab/occupancy":
                if data.get("point") not in {"A", "B"} or not isinstance(
                    data.get("occupied"), bool
                ):
                    return self.reply(
                        422, {"error": "invalid modeled pickup occupancy"}
                    )
                state.setdefault("occupied", [])
                if data["occupied"] and data["point"] not in state["occupied"]:
                    state["occupied"].append(data["point"])
                if not data["occupied"] and data["point"] in state["occupied"]:
                    state["occupied"].remove(data["point"])
                persist()
                log(
                    "agent",
                    "OCCUPANCY_MODEL",
                    point=data["point"],
                    occupied=data["occupied"],
                    time=sim.time,
                )
                self.reply(200, {"occupied": state["occupied"]})
            elif self.path == "/lab/simulator-exit":
                sim.close()
                self.reply(200, {"closed": True})
            else:
                self.reply(404, {})
        except Exception as exc:
            log("agent", "INFRASTRUCTURE_ERROR", reason=repr(exc), time=sim.time)
            self.reply(500, {"error": repr(exc), "category": "infrastructure"})

    def reply(self, status, data):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    try:
        HTTPServer(
            ("127.0.0.1", int(os.environ["AGENT_PORT"])), Handler
        ).serve_forever()
    finally:
        sim.close()
