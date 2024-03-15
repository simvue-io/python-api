import pytest

import simvue.run as sv_run

@pytest.mark.run
def test_log_metrics(create_test_run: tuple[sv_run.Run, dict]) -> None:
    METRICS = {
        "a": 10,
        "b": 1.2,
        "c": "word"
    }
    run, _ = create_test_run
    run.update_tags(["simvue_client_unit_tests", "test_log_metrics"])
    run.log_metrics(METRICS)


@pytest.mark.run
def test_log_metrics_offline(create_test_run_offline: tuple[sv_run.Run, dict]) -> None:
    METRICS = {
        "a": 10,
        "b": 1.2,
        "c": "word"
    }
    run, _ = create_test_run_offline
    run.update_tags(["simvue_client_unit_tests", "test_log_metrics"])
    run.log_metrics(METRICS)


@pytest.mark.run
def test_log_events(create_test_run: tuple[sv_run.Run, dict]) -> None:
    EVENT_MSG = "Hello world!"
    run, _ = create_test_run
    run.update_tags(["simvue_client_unit_tests", "test_log_events"])
    run.log_event(EVENT_MSG)


@pytest.mark.run
def test_log_events_offline(create_test_run_offline: tuple[sv_run.Run, dict]) -> None:
    EVENT_MSG = "Hello world!"
    run, _ = create_test_run_offline
    run.update_tags(["simvue_client_unit_tests", "test_log_events"])
    run.log_event(EVENT_MSG)


@pytest.mark.run
def test_update_metadata(create_test_run: tuple[sv_run.Run, dict]) -> None:
    METADATA = {
        "a": 10,
        "b": 1.2,
        "c": "word"
    }
    run, _ = create_test_run
    run.update_tags(["simvue_client_unit_tests", "test_update_metadata"])
    run.update_metadata(METADATA)


@pytest.mark.run
def test_update_metadata_offline(create_test_run_offline: tuple[sv_run.Run, dict]) -> None:
    METADATA = {
        "a": 10,
        "b": 1.2,
        "c": "word"
    }
    run, _ = create_test_run_offline
    run.update_tags(["simvue_client_unit_tests", "test_update_metadata"])
    run.update_metadata(METADATA)
