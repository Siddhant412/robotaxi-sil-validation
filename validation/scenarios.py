from validation.oracles import full_ride


def test_T01_full_ride(episode):
    e = episode
    e.create()
    e.until(lambda: e.ride()["state"] == "COMPLETED")
    full_ride(e)


from concurrent.futures import ThreadPoolExecutor
import json
import httpx
from validation.oracles import quiescent_interval, stopped_at


def test_T02_duplicate_request(episode):
    e = episode
    first = e.create()
    second = e.create()
    assert first["ride_id"] == second["ride_id"]
    e.request(
        "POST",
        "/rides",
        {"origin": "B"},
        headers={"Idempotency-Key": "request-1"},
        expected=409,
    )
    commands = e.request("GET", "/vehicles/taxi/commands")["commands"]
    assert len(commands) == 1
    e.until(lambda: e.ride()["state"] == "COMPLETED")
    full_ride(e)


def test_T03_assignment_concurrency(episode):
    e = episode

    def submit(k):
        return httpx.post(
            e.urls["backend"] + "/rides",
            json={},
            headers={"Idempotency-Key": k},
            timeout=5,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(submit, ["first", "second"]))
    assert sorted(r.status_code for r in responses) == [200, 409]
    e.ride_id = next(r.json()["ride_id"] for r in responses if r.status_code == 200)
    assert len(e.request("GET", "/vehicles/taxi/commands")["commands"]) == 1


def test_T04_cancel_approaching(episode):
    e = episode
    e.create()
    e.step(8)
    assert e.agent()["observation"]["speed"] > 0
    pending = e.action("cancel")
    assert pending["state"] == "CANCEL_REQUESTED"
    e.until(lambda: e.ride()["state"] == "CANCELLED", 160)
    assert stopped_at(e.samples, "e0", 30)
    quiescent_interval(e)


def stale_assignment(e):
    e.faults(hold_assignment=True)
    e.create()
    e.step()
    original = list(
        e.request("GET", "/lab/evidence", service="relay")["held"].values()
    )[0]
    assert original["mission_version"] == 1
    e.action("cancel")
    e.until(lambda: e.ride()["state"] == "CANCELLED", 10)
    e.faults(hold_assignment=False, release=True)
    quiescent_interval(e)
    logs = [
        json.loads(x) for x in (e.directory / "agent.jsonl").read_text().splitlines()
    ]
    assert any(
        x["kind"] == "REJECTED" and x["event"]["command_id"] == original["command_id"]
        for x in logs
    )


def test_T05_stale_assignment(episode):
    try:
        stale_assignment(episode)
    finally:
        episode.screenshot()


def test_T06_duplicate_ack_loss(episode):
    e = episode
    e.faults(drop_ack=2, duplicate=True)
    e.create()
    e.step(4)
    evidence = e.request("GET", "/lab/evidence", service="relay")
    assert len(evidence["attempts"]) == 1
    assert max(evidence["attempts"].values()) > 1
    e.until(lambda: e.ride()["state"] == "COMPLETED")
    full_ride(e)


def test_T07_reordered_events(episode):
    e = episode
    e.faults(hold_kinds=["TELEMETRY"])
    e.create()
    e.step(3)
    e.faults(hold_kinds=[])
    e.step(4)
    before = e.ride()
    e.faults(release=True)
    e.step()
    after = e.ride()
    assert after["state"] == before["state"] == "APPROACHING"
    assert after["telemetry"]["time"] > before["telemetry"]["time"]
    timeline = e.request("GET", f"/rides/{e.ride_id}/timeline")
    assert any(x.get("late") for x in timeline)
    e.faults(hold_kinds=["READY_FOR_BOARDING"])
    e.until(lambda: e.agent()["state"]["execution"] == "IN_TRIP", 100)
    assert e.ride()["state"] == "APPROACHING"
    e.faults(hold_kinds=[], release=True)
    e.step()
    assert e.ride()["state"] == "IN_TRIP"
    e.until(lambda: e.ride()["state"] == "COMPLETED")
    full_ride(e)


def test_T08_partition(episode):
    e = episode
    e.create()
    e.step(6)
    lost = e.agent()["observation"]["time"]
    e.faults(partition=True)
    e.step(6)
    assert not e.ride()["telemetry_fresh"]
    e.until(lambda: e.agent()["state"]["execution"] == "HOLDING", 12)
    initiated = e.agent()["observation"]["time"]
    assert initiated - lost <= 13
    e.until(
        lambda: bool(stopped_at([{"observation": e.agent()["observation"]}], "e0", 30)),
        160,
    )
    assert e.ride()["state"] != "COMPLETED"
    restored = e.agent()["observation"]["time"]
    e.faults(partition=False)
    e.step()
    assert e.ride()["telemetry_fresh"]
    assert e.agent()["state"]["execution"] == "APPROACHING"
    e.record(
        "PARTITION_METRIC",
        lost=lost,
        holding_initiated=initiated,
        restored=restored,
        reconciled=e.agent()["observation"]["time"],
        clock="simulation",
    )
    e.until(lambda: e.ride()["state"] == "COMPLETED")
    full_ride(e)


def test_T09_backend_restart(episode):
    e = episode
    e.create()
    e.step(6)
    before = e.ride()
    timeline = e.request("GET", f"/rides/{e.ride_id}/timeline")
    e.stop("backend")
    # This is a real unavailable HTTP process, separately from the partition rule.
    e.step(2)
    e.launch("backend")
    after = e.ride()
    assert after["ride_id"] == before["ride_id"]
    assert after["mission_version"] == before["mission_version"]
    assert e.request("GET", f"/rides/{e.ride_id}/timeline") == timeline
    e.step()
    e.until(lambda: e.ride()["state"] == "COMPLETED")
    full_ride(e)
    assert "TRANSPORT_ERROR" in (e.directory / "relay.jsonl").read_text()


