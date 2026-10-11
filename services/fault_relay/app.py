"""Run-scoped application-message faults. Control traffic never traverses faults."""

import os
import httpx
from fastapi import FastAPI, HTTPException
from lab.common import log, uid

app = FastAPI()
backend = os.environ["BACKEND_URL"]
client = httpx.Client(timeout=0.5)
rules = {
    "partition": False,
    "hold_assignment": False,
    "hold_kinds": [],
    "drop_ack": 0,
    "duplicate": False,
    "replay_intent": False,
}
held = {}
release = []
seen = {}
last_active = None


@app.get("/health")
@app.get("/ready")
async def health():
    return {"ready": True}


@app.post("/lab/faults")
async def faults(data: dict):
    if os.environ.get("LAB_MODE") != "1":
        raise HTTPException(404)
    unknown = set(data) - set(rules) - {"release", "clear"}
    if unknown:
        raise HTTPException(422, f"unknown rules: {unknown}")
    if data.get("clear"):
        rules.update(
            partition=False,
            hold_assignment=False,
            hold_kinds=[],
            drop_ack=0,
            duplicate=False,
        )
    if data.get("release"):
        release.extend(held.values())
        held.clear()
    rules.update({k: v for k, v in data.items() if k in rules})
    log("relay", "RULE_CHANGE", rules=rules.copy(), action=data)
    return {"rules": rules, "held": list(held), "released": len(release)}


def forward(method, path, data=None):
    if rules["partition"]:
        log("relay", "PARTITION_REJECT", path=path, delivery_attempt_id=uid())
        raise HTTPException(503, "simulated partition")
    try:
        r = client.request(method, backend + path, json=data)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPError as exc:
        log(
            "relay",
            "TRANSPORT_ERROR",
            path=path,
            reason=str(exc),
            delivery_attempt_id=uid(),
        )
        raise HTTPException(503, str(exc)) from exc


@app.get("/vehicles/taxi/commands")
async def commands(time: float = 1):
    global last_active
    payload = forward("GET", f"/vehicles/taxi/commands?time={time}")
    if payload["intent"] and payload["intent"]["state"] not in {
        "CANCEL_REQUESTED",
        "CANCELLED",
        "COMPLETED",
        "FAILED",
    }:
        last_active = payload["intent"].copy()
    if rules["replay_intent"] and last_active:
        payload["intent"] = last_active.copy()
        log(
            "relay",
            "OBSOLETE_LEASE_DELIVERED",
            mission_version=last_active["mission_version"],
            time=time,
            delivery_attempt_id=uid(),
        )
    result = []
    released_ids = {x.get("command_id") for x in release if "command_id" in x}
    for c in payload["commands"]:
        cid = c["command_id"]
        seen[cid] = seen.get(cid, 0) + 1
        attempt = uid()
        log(
            "relay",
            "COMMAND_ATTEMPT",
            command=c,
            delivery_attempt_id=attempt,
            attempt=seen[cid],
        )
        if (
            c["kind"] == "ASSIGN"
            and rules["hold_assignment"]
            and cid not in released_ids
        ):
            if len(held) >= 512 and cid not in held:
                raise HTTPException(503, "relay queue capacity exhausted")
            held[cid] = c
            log("relay", "HELD", command_id=cid, time=time, delivery_attempt_id=attempt)
        else:
            result.append(c)
            log(
                "relay",
                "COMMAND_DELIVERED",
                command_id=cid,
                time=time,
                delivery_attempt_id=attempt,
            )
            if rules["duplicate"]:
                result.append(c)
    # Release old commands after fresh commands: deterministic reordering barrier.
    for c in list(release):
        if "event_id" not in c:
            result.append(c)
            release.remove(c)
            log(
                "relay",
                "COMMAND_RELEASED",
                command_id=c["command_id"],
                time=time,
                delivery_attempt_id=uid(),
            )
    payload["commands"] = result
    return payload


@app.post("/vehicle-events")
async def events(e: dict):
    attempt = uid()
    log("relay", "EVENT_ATTEMPT", event=e, delivery_attempt_id=attempt)
    if rules["partition"]:
        return forward("POST", "/vehicle-events", e)
    if e["kind"] == "ACK" and rules["drop_ack"] > 0:
        rules["drop_ack"] -= 1
        log(
            "relay",
            "ACK_SUPPRESSED",
            event_id=e["event_id"],
            delivery_attempt_id=attempt,
        )
        raise HTTPException(503, "ack response suppressed; retry same event")
    if e["kind"] in rules["hold_kinds"]:
        if len(held) >= 512 and e["event_id"] not in held:
            raise HTTPException(503, "relay queue capacity exhausted")
        held[e["event_id"]] = e
        log("relay", "HELD_EVENT", event_id=e["event_id"], delivery_attempt_id=attempt)
        return {"queued": True}
    result = forward("POST", "/vehicle-events", e)
    log("relay", "EVENT_DELIVERED", event_id=e["event_id"], delivery_attempt_id=attempt)
    if rules["duplicate"]:
        forward("POST", "/vehicle-events", e)
    for item in list(release):
        if "event_id" in item:
            forward("POST", "/vehicle-events", item)
            release.remove(item)
            log(
                "relay",
                "EVENT_RELEASED",
                event_id=item["event_id"],
                delivery_attempt_id=uid(),
            )
    return result


@app.get("/lab/evidence")
async def evidence():
    if os.environ.get("LAB_MODE") != "1":
        raise HTTPException(404)
    return {"rules": rules, "held": held, "release": release, "attempts": seen}
