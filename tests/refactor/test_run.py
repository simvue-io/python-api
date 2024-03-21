import pytest
import time
import contextlib

import simvue.run as sv_run
import simvue.client as sv_cl

@pytest.mark.run
def test_log_metrics(create_plain_run: tuple[sv_run.Run, dict]) -> None:
    METRICS = {
        "a": 10,
        "b": 1.2
    }
    run, run_data = create_plain_run
    run.update_tags(["simvue_client_unit_tests", "test_log_metrics"])
    run.log_metrics(METRICS)
    time.sleep(2.)
    run.close()
    client = sv_cl.Client()
    assert client.get_metrics_multiple([run_data["run_id"]], list(METRICS.keys()), xaxis="step")
    
    with contextlib.suppress(RuntimeError):
        client.delete_run(run_data["run_id"])

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
