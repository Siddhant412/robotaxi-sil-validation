"""Single-process durable backend; every domain mutation and outbox write is atomic."""

import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from lab.common import RUN, db, log, uid

app = FastAPI()
conn = db("backend")
conn.executescript("""
CREATE TABLE IF NOT EXISTS rides(id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS assignments(vehicle TEXT PRIMARY KEY, ride TEXT UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS outbox(id TEXT PRIMARY KEY, data TEXT NOT NULL, ack INTEGER DEFAULT 0, attempts INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS inbox(id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS idempotency(key TEXT PRIMARY KEY, payload TEXT NOT NULL, ride TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, ride TEXT, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS effects(ride TEXT PRIMARY KEY, kind TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value INTEGER);
INSERT OR IGNORE INTO meta VALUES('sequence',0);
INSERT OR IGNORE INTO meta VALUES('clock',1);
INSERT OR IGNORE INTO meta VALUES('producer',0);
""")
TERMINAL = {"CANCELLED", "COMPLETED", "FAILED"}
NEXT = {
    "ASSIGNED": "APPROACHING",
    "APPROACHING": "READY_FOR_BOARDING",
    "READY_FOR_BOARDING": "IN_TRIP",
    "IN_TRIP": "DROPOFF_READY",
    "DROPOFF_READY": "COMPLETED",
    "CANCEL_REQUESTED": "CANCELLED",
}


@contextmanager
def tx():
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise


def clock():
    return conn.execute("SELECT value FROM meta WHERE key='clock'").fetchone()[0]


def ride(rid):
    row = conn.execute("SELECT data FROM rides WHERE id=?", (rid,)).fetchone()
    if not row:
        raise HTTPException(404, "unknown ride")
    return json.loads(row[0])


def save(r):
    conn.execute(
        "INSERT OR REPLACE INTO rides VALUES(?,?)", (r["ride_id"], json.dumps(r))
    )


def audit(r, kind, **extra):
    data = dict(
        run_id=RUN,
        ride_id=r["ride_id"],
        kind=kind,
        time=clock(),
        server_revision=r["server_revision"],
        **extra,
    )
    conn.execute(
        "INSERT INTO audit(ride,data) VALUES(?,?)", (r["ride_id"], json.dumps(data))
    )
    log(
        "backend",
        kind,
        **{k: v for k, v in data.items() if k not in {"run_id", "kind"}},
    )


def command(r, kind):
    conn.execute("UPDATE meta SET value=value+1 WHERE key='sequence'")
    seq = conn.execute("SELECT value FROM meta WHERE key='sequence'").fetchone()[0]
    c = dict(
        schema_version=1,
        run_id=RUN,
        command_id=uid(),
        ride_id=r["ride_id"],
        mission_id=r["ride_id"],
        vehicle_id="taxi",
        kind=kind,
        mission_version=r["mission_version"],
        vehicle_command_sequence=seq,
        issued_at=clock(),
        expires_at=clock() + 12,
        pickup=r["pickup"],
        passenger_ready=r["passenger_ready"],
        causation_id=r["ride_id"],
    )
    conn.execute(
        "INSERT INTO outbox(id,data) VALUES(?,?)", (c["command_id"], json.dumps(c))
    )
    audit(r, "COMMAND_ISSUED", command=c)


class Create(BaseModel):
    origin: Literal["A", "B"] = "A"
    destination: Literal["D"] = "D"
    passenger_ready: bool = True
    allowed_walking_limit: float = Field(default=200, ge=0, le=1000)
    client_id: str = Field(default="synthetic", min_length=1, max_length=100)


class Revision(BaseModel):
    expected_revision: int = Field(ge=1)


class Pickup(Revision):
    pickup: Literal["B"] = "B"
    operator: str = Field(min_length=1, max_length=100)
    reason: str = Field(min_length=1, max_length=300)