def test_T10_agent_restart_tombstone(episode):
    e = episode
    e.faults(hold_assignment=True)
    e.create()
    e.step()
    e.action("cancel")
    e.until(lambda: e.ride()["state"] == "CANCELLED", 10)
    old_boot = e.agent()["boot_id"]
    e.restart("agent")
    assert e.agent()["boot_id"] != old_boot
    e.faults(hold_assignment=False, release=True)
    quiescent_interval(e)


def test_T11_pickup_change(episode):
    e = episode
    e.create()
    e.step(5)
    e.request(
        "POST", "/lab/occupancy", {"point": "A", "occupied": True}, service="agent"
    )
    e.step()
    assert e.agent()["state"]["execution"] == "BLOCKED_PICKUP"
    r = e.action(
        "pickup", pickup="B", operator="demo", reason="synthetic curb A occupied"
    )
    assert not r["passenger_ready"]
    e.until(lambda: e.ride()["state"] == "READY_FOR_BOARDING", 100)
    e.step(5)
    assert e.ride()["state"] == "READY_FOR_BOARDING"
    assert stopped_at(e.samples, "e1", 220)
    assert not stopped_at(e.samples, "e1", 100)
    e.action("ready")
    e.until(lambda: e.ride()["state"] == "COMPLETED")
    assert e.ride()["pickup"] == e.agent()["state"]["mission"]["pickup"] == "B"
    assert e.ride()["completion_effects"] == 1


def test_T12_duplicate_completion(episode):
    e = episode
    e.create()
    e.until(lambda: e.ride()["state"] == "COMPLETED")
    full_ride(e)
    timeline = e.request("GET", f"/rides/{e.ride_id}/timeline")
    event = next(
        x["event"]
        for x in timeline
        if x["kind"] == "EVENT_RECEIVED" and x["event"]["kind"] == "COMPLETED"
    )
    e.request("POST", "/vehicle-events", event)
    e.request("POST", "/vehicle-events", event)
    assert e.ride()["completion_effects"] == 1
    assert (
        sum(
            x["kind"] == "COMPLETED"
            for x in e.request("GET", f"/rides/{e.ride_id}/timeline")
        )
        == 1
    )


def test_T13_stale_operator(episode):
    e = episode
    r = e.create()
    e.step(2)
    e.request(
        "POST",
        f"/rides/{e.ride_id}/pickup",
        {
            "expected_revision": r["server_revision"],
            "pickup": "B",
            "operator": "demo",
            "reason": "old screen",
        },
        expected=409,
    )
    assert e.ride()["pickup"] == "A"
    assert any(
        x["kind"] == "OPERATOR_PICKUP_REJECTED"
        for x in e.request("GET", f"/rides/{e.ride_id}/timeline")
    )
    e.action("pickup", pickup="B", operator="demo", reason="available alternative")
    assert any(
        x["kind"] == "OPERATOR_PICKUP" and x["operator"] == "demo"
        for x in e.request("GET", f"/rides/{e.ride_id}/timeline")
    )


def test_T14_old_lease(episode):
    e = episode
    e.create()
    e.request("GET", "/vehicles/taxi/commands")
    e.step(2)
    e.action("cancel")
    e.until(lambda: e.ride()["state"] == "CANCELLED", 160)
    # Re-submit old event and observe no execution; terminal intent is never lease refreshed.
    e.faults(replay_intent=True)
    e.step(12)
    quiescent_interval(e)
    assert e.agent()["state"]["lease"] < e.agent()["observation"]["time"]


def test_T15_cancel_boarding_race(episode):
    e = episode
    e.create()
    e.until(lambda: e.ride()["state"] == "READY_FOR_BOARDING")
    e.action("cancel")
    e.step(3)
    assert not e.agent()["state"].get("onboard", False)
    e.until(lambda: e.ride()["state"] == "CANCELLED", 160)
    quiescent_interval(e, 5)


def test_T15_cancel_after_boarding(episode):
    e = episode
    e.create()
    e.until(lambda: e.ride()["state"] == "IN_TRIP")
    r = e.ride()
    e.request(
        "POST",
        f"/rides/{e.ride_id}/cancel",
        {"expected_revision": r["server_revision"]},
        expected=409,
    )
    e.until(lambda: e.ride()["state"] == "COMPLETED")
    full_ride(e)


def test_T16_simulator_exit(episode):
    e = episode
    e.create()
    e.step(2)
    e.request("POST", "/lab/simulator-exit", {}, service="agent")
    r = e.request("POST", "/lab/step", {"steps": 1}, service="agent", expected=500)
    assert r["category"] == "infrastructure"
    assert e.ride()["state"] != "COMPLETED"


def test_T08_partition_cancel(episode):
    e = episode
    e.create()
    e.step(5)
    e.faults(partition=True)
    e.action("cancel")
    e.step(15)
    assert e.ride()["state"] == "CANCEL_REQUESTED"
    assert not e.ride()["telemetry_fresh"]
    e.until(
        lambda: bool(stopped_at([{"observation": e.agent()["observation"]}], "e0", 30)),
        160,
    )
    e.faults(partition=False)
    e.until(lambda: e.ride()["state"] == "CANCELLED", 5)
    quiescent_interval(e)
