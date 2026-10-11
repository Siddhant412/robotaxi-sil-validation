import json
import uuid
from pathlib import Path
import pytest
from lab.harness import Episode
from lab.simulator import build_network


@pytest.fixture(scope="session", autouse=True)
def network():
    build_network()


@pytest.fixture
def episode(request):
    directory = Path("artifacts") / (request.node.name + "-" + uuid.uuid4().hex[:8])
    request.node.lab_directory = directory
    e = Episode(directory, case=request.node.name)
    try:
        e.start()
        yield e
    finally:
        e.close()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    reports = getattr(item, "lab_reports", {})
    reports[report.when] = report
    item.lab_reports = reports
    if report.when == "teardown" and hasattr(item, "lab_directory"):
        failures = [r for r in reports.values() if r.failed]
        skips = [r for r in reports.values() if r.skipped]
        infrastructure = any(
            r.when != "call" or "InfrastructureError" in str(r.longrepr)
            for r in failures
        )
        result = {
            "test": item.name,
            "scenario_executed": "call" in reports and not reports["call"].skipped,
            "outcome": (
                "infrastructure_error"
                if infrastructure
                else "product_failure"
                if failures
                else "skipped"
                if skips
                else "pass"
            ),
            "details": "\n".join(str(r.longrepr) for r in failures) or None,
        }
        (item.lab_directory / "result.json").write_text(
            json.dumps(result, indent=2) + "\n"
        )