class Event(BaseModel):
    schema_version: Literal[1] = 1
    run_id: str
    event_id: str
    ride_id: str
    mission_version: int = Field(ge=1)
    producer_sequence: int = Field(ge=1)
    boot_id: str
    kind: Literal[
        "ACK",
        "REJECTED",
        "APPROACHING",
        "READY_FOR_BOARDING",
        "IN_TRIP",
        "DROPOFF_READY",
        "COMPLETED",
        "CANCELLED",
        "TELEMETRY",
        "HOLDING",
        "FAILED",
    ]
    time: float = Field(ge=0)
    observation: dict
    execution: str
    causation_id: str
    command_id: str | None = None
    reason: str | None = None


@app.get("/health")
@app.get("/ready")
async def health():
    conn.execute("SELECT 1")
    return {"ready": True, "run_id": RUN}


@app.get("/")
async def ui():
    return HTMLResponse(
        (Path(__file__).resolve().parents[2] / "web/index.html").read_text()
    )


@app.post("/rides")
async def create(
    p: Create, idempotency_key: str = Header(min_length=1, max_length=200)
):
    payload = p.model_dump_json()
    key = p.client_id + ":POST/rides:" + idempotency_key
    with tx():
        old = conn.execute(
            "SELECT payload,ride FROM idempotency WHERE key=?", (key,)
        ).fetchone()
        if old:
            if old[0] != payload:
                raise HTTPException(409, "idempotency payload conflict")
            return ride(old[1])
        if conn.execute("SELECT 1 FROM assignments").fetchone():
            raise HTTPException(409, "vehicle already assigned; retry explicitly later")
        r = dict(
            ride_id=uid(),
            state="ASSIGNED",
            server_revision=1,
            mission_version=1,
            pickup=p.origin,
            passenger_ready=p.passenger_ready,
            allowed_walking_limit=p.allowed_walking_limit,
            telemetry=None,
            incident=None,
        )
        save(r)
        conn.execute("INSERT INTO assignments VALUES(?,?)", ("taxi", r["ride_id"]))
        conn.execute(
            "INSERT INTO idempotency VALUES(?,?,?)", (key, payload, r["ride_id"])
        )
        audit(r, "REQUESTED")
        audit(r, "ASSIGNED")
        command(r, "ASSIGN")
        return r


def get_ride(rid: str):
    r = ride(rid)
    r["telemetry_age"] = (
        None if r["telemetry"] is None else max(0, clock() - r["telemetry"]["time"])
    )
    r["telemetry_fresh"] = r["telemetry_age"] is not None and r["telemetry_age"] <= 4
    r["clock"] = clock()
    r["completion_effects"] = conn.execute(
        "SELECT count(*) FROM effects WHERE ride=?", (rid,)
    ).fetchone()[0]
    return r


@app.get("/rides/{rid}")
async def view_ride(rid: str):
    return get_ride(rid)


def expected(r, p):
    if p.expected_revision != r["server_revision"]:
        raise HTTPException(409, "stale server revision")


@app.post("/rides/{rid}/cancel")
async def cancel(rid: str, p: Revision):
    with tx():
        r = ride(rid)
        expected(r, p)
        if r["state"] in {"IN_TRIP", "DROPOFF_READY"} | TERMINAL | {"CANCEL_REQUESTED"}:
            raise HTTPException(409, "cancellation is only allowed before boarding")
        r.update(
            state="CANCEL_REQUESTED",
            mission_version=r["mission_version"] + 1,
            server_revision=r["server_revision"] + 1,
        )
        save(r)
        audit(r, "CANCEL_REQUESTED")
        command(r, "CANCEL")
        return r


