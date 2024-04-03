import pytest
import time
import typing
import contextlib
import concurrent.futures
import random

import simvue.run as sv_run
import simvue.client as sv_cl




@pytest.mark.run
@pytest.mark.parametrize("overload_buffer", (True, False))
def test_log_metrics(
    create_plain_run: tuple[sv_run.Run, dict], overload_buffer: bool, setup_logging, mocker
) -> None:
    setup_logging.capture = "Executing 'metrics' callback on buffer"
    METRICS = {"a": 10, "b": 1.2}
    run, run_data = create_plain_run
    run.update_tags(["simvue_client_unit_tests", "test_log_metrics"])
    if overload_buffer:
        for i in range(run._dispatcher._max_buffer_size * 3):
            run.log_metrics({key: i for key in METRICS.keys()})
    else:
        run.log_metrics(METRICS)
    time.sleep(2.0 if not overload_buffer else 3.0)
    run.close()
    client = sv_cl.Client()
    _data = client.get_metrics_multiple(
        [run_data["run_id"]], list(METRICS.keys()), xaxis="step"
    )

    with contextlib.suppress(RuntimeError):
        client.delete_run(run_data["run_id"])

    assert len(_data) == (
        len(METRICS) if not overload_buffer else len(METRICS) * run._dispatcher._max_buffer_size * 3
    )

    assert setup_logging.count == (1 if not overload_buffer else 3)


@pytest.mark.run
def test_log_metrics_offline(create_test_run_offline: tuple[sv_run.Run, dict]) -> None:
    METRICS = {"a": 10, "b": 1.2, "c": "word"}
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
    METADATA = {"a": 10, "b": 1.2, "c": "word"}
    run, _ = create_test_run
    run.update_tags(["simvue_client_unit_tests", "test_update_metadata"])
    run.update_metadata(METADATA)


@pytest.mark.run
def test_update_metadata_offline(
    create_test_run_offline: tuple[sv_run.Run, dict],
) -> None:
    METADATA = {"a": 10, "b": 1.2, "c": "word"}
    run, _ = create_test_run_offline
    run.update_tags(["simvue_client_unit_tests", "test_update_metadata"])
    run.update_metadata(METADATA)


@pytest.mark.run
@pytest.mark.parametrize("multi_threaded", (True, False), ids=("multi", "single"))
def test_runs_multiple_parallel(multi_threaded: bool) -> None:
    N_RUNS: int = 2
    if multi_threaded:
        def thread_func(index: int) -> tuple[list[dict[str, typing.Any]], str]:
            with sv_run.Run() as run:
                run.config(suppress_errors=False)
                run.init(
                    name=f"test_runs_multiple_{index + 1}",
                    tags=["simvue_client_unit_tests", "test_multi_run_threaded"],
                    folder="/simvue_unit_testing"
                )
                metrics = []
                for _ in range(10):
                    time.sleep(1)
                    metric = {f"var_{index + 1}": random.random()}
                    metrics.append(metric)
                    run.log_metrics(metric)
            return metrics, run._id
        with concurrent.futures.ThreadPoolExecutor(max_workers=N_RUNS) as executor:
            futures = [executor.submit(thread_func, i) for i in range(N_RUNS)]

            time.sleep(1)

            client = sv_cl.Client()
                
            for i, future in enumerate(concurrent.futures.as_completed(futures)):
                metrics, run_id = future.result()
                assert metrics
                assert client.get_metrics(run_id, f"var_{i + 1}", "step")
                with contextlib.suppress(RuntimeError):
                    client.delete_run(run_id)
    else:
        with sv_run.Run() as run_1:
            with sv_run.Run() as run_2:
                run_1.config(suppress_errors=False)
                run_1.init(
                    name="test_runs_multiple_unthreaded_1",
                    tags=["simvue_client_unit_tests", "test_multi_run_unthreaded"],
                    folder="/simvue_unit_testing"
                )
                run_2.config(suppress_errors=False)
                run_2.init(
                    name="test_runs_multiple_unthreaded_2",
                    tags=["simvue_client_unit_tests", "test_multi_run_unthreaded"],
                    folder="/simvue_unit_testing"
                )
                metrics_1 = []
                metrics_2 = []
                for _ in range(10):
                    time.sleep(1)
                    for index, (metrics, run) in enumerate(zip((metrics_1, metrics_2), (run_1, run_2))):
                        metric = {f"var_{index}": random.random()}
                        metrics.append(metric)
                        run.log_metrics(metric)

                time.sleep(1)

                client = sv_cl.Client()

                for i, run_id in enumerate((run_1._id, run_2._id)):
                    assert metrics
                    assert client.get_metrics(run_id, f"var_{i}", "step")

        with contextlib.suppress(RuntimeError):
            client.delete_run(run_1._id)
            client.delete_run(run_2._id)


@pytest.mark.run
def test_runs_multiple_series() -> None:
    N_RUNS: int = 2

    metrics = []
    run_ids = []

    for index in range(N_RUNS):
        with sv_run.Run() as run:
            run_metrics = []
            run.config(suppress_errors=False)
            run.init(
                name=f"test_runs_multiple_series_{index}",
                tags=["simvue_client_unit_tests", "test_multi_run_series"],
                folder="/simvue_unit_testing"
            )
            run_ids.append(run._id)
            for _ in range(10):
                time.sleep(1)
                metric = {f"var_{index}": random.random()}
                run_metrics.append(metric)
                run.log_metrics(metric)
        metrics.append(run_metrics)

    time.sleep(1)

    client = sv_cl.Client()

    for i, run_id in enumerate(run_ids):
        assert metrics[i]
        assert client.get_metrics(run_id, f"var_{i}", "step")

    with contextlib.suppress(RuntimeError):
        for run_id in run_ids:
            client.delete_run(run_id)
