def test_HTTP_validation_and_idempotency_scope(episode):
    e = episode
    e.request(
        "POST",
        "/rides",
        {"origin": "invalid"},
        headers={"Idempotency-Key": "x"},
        expected=422,
    )
    e.request("POST", "/rides", {}, expected=422)
    r = e.create()
    assert r["state"] == "ASSIGNED"
    e.request(
        "POST", f"/rides/{e.ride_id}/cancel", {"expected_revision": 0}, expected=422
    )
    e.request("POST", "/vehicle-events", {"kind": "invented"}, expected=422)
    assert e.ride()["state"] == "ASSIGNED"


def test_HTTP_walking_constraint(episode):
    e = episode
    e.create(allowed_walking_limit=50)
    r = e.ride()
    e.request(
        "POST",
        f"/rides/{e.ride_id}/pickup",
        {
            "expected_revision": r["server_revision"],
            "pickup": "B",
            "operator": "demo",
            "reason": "curb unavailable",
        },
        expected=409,
    )
    assert e.ride()["pickup"] == "A"