@app.post("/rides/{rid}/pickup")
async def pickup(rid: str, p: Pickup):
    with tx():
        r = ride(rid)
        expected(r, p)
        if (
            r["state"] not in {"ASSIGNED", "APPROACHING", "READY_FOR_BOARDING"}
            or r["pickup"] != "A"
        ):
            raise HTTPException(409, "pickup update is obsolete or ineligible")
        from lab.simulator import FIXTURE

        access = FIXTURE["alternatives"]["A"]["B"]
        if (
            not access["accessible"]
            or r["allowed_walking_limit"] < access["walking_distance_m"]
        ):
            raise HTTPException(
                409, "alternative requires 120 m of annotated walking access"
            )
        r.update(
            pickup="B",
            passenger_ready=False,
            state="APPROACHING",
            mission_version=r["mission_version"] + 1,
            server_revision=r["server_revision"] + 1,
            incident="pickup A unavailable; passenger must confirm arrival at B",
        )
        save(r)
        audit(
            r,
            "OPERATOR_PICKUP",
            operator=p.operator,
            reason=p.reason,
            outcome="accepted",
        )
        command(r, "PICKUP")
        return r


@app.post("/rides/{rid}/ready")
async def passenger_ready(rid: str, p: Revision):
    with tx():
        r = ride(rid)
        expected(r, p)
        if r["state"] not in {"ASSIGNED", "APPROACHING", "READY_FOR_BOARDING"}:
            raise HTTPException(409, "readiness cannot change in this state")
        r.update(
            passenger_ready=True,
            mission_version=r["mission_version"] + 1,
            server_revision=r["server_revision"] + 1,
        )
        save(r)
        audit(r, "PASSENGER_READY")
        command(r, "READY")
        return r


@app.get("/vehicles/{vid}/commands")
async def commands(vid: str, time: float = 1):
    if vid != "taxi" or time < 0:
        raise HTTPException(422, "invalid vehicle or clock")
    with tx():
        conn.execute("UPDATE meta SET value=max(value,?) WHERE key='clock'", (time,))
        rows = conn.execute(
            "SELECT id,data,attempts FROM outbox WHERE ack=0 ORDER BY rowid"
        ).fetchall()
        outgoing = []
        for cid, data, attempts in rows:
            if attempts < 64:
                conn.execute("UPDATE outbox SET attempts=attempts+1 WHERE id=?", (cid,))
                outgoing.append(json.loads(data))
            elif attempts == 64:
                c = json.loads(data)
                r = ride(c["ride_id"])
                r["incident"] = "command retry budget exhausted"
                r["server_revision"] += 1
                save(r)
                audit(r, "COMMAND_RETRY_EXHAUSTED", command_id=cid)
                conn.execute("UPDATE outbox SET attempts=65 WHERE id=?", (cid,))
        row = conn.execute("SELECT ride FROM assignments").fetchone()
        r = ride(row[0]) if row else None
        return {
            "commands": outgoing,
            "intent": r,
            "lease_until": time + 12,
            "clock": clock(),
        }


