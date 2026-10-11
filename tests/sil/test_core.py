import pytest
from validation import scenarios


@pytest.mark.critical
def test_T01_full_ride(episode):
    scenarios.test_T01_full_ride(episode)


@pytest.mark.critical
def test_T02_duplicate_request(episode):
    scenarios.test_T02_duplicate_request(episode)


def test_T03_assignment_concurrency(episode):
    scenarios.test_T03_assignment_concurrency(episode)


@pytest.mark.critical
def test_T04_cancel_approaching(episode):
    scenarios.test_T04_cancel_approaching(episode)


@pytest.mark.critical
def test_T05_stale_assignment(episode):
    scenarios.test_T05_stale_assignment(episode)


def test_T06_duplicate_ack_loss(episode):
    scenarios.test_T06_duplicate_ack_loss(episode)


@pytest.mark.critical
def test_T07_reordered_events(episode):
    scenarios.test_T07_reordered_events(episode)


@pytest.mark.critical
def test_T08_partition(episode):
    scenarios.test_T08_partition(episode)


@pytest.mark.critical
def test_T09_backend_restart(episode):
    scenarios.test_T09_backend_restart(episode)


def test_T10_agent_restart_tombstone(episode):
    scenarios.test_T10_agent_restart_tombstone(episode)


def test_T11_pickup_change(episode):
    scenarios.test_T11_pickup_change(episode)


@pytest.mark.critical
def test_T12_duplicate_completion(episode):
    scenarios.test_T12_duplicate_completion(episode)


def test_T13_stale_operator(episode):
    scenarios.test_T13_stale_operator(episode)


def test_T14_old_lease(episode):
    scenarios.test_T14_old_lease(episode)


def test_T15_cancel_boarding_race(episode):
    scenarios.test_T15_cancel_boarding_race(episode)


def test_T15_cancel_after_boarding(episode):
    scenarios.test_T15_cancel_after_boarding(episode)


def test_T16_simulator_exit(episode):
    scenarios.test_T16_simulator_exit(episode)


@pytest.mark.critical
def test_T08_partition_cancel(episode):
    scenarios.test_T08_partition_cancel(episode)
