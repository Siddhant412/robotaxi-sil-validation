"""External requirements checks; does not import product transition functions."""


def stopped_at(samples, edge, pos):
    return [
        s["observation"]
        for s in samples
        if s["observation"]["edge"] == edge
        and abs(s["observation"]["lane_pos"] - pos) < 1
        and s["observation"]["stopped"]
        and s["observation"]["speed"] < 0.01
    ]


def full_ride(e, pickup="A"):
    assert stopped_at(e.samples, "e1", 100 if pickup == "A" else 220), (
        "R05 no observed pickup stop"
    )
    assert stopped_at(e.samples, "e2", 180), "R06 no observed drop-off stop"
    r = e.ride()
    assert r["state"] == "COMPLETED"
    assert r["completion_effects"] == 1, "R06 duplicate/missing receipt"
    t = e.request("GET", f"/rides/{e.ride_id}/timeline")
    states = [
        x["kind"]
        for x in t
        if x["kind"]
        in {
            "ASSIGNED",
            "APPROACHING",
            "READY_FOR_BOARDING",
            "IN_TRIP",
            "DROPOFF_READY",
            "COMPLETED",
        }
    ]
    assert states == [
        "ASSIGNED",
        "APPROACHING",
        "READY_FOR_BOARDING",
        "IN_TRIP",
        "DROPOFF_READY",
        "COMPLETED",
    ], states
    for x in t:
        if x["kind"] == "EVENT_RECEIVED" and x["event"]["kind"] == "IN_TRIP":
            assert x["event"]["observation"]["stopped"], "R05 boarded while moving"
    assert len(stopped_at(e.samples, "e2", 180)) >= 3, "alighting dwell not observed"


def quiescent_interval(e, ticks=20):
    before = e.agent()["observation"]
    samples = [e.step() for _ in range(ticks)]
    for s in samples:
        o = s["observation"]
        assert o["stopped"] and o["speed"] < 0.01, (
            "R11 cancelled vehicle resumed motion"
        )
        assert sum((a - b) ** 2 for a, b in zip(o["xy"], before["xy"])) < 0.01, (
            "R03 cancelled route reactivated"
        )
        assert s["agent"]["execution"] in {"CANCELLED", "IDLE"}, (
            "R03 terminal mission resurrected"
        )
    assert e.ride()["state"] == "CANCELLED"