@app.post("/vehicle-events")
async def events(e: Event):
    if e.run_id != RUN:
        raise HTTPException(409, "wrong run")
    d = e.model_dump()
    with tx():
        if conn.execute("SELECT 1 FROM inbox WHERE id=?", (e.event_id,)).fetchone():
            return {"duplicate": True}
        conn.execute("INSERT INTO inbox VALUES(?,?)", (e.event_id, json.dumps(d)))
        conn.execute("UPDATE meta SET value=max(value,?) WHERE key='clock'", (e.time,))
        r = ride(e.ride_id)
        high = conn.execute("SELECT value FROM meta WHERE key='producer'").fetchone()[0]
        conn.execute(
            "UPDATE meta SET value=max(value,?) WHERE key='producer'",
            (e.producer_sequence,),
        )
        audit(r, "EVENT_RECEIVED", event=d, late=e.producer_sequence <= high)
        if e.kind == "ACK" and e.command_id:
            conn.execute("UPDATE outbox SET ack=1 WHERE id=?", (e.command_id,))
        if e.mission_version != r["mission_version"]:
            return {"ignored": "obsolete mission version"}
        if e.kind == "TELEMETRY" and e.producer_sequence > high:
            r["telemetry"] = {
                "time": e.time,
                "observation": e.observation,
                "execution": e.execution,
            }
        elif e.kind in {"HOLDING", "FAILED"} and e.producer_sequence > high:
            r["incident"] = e.reason or e.kind
            if e.kind == "FAILED" and r["state"] not in TERMINAL:
                r["state"] = "FAILED"
                conn.execute("DELETE FROM assignments WHERE ride=?", (e.ride_id,))
        # Retain useful late progress independently of telemetry high-water marks.
        # Reconcile only the next legal transition, using received observation evidence.
        cached = [
            json.loads(row[0])
            for row in conn.execute("SELECT data FROM inbox ORDER BY rowid")
        ]
        for _ in range(7):
            following = NEXT.get(r["state"])
            candidates = [
                x
                for x in cached
                if x["ride_id"] == r["ride_id"]
                and x["mission_version"] == r["mission_version"]
                and x["kind"] == following
            ]
            if not candidates:
                break
            observed = min(candidates, key=lambda x: x["producer_sequence"])
            if following in {
                "READY_FOR_BOARDING",
                "IN_TRIP",
                "DROPOFF_READY",
                "COMPLETED",
                "CANCELLED",
            }:
                point = (
                    r["pickup"]
                    if following in {"READY_FOR_BOARDING", "IN_TRIP"}
                    else ("H" if following == "CANCELLED" else "D")
                )
                from lab.simulator import POINTS

                edge, pos = POINTS[point]
                o = observed["observation"]
                if not (
                    o.get("stopped")
                    and o.get("speed", 999) < 0.01
                    and o.get("edge") == edge
                    and abs(o.get("lane_pos", -999) - pos) < 1
                ):
                    raise HTTPException(409, "arrival evidence missing")
                if following == "IN_TRIP" and not r["passenger_ready"]:
                    raise HTTPException(409, "passenger is not ready")
            r["state"] = following
            audit(
                r,
                following,
                causation_id=observed["event_id"],
                observed_time=observed["time"],
            )
            if following in TERMINAL:
                conn.execute("DELETE FROM assignments WHERE ride=?", (e.ride_id,))
            if following == "COMPLETED":
                conn.execute(
                    "INSERT OR IGNORE INTO effects VALUES(?,'receipt')", (e.ride_id,)
                )
        r["server_revision"] += 1
        save(r)
        return {"accepted": True}


@app.get("/rides/{rid}/timeline")
async def timeline(rid: str):
    ride(rid)
    return [
        json.loads(x[0])
        for x in conn.execute("SELECT data FROM audit WHERE ride=? ORDER BY id", (rid,))
    ]


@app.get("/operations/incidents")
async def incidents():
    return [
        get_ride(x[0])
        for x in conn.execute("SELECT id FROM rides")
        if get_ride(x[0])["incident"] or not get_ride(x[0])["telemetry_fresh"]
    ]


@app.post("/lab/clock")
async def set_clock(data: dict):
    if os.environ.get("LAB_MODE") != "1":
        raise HTTPException(404)
    conn.execute(
        "UPDATE meta SET value=max(value,?) WHERE key='clock'", (data["time"],)
    )
    return {"clock": clock()}


# Rejected operator intent is audited in a separate transaction after rollback.
from fastapi import Request
from fastapi.responses import JSONResponse


@app.exception_handler(HTTPException)
async def rejected(request: Request, exc: HTTPException):
    if request.url.path.endswith("/pickup"):
        rid = request.url.path.split("/")[-2]
        body = await request.json()
        try:
            with tx():
                r = ride(rid)
                audit(
                    r,
                    "OPERATOR_PICKUP_REJECTED",
                    operator=body.get("operator"),
                    reason=body.get("reason"),
                    expected_revision=body.get("expected_revision"),
                    outcome="rejected",
                    detail=exc.detail,
                )
        except HTTPException:
            pass
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
