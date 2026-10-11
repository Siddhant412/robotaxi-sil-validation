import json
import time
import pytest
from playwright.sync_api import sync_playwright, expect


@pytest.fixture
def page(episode):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context()
        context.tracing.start(screenshots=True, snapshots=True, sources=True)
        page = context.new_page()
        page.set_default_timeout(5000)
        page.goto(episode.urls["backend"])
        try:
            yield page
        finally:
            page.screenshot(path=str(episode.directory / "ui.png"), full_page=True)
            context.tracing.stop(path=str(episode.directory / "browser-trace.zip"))
            browser.close()


def requested(e, page):
    page.locator("#request").click()
    expect(page.locator("#status")).to_have_text("Assigned")
    e.ride_id = page.evaluate("rideId")
    return e.ride()


def test_UI_normal(episode, page):
    e = episode
    requested(e, page)
    e.step()
    expect(page.locator("#status")).to_have_text("Approaching")
    e.until(lambda: e.ride()["state"] == "READY_FOR_BOARDING")
    expect(page.locator("#status")).to_have_text("Ready for boarding")
    e.step(2)
    expect(page.locator("#status")).to_have_text("In trip")
    e.until(lambda: e.ride()["state"] == "COMPLETED")
    start = time.monotonic()
    expect(page.locator("#status")).to_have_text("Completed")
    e.record(
        "UI_CONVERGENCE",
        wall_seconds=time.monotonic() - start,
        state="COMPLETED",
        clock="wall",
    )


def test_UI_cancel_pending_confirmed(episode, page):
    e = episode
    e.faults(hold_assignment=True)
    requested(e, page)
    e.step()
    expect(page.locator("#freshness")).to_contain_text("unknown")
    page.locator("#cancel").click()
    expect(page.locator("#status")).to_contain_text("awaiting vehicle confirmation")
    e.until(lambda: e.ride()["state"] == "CANCELLED", 10)
    expect(page.locator("#status")).to_have_text(
        "Cancelled — vehicle confirmed holding"
    )


def test_UI_stale(episode, page):
    e = episode
    requested(e, page)
    e.step(2)
    expect(page.locator("#freshness")).to_have_text("Vehicle status fresh")
    e.faults(partition=True)
    e.step(6)
    expect(page.locator("#freshness")).to_contain_text("stale / unknown")
    assert "live" in page.locator("#freshness").inner_text()
    e.faults(partition=False)
    e.step()
    expect(page.locator("#freshness")).to_have_text("Vehicle status fresh")


def test_UI_pickup_revision_operator(episode, page):
    e = episode
    old = requested(e, page)
    page.locator("#change").click()
    expect(page.locator("#pickup")).to_contain_text("Pickup B")
    assert not e.ride()["passenger_ready"]
    # Inject an old server response at the browser's HTTP boundary.
    page.route(
        "**/rides/" + e.ride_id,
        lambda route: route.fulfill(
            status=200, content_type="application/json", body=json.dumps(old)
        ),
    )
    page.evaluate("poll()")
    expect(page.locator("#pickup")).to_contain_text("Pickup B")
    page.unroute("**/rides/" + e.ride_id)
    e.until(lambda: e.ride()["state"] == "READY_FOR_BOARDING", 100)
    expect(page.locator("#ready")).to_be_enabled()
    page.locator("#ready").click()
    expect(page.locator("#pickup")).to_contain_text("passenger ready")
    e.until(lambda: e.ride()["state"] == "COMPLETED")
    expect(page.locator("#status")).to_have_text("Completed")
    page.locator("#timeline").click()
    expect(page.locator("#audit")).to_contain_text("OPERATOR_PICKUP")
