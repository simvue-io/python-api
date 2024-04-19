import pytest
import time
import typing
import contextlib
import inspect
import uuid
import concurrent.futures
import random

import simvue.run as sv_run
import simvue.client as sv_cl

if typing.TYPE_CHECKING:
    from .conftest import CountingLogHandler


@pytest.mark.run
@pytest.mark.parametrize("overload_buffer", (True, False), ids=("overload", "normal"))
def test_log_metrics(
    overload_buffer: bool,
    setup_logging: "CountingLogHandler",
    mocker,
) -> None:
    METRICS = {"a": 10, "b": 1.2}

    setup_logging.captures = ["'a'", "resources/"]

    # Have to create the run outside of fixtures because the resources dispatch
    # occurs immediately and is not captured by the handler when using the fixture
    run = sv_run.Run()
    run.config(suppress_errors=False)
    run.init(
        name=f"test_run_{str(uuid.uuid4()).split('-', 1)[0]}",
        tags=["simvue_client_unit_tests"],
        folder="/simvue_unit_testing"
    )

    run.update_tags(["simvue_client_unit_tests", "test_log_metrics"])

    # Speed up the read rate for this test
    run._dispatcher._max_buffer_size = 10
    run._dispatcher._max_read_rate *= 10

    if overload_buffer:
        for i in range(run._dispatcher._max_buffer_size * 3):
            run.log_metrics({key: i for key in METRICS.keys()})
    else:
        run.log_metrics(METRICS)
    time.sleep(1.0 if not overload_buffer else 2.0)
    run.close()
    client = sv_cl.Client()
    _data = client.get_metrics_multiple(
        [run._id], list(METRICS.keys()), xaxis="step"
    )

    with contextlib.suppress(RuntimeError):
        client.delete_run(run._id)

    assert len(_data) == (
        len(METRICS)
        if not overload_buffer
        else len(METRICS) * run._dispatcher._max_buffer_size * 3
    )

    # Check metrics have been set
    assert setup_logging.counts[0] == 1 if not overload_buffer else 3

    # Check heartbeat has been called at least once (so sysinfo sent)
    assert setup_logging.counts[1] > 0


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

        def thread_func(index: int) -> tuple[int, list[dict[str, typing.Any]], str]:
            with sv_run.Run() as run:
                run.config(suppress_errors=False)
                run.init(
                    name=f"test_runs_multiple_{index + 1}",
                    tags=["simvue_client_unit_tests", "test_multi_run_threaded"],
                    folder="/simvue_unit_testing",
                )
                metrics = []
                for _ in range(10):
                    time.sleep(1)
                    metric = {f"var_{index + 1}": random.random()}
                    metrics.append(metric)
                    run.log_metrics(metric)
            return index, metrics, run._id

        with concurrent.futures.ThreadPoolExecutor(max_workers=N_RUNS) as executor:
            futures = [executor.submit(thread_func, i) for i in range(N_RUNS)]

            time.sleep(1)

            client = sv_cl.Client()

            for future in concurrent.futures.as_completed(futures):
                id, metrics, run_id = future.result()
                assert metrics
                assert client.get_metrics(run_id, f"var_{id + 1}", "step")
                with contextlib.suppress(RuntimeError):
                    client.delete_run(run_id)
    else:
        with sv_run.Run() as run_1:
            with sv_run.Run() as run_2:
                run_1.config(suppress_errors=False)
                run_1.init(
                    name="test_runs_multiple_unthreaded_1",
                    tags=["simvue_client_unit_tests", "test_multi_run_unthreaded"],
                    folder="/simvue_unit_testing",
                )
                run_2.config(suppress_errors=False)
                run_2.init(
                    name="test_runs_multiple_unthreaded_2",
                    tags=["simvue_client_unit_tests", "test_multi_run_unthreaded"],
                    folder="/simvue_unit_testing",
                )
                metrics_1 = []
                metrics_2 = []
                for _ in range(10):
                    time.sleep(1)
                    for index, (metrics, run) in enumerate(
                        zip((metrics_1, metrics_2), (run_1, run_2))
                    ):
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
                folder="/simvue_unit_testing",
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


@pytest.mark.run
@pytest.mark.parametrize(
    "post_init", (True, False),
    ids=("pre-init", "post-init")
)
def test_suppressed_errors(setup_logging: "CountingLogHandler", post_init: bool) -> None:
    setup_logging.captures = ["Skipping call to"]

    with sv_run.Run(mode="offline") as run:            
        decorated_funcs = [name for name, method in inspect.getmembers(run, inspect.ismethod) if method.__name__.endswith("__fail_safe")]

        if post_init:
            decorated_funcs.remove("init")
            run.init(name="test_suppressed_errors", folder="/simvue_unit_testing", tags=["simvue_client_unit_tests"])

        run.config(suppress_errors=True)
        run._error("Oh dear this error happened :(")
        if run._dispatcher:
            assert run._dispatcher.empty
        for func in decorated_funcs:
            assert not getattr(run, func)()
    if post_init:
        assert setup_logging.counts[0] == len(decorated_funcs) + 1
    else:
        assert setup_logging.counts[0] == len(decorated_funcs)
    