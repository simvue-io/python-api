import json
import logging
import platform
import os
import numpy
import pytest
import requests
import pytest_mock
import time
import typing
import contextlib
import inspect
import tempfile
import threading
import uuid
import psutil
import pathlib
import concurrent.futures
import random
import datetime
import simvue
from simvue.api.objects import Alert, Metrics
from simvue.api.objects.grids import GridMetrics
from simvue.eco.api_client import CO2SignalData, CO2SignalResponse
from simvue.exception import ObjectNotFoundError, SimvueRunError
from simvue.eco.emissions_monitor import TIME_FORMAT, CO2Monitor
from simvue.sender import Sender
import simvue.run as sv_run
import simvue.client as sv_cl
import simvue.config.user as sv_cfg

from simvue.api.objects import Run as RunObject

if typing.TYPE_CHECKING:
    from .conftest import CountingLogHandler


@pytest.mark.run
def test_created_run(request) -> None:
    _uuid = f"{uuid.uuid4()}".split("-")[0]
    with sv_run.Run() as run_created:
        run_created.init(
            request.node.name.replace("[", "_").replace("]", "_"),
            tags=[platform.system(), 
                "simvue_client_unit_tests",
                "test_created_run"
            ],
            folder=f"/simvue_unit_testing/{_uuid}",
            running=False,
            visibility="tenant" if os.environ.get("CI") else None,
            retention_period=os.environ.get("SIMVUE_TESTING_RETENTION_PERIOD", "2 mins"),
        )
        _run = RunObject(identifier=run_created.id)
        assert _run.status == "created"
    with contextlib.suppress(ObjectNotFoundError):
        client = sv_cl.Client()
        client.delete_folder(
            f"/simvue_unit_testing/{uuid}",
            remove_runs=True,
            recursive=True
        )


@pytest.mark.run
def test_check_run_initialised_decorator() -> None:
    with sv_run.Run(mode="offline") as run:
        for method_name, method in inspect.getmembers(run, inspect.ismethod):
            if not method.__name__.endswith("init_locked"):
                continue
            with pytest.raises(RuntimeError) as e:
                getattr(run, method_name)()
            assert "Simvue Run must be initialised" in str(e.value)


@pytest.mark.run
@pytest.mark.eco
@pytest.mark.online
def test_run_with_emissions_online(speedy_heartbeat, mock_co2_signal, create_plain_run: tuple[sv_run.Run, ...], mocker) -> None:
    run_created, _ = create_plain_run
    metric_interval = 1
    run_created._user_config.eco.co2_signal_api_token = "test_token"
    run_created.config(enable_emission_metrics=True, system_metrics_interval=metric_interval)
    while (
        "sustainability.emissions.total" not in requests.get(
            url=f"{run_created._user_config.server.url}/metrics/names",
            headers=run_created._headers,
            params={"runs": json.dumps([run_created.id])}).json()
        and run_created.metric_spy.call_count < 4
    ):
        time.sleep(metric_interval)
    _run = RunObject(identifier=run_created.id)
    _metric_names = [item[0] for item in _run.metrics]
    client = sv_cl.Client()
    for _metric in ["emissions", "energy_consumed"]:
        _total_metric_name = f"sustainability.{_metric}.total"
        _delta_metric_name = f"sustainability.{_metric}.delta"
        assert _total_metric_name in _metric_names
        assert _delta_metric_name in _metric_names
        _metric_values = client.get_metric_values(
            metric_names=[_total_metric_name, _delta_metric_name],
            xaxis="time",
            output_format="dataframe",
            run_ids=[run_created.id],
        )
        # Check that total = previous total + latest delta
        _total_values = _metric_values[_total_metric_name].tolist()
        _delta_values = _metric_values[_delta_metric_name].tolist()
        for i in range(1, len(_total_values)):
            assert _total_values[i] == _total_values[i - 1] + _delta_values[i]

@pytest.mark.run
@pytest.mark.eco
@pytest.mark.offline
def test_run_with_emissions_offline(speedy_heartbeat, mock_co2_signal, create_plain_run_offline, monkeypatch) -> None:
    run_created, _ = create_plain_run_offline
    run_created.config(enable_emission_metrics=True)
    time.sleep(5)
    # Run should continue, but fail to log metrics until sender runs and creates file
    _sender = Sender(cache_directory=os.environ["SIMVUE_OFFLINE_DIRECTORY"], throw_exceptions=True)
    _sender.upload()
    id_mapping = _sender.id_mapping
    _run = RunObject(identifier=id_mapping[run_created.id])
    _metric_names = [item[0] for item in _run.metrics]
    for _metric in ["emissions", "energy_consumed"]:
        _total_metric_name = f"sustainability.{_metric}.total"
        _delta_metric_name = f"sustainability.{_metric}.delta"
        assert _total_metric_name not in _metric_names
        assert _delta_metric_name not in _metric_names
    # Sender should now have made a local file, and the run should be able to use it to create emissions metrics
    time.sleep(5)
    _sender = Sender(cache_directory=os.environ["SIMVUE_OFFLINE_DIRECTORY"], throw_exceptions=True)
    _sender.upload()
    id_mapping = _sender.id_mapping
    _run.refresh()
    _metric_names = [item[0] for item in _run.metrics]
    client = sv_cl.Client()
    for _metric in ["emissions", "energy_consumed"]:
        _total_metric_name = f"sustainability.{_metric}.total"
        _delta_metric_name = f"sustainability.{_metric}.delta"
        assert _total_metric_name in _metric_names
        assert _delta_metric_name in _metric_names
        _metric_values = client.get_metric_values(
            metric_names=[_total_metric_name, _delta_metric_name],
                xaxis="time",
            output_format="dataframe",
            run_ids=[id_mapping[run_created.id]],
        )
        # Check that total = previous total + latest delta
        _total_values = _metric_values[_total_metric_name].tolist()
        _delta_values = _metric_values[_delta_metric_name].tolist()
        assert len(_total_values) > 1
        for i in range(1, len(_total_values)):
            assert _total_values[i] == _total_values[i - 1] + _delta_values[i]

@pytest.mark.run
@pytest.mark.parametrize(
    "timestamp",
    (datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f"), None),
    ids=("timestamp", "no_timestamp"),
)
@pytest.mark.parametrize("overload_buffer", (True, False), ids=("overload", "normal"))
@pytest.mark.parametrize(
    "visibility", ("bad_option", "tenant", "public", ["user01"], None)
)
@pytest.mark.parametrize("metric_type", ("regular", "tensor"))
def test_log_metrics_online(
    overload_buffer: bool,
    timestamp: str | None,
    mocker: pytest_mock.MockerFixture,
    request: pytest.FixtureRequest,
    visibility: typing.Literal["public", "tenant"] | list[str] | None,
    metric_type: typing.Literal["regular", "tensor"],
) -> None:
    METRICS = {"a": 10, "aB0-_/.:=><+()": 1.2}

    # Have to create the run outside of fixtures because the resources dispatch
    # occurs immediately and is not captured by the handler when using the fixture
    run = sv_run.Run()
    run.config(suppress_errors=False)


    if metric_type == "tensor":
        metrics_spy = mocker.spy(GridMetrics, "new")
    else:
        metrics_spy = mocker.spy(Metrics, "new")
    system_metrics_spy = mocker.spy(sv_run.Run, "_get_internal_metrics")
    unique_id = f"{uuid.uuid4()}".split("-")[0]

    if visibility == "bad_option":
        with pytest.raises(SimvueRunError, match="visibility") as e:
            run.init(
                request.node.name.replace("[", "_").replace("]", "_"),
                tags=[platform.system(), 
                    "simvue_client_unit_tests",
                    "test_log_metrics",
                ],
                folder=f"/simvue_unit_testing/{unique_id}",
                retention_period=os.environ.get("SIMVUE_TESTING_RETENTION_PERIOD", "2 mins"),
                visibility=visibility,
            )
            # Will log system metrics on startup, and then not again within timeframe of test
            # So should have exactly one measurement of this
            run.config(system_metrics_interval=100)
        return

    run.init(
        request.node.name.replace("[", "_").replace("]", "_"),
        tags=[platform.system(), 
            "simvue_client_unit_tests",
            "test_log_metrics",
        ],
        folder=f"/simvue_unit_testing/{unique_id}",
        visibility=visibility,
        retention_period=os.environ.get("SIMVUE_TESTING_RETENTION_PERIOD", "2 mins"),
    )
    if metric_type == "tensor":
        METRICS = {"c": numpy.identity(10), "g": numpy.ones((10, 10)) + 3 * numpy.identity(10)}
        run.assign_metric_to_grid(
            metric_name="c",
            grid_name="test_log_metrics",
            axes_ticks=numpy.vstack([
                numpy.linspace(0, 10, 10),
                numpy.linspace(0, 20, 10),
            ]),
            axes_labels=["x", "y"]
        )
    # Will log system metrics on startup, and then not again within timeframe of test
    # So should have exactly one measurement of this
    run.config(system_metrics_interval=100)
    # Speed up the read rate for this test
    run._dispatcher._max_buffer_size = 10
    run._dispatcher._max_read_rate *= 10

    if overload_buffer:
        for i in range(run._dispatcher._max_buffer_size * 3):
            _value = i * numpy.identity(10) if metric_type == "tensor" else i
            run.log_metrics({key: _value for key in METRICS}, timestamp=timestamp)
    else:
        run.log_metrics(METRICS, timestamp=timestamp)
    run.close()

    #TODO: No client functions defined for grids yet
    # Temporary solution - use direct API endpoints
    if metric_type == "tensor":
        for name, values in METRICS.items():
            if overload_buffer:
                for i in range(run._dispatcher._max_buffer_size * 3):
                    response = requests.get(
                        url=f"{run._user_config.server.url}/runs/{run.id}/metrics/{name}/values?step={i}",
                        headers=run._sv_obj._headers,
                    )
                    assert response.status_code == 200            
                    numpy.testing.assert_almost_equal(numpy.array(response.json().get("array")), i * numpy.identity(10))
            else:
                response = requests.get(
                    url=f"{run._user_config.server.url}/runs/{run.id}/metrics/{name}/values?step=0",
                    headers=run._sv_obj._headers,
                )
                assert response.status_code == 200            
                numpy.testing.assert_almost_equal(numpy.array(response.json().get("array")), values)
    else:    
        time.sleep(2.0 if overload_buffer else 1.0)
        client = sv_cl.Client()
        _data = client.get_metric_values(
            run_ids=[run.id],
            metric_names=list(METRICS.keys()),
            xaxis="step",
            aggregate=False,
        )

        with contextlib.suppress(ObjectNotFoundError):
            client.delete_folder(
                f"/simvue_unit_testing/{unique_id}",
                recursive=True,
                remove_runs=True
            )

        assert _data

        assert sorted(set(METRICS.keys())) == sorted(set(_data.keys()))
        _steps = []
        for entry in _data.values():
            _steps += [i[0] for i in entry.keys()]
        _steps = set(_steps)

        assert len(_steps) == (
            run._dispatcher._max_buffer_size * 3 if overload_buffer else 1
        )

    if overload_buffer:
        assert metrics_spy.call_count > 2
    else:
        assert metrics_spy.call_count <= 2

    # Check heartbeat has been called at least once (so sysinfo sent)
    assert system_metrics_spy.call_count >= 1


@pytest.mark.run
@pytest.mark.offline
@pytest.mark.parametrize("metric_type", ("regular", "tensor"))
def test_log_metrics_offline(
    create_plain_run_offline: tuple[sv_run.Run, dict],
    metric_type: typing.Literal["regular", "tensor"]
) -> None:
    run, _ = create_plain_run_offline
    run_name = run.name
    if metric_type == "tensor":
        METRICS = {"c": numpy.identity(10), "g": numpy.ones((10, 10)) + 3 * numpy.identity(10)}
        run.assign_metric_to_grid(
            metric_name="c",
            grid_name="test_log_metrics",
            axes_ticks=numpy.vstack([
                numpy.linspace(0, 10, 10),
                numpy.linspace(0, 20, 10),
            ]),
            axes_labels=["x", "y"]
        )
    else:
        METRICS = {"a": 10, "aB0-_/.:=><+()": 1.2, "c": 2}
        
    run.log_metrics(METRICS)
    
    time.sleep(1)
    _sender = Sender(cache_directory=os.environ["SIMVUE_OFFLINE_DIRECTORY"], throw_exceptions=True)
    _sender.upload()
    id_mapping = _sender.id_mapping
    time.sleep(1)
    
    if metric_type == "tensor":
        for name, values in METRICS.items():
            response = requests.get(
                url=f"{run._user_config.server.url}/runs/{id_mapping[run.id]}/metrics/{name}/values?step=0",
                headers={
                    "Authorization": f"Bearer {run._user_config.server.token.get_secret_value()}",
                    "User-Agent": "Simvue Python client",
                    "Accept-Encoding": "gzip",
                }
            )
            assert response.status_code == 200
            numpy.testing.assert_almost_equal(numpy.array(response.json().get("array")), values)
    else:
        client = sv_cl.Client()

        _data = client.get_metric_values(
            run_ids=[client.get_run_id_from_name(run_name)],
            metric_names=list(METRICS.keys()),
            xaxis="step",
            aggregate=False,
        )

        assert sorted(set(METRICS.keys())) == sorted(set(_data.keys()))
        _steps = []
        for entry in _data.values():
            _steps += [i[0] for i in entry.keys()]
        _steps = set(_steps)
        assert len(_steps) == 1

@pytest.mark.run
@pytest.mark.parametrize(
    "visibility", ("bad_option", "tenant", "public", ["user01"], None)
)
def test_visibility_online(
    request: pytest.FixtureRequest,
    visibility: typing.Literal["public", "tenant"] | list[str] | None,
) -> None:

    run = sv_run.Run()
    run.config(suppress_errors=False)
    _uuid = f"{uuid.uuid4()}".split("-")[0]

    if visibility == "bad_option":
        with pytest.raises(SimvueRunError, match="visibility") as e:
            run.init(
                request.node.name.replace("[", "_").replace("]", "_"),
                tags=[platform.system(), 
                    "simvue_client_unit_tests",
                    "test_visibility_online"
                ],
                folder=f"/simvue_unit_testing/{_uuid}",
                retention_period=os.environ.get("SIMVUE_TESTING_RETENTION_PERIOD", "2 mins"),
                visibility=visibility,
            )
        return

    run.init(
        request.node.name.replace("[", "_").replace("]", "_"),
        tags=[platform.system(), 
            "simvue_client_unit_tests",
            "test_visibility_online"
        ],
        folder=f"/simvue_unit_testing/{_uuid}",
        visibility=visibility,
        retention_period=os.environ.get("SIMVUE_TESTING_RETENTION_PERIOD", "2 mins"),
    )
    _id = run.id
    run.close()
    _retrieved_run = RunObject(identifier=_id)

    if visibility == "tenant":
        assert _retrieved_run.visibility.tenant
    elif visibility == "public":
        assert _retrieved_run.visibility.public
    elif not visibility:
        assert not _retrieved_run.visibility.tenant and not _retrieved_run.visibility.public
    else:
        assert _retrieved_run.visibility.users == visibility
    
@pytest.mark.run
@pytest.mark.offline
@pytest.mark.parametrize(
    "visibility", ("bad_option", "tenant", "public", ["user01"], None)
)
def test_visibility_offline(
    request: pytest.FixtureRequest,
    monkeypatch,
    visibility: typing.Literal["public", "tenant"] | list[str] | None,
) -> None:
    _uuid = f"{uuid.uuid4()}".split("-")[0]
    with tempfile.TemporaryDirectory() as tempd:
        os.environ["SIMVUE_OFFLINE_DIRECTORY"] = tempd
        run = sv_run.Run(mode="offline")
        run.config(suppress_errors=False)

        if visibility == "bad_option":
            with pytest.raises(SimvueRunError, match="visibility") as e:
                run.init(
                    request.node.name.replace("[", "_").replace("]", "_"),
                    tags=[platform.system(), 
                        "simvue_client_unit_tests",
                        "test_visibility_offline"
                    ],
                    folder=f"/simvue_unit_testing/{_uuid}",
                    retention_period=os.environ.get("SIMVUE_TESTING_RETENTION_PERIOD", "2 mins"),
                    visibility=visibility,
                )
            return

        run.init(
            request.node.name.replace("[", "_").replace("]", "_"),
            tags=[platform.system(), 
               "simvue_client_unit_tests",
               "test_visibility_offline"
            ],
            folder=f"/simvue_unit_testing/{_uuid}",
            visibility=visibility,
            retention_period=os.environ.get("SIMVUE_TESTING_RETENTION_PERIOD", "2 mins"),
        )
        _id = run.id
        _sender = Sender(cache_directory=os.environ["SIMVUE_OFFLINE_DIRECTORY"], throw_exceptions=True)
        _sender.upload()
        id_mapping = _sender.id_mapping
        run.close()
        _retrieved_run = RunObject(identifier=id_mapping.get(_id))

        if visibility == "tenant":
            assert _retrieved_run.visibility.tenant
        elif visibility == "public":
            assert _retrieved_run.visibility.public
        elif not visibility:
            assert not _retrieved_run.visibility.tenant and not _retrieved_run.visibility.public
        else:
            assert _retrieved_run.visibility.users == visibility
        with contextlib.suppress(ObjectNotFoundError):
            client = sv_cl.Client()
            client.delete_folder(
                f"/simvue_unit_testing/{_uuid}",
                recursive=True,
                remove_runs=True
            )

@pytest.mark.run
def test_log_events_online(create_test_run: tuple[sv_run.Run, dict]) -> None:
    EVENT_MSG = "Hello world!"
    run, _ = create_test_run
    run.log_event(EVENT_MSG)
    client = sv_cl.Client()
    event_data = client.get_events(run.id, count_limit=1)
    assert event_data[0].get("message", EVENT_MSG)


@pytest.mark.run
@pytest.mark.offline
def test_log_events_offline(create_plain_run_offline: tuple[sv_run.Run, dict]) -> None:
    EVENT_MSG = "Hello offline world!"
    run, _ = create_plain_run_offline
    run_name = run.name
    run.log_event(EVENT_MSG)
    _sender = Sender(cache_directory=os.environ["SIMVUE_OFFLINE_DIRECTORY"], throw_exceptions=True)
    _sender.upload()
    client = sv_cl.Client()
    attempts: int = 0

    # Because the time taken may vary between systems allow up to five attempts
    # at an interval of 1 second
    while (
        not (event_data := client.get_events(client.get_run_id_from_name(run_name), count_limit=1))
    ) and attempts < 5:
        time.sleep(1)
        _sender = Sender(cache_directory=os.environ["SIMVUE_OFFLINE_DIRECTORY"], max_workers=2, threading_threshold=10, throw_exceptions=True)
        _sender.upload()
        attempts += 1
    assert event_data[0].get("message", EVENT_MSG)


@pytest.mark.run
@pytest.mark.offline
def test_offline_tags(create_plain_run_offline: tuple[sv_run.Run, dict]) -> None:
    _, run_data = create_plain_run_offline
    _sender = Sender(cache_directory=os.environ["SIMVUE_OFFLINE_DIRECTORY"], max_workers=2, threading_threshold=10, throw_exceptions=True)
    _sender.upload()
    client = sv_cl.Client()

    tags = client.get_tags()

    # Find tag
    run_tags = [tag for tag in tags if tag[1].name == run_data["tags"][-1]]
    assert len(run_tags) == 1
    client.delete_tag(run_tags[0][0])


@pytest.mark.run
def test_update_metadata_running(create_test_run: tuple[sv_run.Run, dict]) -> None:
    METADATA = {"a": 1, "b": 1.2, "c": "word", "d": "new"}
    run, _ = create_test_run
    # Add an initial set of metadata
    run.update_metadata({"a": 10, "b": 1.2, "c": "word"})
    # Try updating a second time, check original dict isnt overwritten
    run.update_metadata({"d": "new"})
    # Try updating an already defined piece of metadata
    run.update_metadata({"a": 1})
    client = sv_cl.Client()
    run_info = client.get_run(run.id)

    for key, value in METADATA.items():
        assert run_info.metadata.get(key) == value


@pytest.mark.run
def test_update_metadata_created(create_pending_run: tuple[sv_run.Run, dict]) -> None:
    METADATA = {"a": 1, "b": 1.2, "c": "word", "d": "new"}
    run, _ = create_pending_run
    # Add an initial set of metadata
    run.update_metadata({"a": 10, "b": 1.2, "c": "word"})
    # Try updating a second time, check original dict isnt overwritten
    run.update_metadata({"d": "new"})
    # Try updating an already defined piece of metadata
    run.update_metadata({"a": 1})
    client = sv_cl.Client()
    run_info = client.get_run(run.id)

    for key, value in METADATA.items():
        assert run_info.metadata.get(key) == value


@pytest.mark.run
@pytest.mark.offline
def test_update_metadata_offline(
    create_plain_run_offline: tuple[sv_run.Run, dict],
) -> None:
    METADATA = {"a": 1, "b": 1.2, "c": "word", "d": "new"}
    run, _ = create_plain_run_offline
    run_name = run.name
    # Add an initial set of metadata
    run.update_metadata({"a": 10, "b": 1.2, "c": "word"})
    # Try updating a second time, check original dict isnt overwritten
    run.update_metadata({"d": "new"})
    # Try updating an already defined piece of metadata
    run.update_metadata({"a": 1})

    _sender = Sender(cache_directory=os.environ["SIMVUE_OFFLINE_DIRECTORY"], max_workers=2, threading_threshold=10, throw_exceptions=True)
    _sender.upload()

    client = sv_cl.Client()
    run_info = client.get_run(client.get_run_id_from_name(run_name))

    for key, value in METADATA.items():
        assert run_info.metadata.get(key) == value


@pytest.mark.run
@pytest.mark.scenario
@pytest.mark.parametrize("multi_threaded", (True, False), ids=("multi", "single"))
def test_runs_multiple_parallel(
    multi_threaded: bool, request: pytest.FixtureRequest
) -> None:
    N_RUNS: int = 2
    _uuid = f"{uuid.uuid4()}".split("-")[0]
    if multi_threaded:

        def thread_func(index: int) -> tuple[int, list[dict[str, typing.Any]], str]:
            with sv_run.Run() as run:
                run.config(suppress_errors=False)
                run.init(
                    request.node.name.replace("[", "_").replace("]", "_") + f"_{index}",
                    tags=[platform.system(), 
                        "simvue_client_unit_tests",
                    ],
                    folder=f"/simvue_client_unit_tests/{_uuid}",
                    retention_period=os.environ.get("SIMVUE_TESTING_RETENTION_PERIOD", "2 mins"),
                    visibility="tenant" if os.environ.get("CI") else None,
                )
                metrics = []
                for _ in range(10):
                    time.sleep(1)
                    metric = {f"var_{index + 1}": random.random()}
                    metrics.append(metric)
                    run.log_metrics(metric)
            return index, metrics, run.id

        with concurrent.futures.ThreadPoolExecutor(max_workers=N_RUNS, thread_name_prefix="test_runs_multiple_parallel") as executor:
            futures = [executor.submit(thread_func, i) for i in range(N_RUNS)]

            client = sv_cl.Client()

            for future in concurrent.futures.as_completed(futures):
                id, metrics, run_id = future.result()
                assert metrics
                assert client.get_metric_values(
                    run_ids=[run_id],
                    metric_names=[f"var_{id + 1}"],
                    xaxis="step",
                    output_format="dict",
                    aggregate=False,
                )
                with contextlib.suppress(RuntimeError):
                    client.delete_run(run_id)
    else:
        with sv_run.Run() as run_1:
            with sv_run.Run() as run_2:
                run_1.config(suppress_errors=False)
                run_1.init(
                    request.node.name.replace("[", "_").replace("]", "_") + "_1",
                    tags=[platform.system(), 
                        "simvue_client_unit_tests",
                        "test_multi_run_unthreaded"
                    ],
                    folder=f"/simvue_client_unit_tests/{_uuid}",
                    retention_period=os.environ.get("SIMVUE_TESTING_RETENTION_PERIOD", "2 mins"),
                    visibility="tenant" if os.environ.get("CI") else None,
                )
                run_2.config(suppress_errors=False)
                run_2.init(
                    request.node.name.replace("[", "_").replace("]", "_") + "_2",
                    tags=[platform.system(), "simvue_client_unit_tests", "test_multi_run_unthreaded"],
                    folder=f"/simvue_client_unit_tests/{_uuid}",
                    retention_period=os.environ.get("SIMVUE_TESTING_RETENTION_PERIOD", "2 mins"),
                    visibility="tenant" if os.environ.get("CI") else None,
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


                client = sv_cl.Client()

                for i, run_id in enumerate((run_1.id, run_2.id)):
                    assert metrics
                    assert client.get_metric_values(
                        run_ids=[run_id],
                        metric_names=[f"var_{i}"],
                        xaxis="step",
                        output_format="dict",
                        aggregate=False,
                    )

        with contextlib.suppress(ObjectNotFoundError):
            client.delete_folder(
                f"/simvue_unit_testing/{_uuid}",
                remove_runs=True,
                recursive=True
            )


@pytest.mark.run
@pytest.mark.scenario
def test_runs_multiple_series(request: pytest.FixtureRequest) -> None:
    N_RUNS: int = 2

    metrics = []
    run_ids = []
    _uuid = f"{uuid.uuid4()}".split("-")[0]

    for index in range(N_RUNS):
        with sv_run.Run() as run:
            run_metrics = []
            run.config(suppress_errors=False)
            run.init(
                request.node.name.replace("[", "_").replace("]", "_"),
                tags=[platform.system(), 
                    "simvue_client_unit_tests",
                    "test_runs_multiple_series"
                ],
                folder=f"/simvue_unit_testing/{_uuid}",
                retention_period=os.environ.get("SIMVUE_TESTING_RETENTION_PERIOD", "2 mins"),
                visibility="tenant" if os.environ.get("CI") else None,
            )
            run_ids.append(run.id)
            for _ in range(10):
                time.sleep(1)
                metric = {f"var_{index}": random.random()}
                run_metrics.append(metric)
                run.log_metrics(metric)
        metrics.append(run_metrics)

    client = sv_cl.Client()

    for i, run_id in enumerate(run_ids):
        assert metrics[i]
        assert client.get_metric_values(
            run_ids=[run_id],
            metric_names=[f"var_{i}"],
            xaxis="step",
            output_format="dict",
            aggregate=False,
        )

    with contextlib.suppress(ObjectNotFoundError):
        client.delete_folder(
            f"/simvue_unit_testing/{_uuid}",
            recursive=True,
            remove_runs=True
        )


@pytest.mark.run
@pytest.mark.parametrize("post_init", (True, False), ids=("pre-init", "post-init"))
def test_suppressed_errors(
    setup_logging: "CountingLogHandler", post_init: bool, request: pytest.FixtureRequest
) -> None:
    logging.getLogger("simvue").setLevel(logging.DEBUG)
    setup_logging.captures = ["Skipping call to"]
    _uuid = f"{uuid.uuid4()}".split("-")[0]

    with sv_run.Run(mode="offline") as run:
        decorated_funcs = [
            name
            for name, method in inspect.getmembers(run, inspect.ismethod)
            if hasattr(method, "__fail_safe")
        ]

        if post_init:
            decorated_funcs.remove("init")
            run.init(
                request.node.name.replace("[", "_").replace("]", "_"),
                folder=f"/simvue_unit_testing/{_uuid}",
                tags=[platform.system(), 
                    "simvue_client_unit_tests",
                    "test_suppressed_errors"
                ],
                retention_period=os.environ.get("SIMVUE_TESTING_RETENTION_PERIOD", "2 mins"),
                visibility="tenant" if os.environ.get("CI") else None,
            )

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

    with contextlib.suppress(ObjectNotFoundError):
        client = sv_cl.Client()
        client.delete_folder(
            f"/simvue_unit_testing/{_uuid}",
            recursive=True,
            remove_runs=True
        )


@pytest.mark.run
def test_bad_run_arguments() -> None:
    with sv_run.Run() as run:
        with pytest.raises(RuntimeError):
            run.init("sdas", [34])


@pytest.mark.run
def test_set_folder_details(request: pytest.FixtureRequest) -> None:
    _uuid = f"{uuid.uuid4()}".split("-")[0]
    with sv_run.Run() as run:
        folder_name: str = f"/simvue_unit_testing/{_uuid}"
        description: str = "test description"
        tags: list[str] = [
            "simvue_client_unit_tests",
            "test_set_folder_details"
        ]
        run.init(
            request.node.name.replace("[", "_").replace("]", "_"),
            folder=folder_name,
            visibility="tenant" if os.environ.get("CI") else None,
            retention_period=os.environ.get("SIMVUE_TESTING_RETENTION_PERIOD", "2 mins"),
        )
        run.set_folder_details(tags=tags, description=description)

    client = sv_cl.Client()
    _folder = client.get_folder(folder_path=folder_name)

    assert _folder.tags
    assert sorted(_folder.tags) == sorted(tags)

    assert _folder.description == description

    with contextlib.suppress(ObjectNotFoundError):
        client.delete_folder(
            f"/simvue_unit_testing/{_uuid}",
            remove_runs=True,
            recursive=True
        )


@pytest.mark.run
@pytest.mark.parametrize(
    "snapshot", (True, False)
)
@pytest.mark.parametrize(
    "valid_mimetype,preserve_path,name,allow_pickle,empty_file,category",
    [
        (True, False, None, False, False, "input"),
        (False, True, None, False, False, "output"),
        (False, False, "test_file", False, False, "code"),
        (False, False, None, True, False, "input"),
        (False, False, None, False, True, "code"),
    ],
    ids=[f"scenario_{i}" for i in range(1, 6)],
)
def test_save_file_online(
    valid_mimetype: bool,
    preserve_path: bool,
    name: str | None,
    allow_pickle: bool,
    empty_file: bool,
    category: typing.Literal["input", "output", "code"],
    snapshot: bool,
    capfd,
    request,
) -> None:
    _uuid = f"{uuid.uuid4()}".split("-")[0]
    file_type: str = "text/plain" if valid_mimetype else "text/text"
    with tempfile.TemporaryDirectory() as tempd:
        with open(
            (out_name := pathlib.Path(tempd).joinpath("test_file.txt")),
            "w",
        ) as out_f:
            out_f.write("" if empty_file else "test data entry")
        with sv_run.Run() as simvue_run:
            folder_name: str = f"/simvue_unit_testing/{_uuid}"
            tags: list[str] = [
                "simvue_client_unit_tests",
                "test_save_file_online"
            ]
            simvue_run.init(
                request.node.name.replace("[", "_").replace("]", "_"),
                folder=folder_name,
                tags=tags,
                visibility="tenant" if os.environ.get("CI") else None,
                retention_period=os.environ.get("SIMVUE_TESTING_RETENTION_PERIOD", "2 mins"),
            )


            if valid_mimetype:
                simvue_run.save_file(
                    out_name,
                    category=category,
                    file_type=file_type,
                    preserve_path=preserve_path,
                    name=name,
                    snapshot=snapshot
                )
            else:
                with pytest.raises(RuntimeError):
                    simvue_run.save_file(
                        out_name,
                        category=category,
                        file_type=file_type,
                        preserve_path=preserve_path,
                    )
                return

            variable = capfd.readouterr()
        time.sleep(1.0)
        os.remove(out_name)
        client = sv_cl.Client()
        base_name = name or out_name.name
        if preserve_path:
            out_loc = pathlib.Path(tempd) / out_name.parent
            stored_name = out_name.parent / pathlib.Path(base_name)
        else:
            out_loc = pathlib.Path(tempd)
            stored_name = pathlib.Path(base_name)
        out_file = out_loc.joinpath(name or out_name.name)
        client.get_artifact_as_file(
            run_id=simvue_run.id, name=f"{name or stored_name}", output_dir=tempd
        )
        assert out_loc.joinpath(name or out_name.name).exists()


@pytest.mark.run
@pytest.mark.offline
@pytest.mark.parametrize(
    "snapshot", (True, False)
)
@pytest.mark.parametrize(
    "preserve_path,name,allow_pickle,empty_file,category",
    [
        (False, None, False, False, "input"),
        (True, None, False, False, "output"),
        (False, "test_file", False, False, "code"),
        (False, None, True, False, "input"),
        (False, None, False, True, "code"),
    ],
    ids=[f"scenario_{i}" for i in range(1, 6)],
)
def test_save_file_offline(
    create_plain_run_offline: tuple[sv_run.Run, dict],
    preserve_path: bool,
    name: str | None,
    allow_pickle: bool,
    empty_file: bool,
    snapshot: bool,
    category: typing.Literal["input", "output", "code"],
    capfd,
) -> None:
    simvue_run, _ = create_plain_run_offline
    run_name = simvue_run.name
    file_type: str = "text/plain"
    with tempfile.TemporaryDirectory() as tempd:
        with open(
            (out_name := pathlib.Path(tempd).joinpath("test_file.txt")),
            "w",
        ) as out_f:
            out_f.write("test data entry")

        simvue_run.save_file(
            out_name,
            category=category,
            file_type=file_type,
            preserve_path=preserve_path,
            name=name,
            snapshot=snapshot
        )
        # if snapshotting, check file can be updated, but previous contents set
        if snapshot:
            with open(
                (out_name := pathlib.Path(tempd).joinpath("test_file.txt")),
                "w",
            ) as out_f:
                out_f.write("updated file!")
        _sender = Sender(cache_directory=os.environ["SIMVUE_OFFLINE_DIRECTORY"], max_workers=2, threading_threshold=10, throw_exceptions=True)
        _sender.upload()
        os.remove(out_name)
        client = sv_cl.Client()
        base_name = name or out_name.name
        if preserve_path:
            out_loc = pathlib.Path(tempd) / out_name.parent
            stored_name = out_name.parent / pathlib.Path(base_name)
        else:
            out_loc = pathlib.Path(tempd)
            stored_name = pathlib.Path(base_name)
        out_file = out_loc.joinpath(name or out_name.name)
        client.get_artifact_as_file(
            run_id=client.get_run_id_from_name(run_name),
            name=f"{name or stored_name}",
            output_dir=tempd,
        )
        assert out_file.exists()
        with open(
            out_file, "r") as out_f:
            content = out_f.read()
        assert content == "test data entry"

@pytest.mark.run
def test_update_tags_running(
    create_plain_run: tuple[sv_run.Run, dict],
    request: pytest.FixtureRequest,
) -> None:
    simvue_run, _ = create_plain_run

    tags = [
        "simvue_client_unit_tests",
        request.node.name.replace("[", "_").replace("]", "_"),
    ]

    simvue_run.set_tags(tags)

    client = sv_cl.Client()
    run_data = client.get_run(simvue_run.id)
    assert sorted(run_data.tags) == sorted(tags)

    simvue_run.update_tags(["additional"])

    run_data = client.get_run(simvue_run.id)
    assert sorted(run_data.tags) == sorted(tags + ["additional"])


@pytest.mark.run
def test_update_tags_created(
    create_pending_run: tuple[sv_run.Run, dict],
    request: pytest.FixtureRequest,
) -> None:
    simvue_run, _ = create_pending_run

    tags = [
        "simvue_client_unit_tests",
        request.node.name.replace("[", "_").replace("]", "_"),
    ]

    simvue_run.set_tags(tags)

    client = sv_cl.Client()
    run_data = client.get_run(simvue_run.id)
    assert sorted(run_data.tags) == sorted(tags)

    simvue_run.update_tags(["additional"])

    run_data = client.get_run(simvue_run.id)
    assert sorted(run_data.tags) == sorted(tags + ["additional"])


@pytest.mark.offline
@pytest.mark.run
def test_update_tags_offline(
    create_plain_run_offline: tuple[sv_run.Run, dict],
) -> None:
    simvue_run, _ = create_plain_run_offline
    run_name = simvue_run.name

    simvue_run.set_tags(
        [
            "simvue_client_unit_tests",
        ]
    )

    simvue_run.update_tags(["additional"])

    _sender = Sender(cache_directory=os.environ["SIMVUE_OFFLINE_DIRECTORY"], max_workers=2, threading_threshold=10, throw_exceptions=True)
    _sender.upload()

    client = sv_cl.Client()
    run_data = client.get_run(client.get_run_id_from_name(run_name))

    assert sorted(run_data.tags) == sorted(["simvue_client_unit_tests", "additional"])


@pytest.mark.run
@pytest.mark.parametrize("object_type", ("DataFrame", "ndarray"))
def test_save_object(
    create_plain_run: tuple[sv_run.Run, dict], object_type: str
) -> None:
    simvue_run, _ = create_plain_run

    if object_type == "DataFrame":
        try:
            from pandas import DataFrame
        except ImportError:
            pytest.skip("Pandas is not installed")
        save_obj = DataFrame({"x": [1, 2, 3, 4], "y": [2, 4, 6, 8]})
    elif object_type == "ndarray":
        try:
            from numpy import array
        except ImportError:
            pytest.skip("Numpy is not installed")
        save_obj = array([1, 2, 3, 4])
    simvue_run.save_object(save_obj, "input", f"test_object_{object_type}")


@pytest.mark.run
def test_add_alerts() -> None:
    _uuid = f"{uuid.uuid4()}".split("-")[0]

    run = sv_run.Run()
    run.init(
        name="test_add_alerts",
        folder=f"/simvue_unit_testing/{_uuid}",
        retention_period=os.environ.get("SIMVUE_TESTING_RETENTION_PERIOD", "2 mins"),
        tags=[platform.system(), "test_add_alerts"],
        visibility="tenant" if os.environ.get("CI") else None,
    )

    _expected_alerts = []

    # Create alerts, have them attach to run automatically
    _id = run.create_event_alert(
        name=f"event_alert_{_uuid}",
        pattern="test",
    )
    _expected_alerts.append(_id)
    time.sleep(1)
    # Retrieve run, check if alert has been added
    _online_run = RunObject(identifier=run.id)
    assert _id in _online_run.alerts

    # Create another alert and attach to run
    _id = run.create_metric_range_alert(
        name=f"metric_range_alert_{_uuid}",
        metric="test",
        range_low=10,
        range_high=100,
        rule="is inside range",
    )
    _expected_alerts.append(_id)
    time.sleep(1)
    # Retrieve run, check both alerts have been added
    _online_run.refresh()
    assert sorted(_online_run.alerts) == sorted(_expected_alerts)

    # Create another alert, do not attach to run
    _id = run.create_metric_threshold_alert(
        name=f"metric_threshold_alert_{_uuid}",
        metric="test",
        threshold=10,
        rule="is above",
        attach_to_run=False,
    )
    time.sleep(1)
    # Retrieve run, check alert has NOT been added
    _online_run.refresh()
    assert sorted(_online_run.alerts) == sorted(_expected_alerts)

    # Try adding all three alerts using add_alerts
    _expected_alerts.append(_id)
    run.add_alerts(
        names=[
            f"event_alert_{_uuid}",
            f"metric_range_alert_{_uuid}",
            f"metric_threshold_alert_{_uuid}",
        ]
    )

    # Check that there is no duplication
    _online_run.refresh()
    assert sorted(_online_run.alerts) == sorted(_expected_alerts)

    # Create another run without adding to run
    _id = run.create_user_alert(name=f"user_alert_{_uuid}", attach_to_run=False)

    # Check alert is not added
    _online_run.refresh()
    assert sorted(_online_run.alerts) == sorted(_expected_alerts)

    # Try adding alerts with IDs, check there is no duplication
    _expected_alerts.append(_id)
    run.add_alerts(ids=_expected_alerts)

    _online_run.refresh()
    assert sorted(_online_run.alerts) == sorted(_expected_alerts)

    run.close()

    client = sv_cl.Client()
    with contextlib.suppress(ObjectNotFoundError):
        client.delete_folder(
            f"/simvue_unit_testing/{_uuid}",
            remove_runs=True,
            recursive=True
        )
    for _id in _expected_alerts:
        client.delete_alert(_id)
        
@pytest.mark.run
@pytest.mark.offline
def test_add_alerts_offline(monkeypatch) -> None:
    _uuid = f"{uuid.uuid4()}".split("-")[0]
    
    temp_d = tempfile.TemporaryDirectory()
    monkeypatch.setenv("SIMVUE_OFFLINE_DIRECTORY", temp_d.name)

    run = sv_run.Run(mode="offline")
    run.init(
        name="test_add_alerts_offline",
        folder=f"/simvue_unit_testing/{_uuid}",
        retention_period=os.environ.get("SIMVUE_TESTING_RETENTION_PERIOD", "2 mins"),
        tags=[platform.system(), "test_add_alerts"],
        visibility="tenant" if os.environ.get("CI") else None,
    )

    _expected_alerts = []

    # Create alerts, have them attach to run automatically
    _id = run.create_event_alert(
        name=f"event_alert_{_uuid}",
        pattern="test",
    )
    _expected_alerts.append(_id)

    # Create another alert and attach to run
    _id = run.create_metric_range_alert(
        name=f"metric_range_alert_{_uuid}",
        metric="test",
        range_low=10,
        range_high=100,
        rule="is inside range",
    )
    _expected_alerts.append(_id)

    # Create another alert, do not attach to run
    _id = run.create_metric_threshold_alert(
        name=f"metric_threshold_alert_{_uuid}",
        metric="test",
        threshold=10,
        rule="is above",
        attach_to_run=False,
    )
    
    # Try redefining existing alert again
    _id = run.create_metric_range_alert(
        name=f"metric_range_alert_{_uuid}",
        metric="test",
        range_low=10,
        range_high=100,
        rule="is inside range",
    )
    
    _id_mapping = sv_send.sender(os.environ["SIMVUE_OFFLINE_DIRECTORY"], 2, 10, throw_exceptions=True)
    _online_run = RunObject(identifier=_id_mapping.get(run.id))

    # Check that there is no duplication
    assert sorted(_online_run.alerts) == sorted([_id_mapping.get(_id) for _id in _expected_alerts])

    # Create another run without adding to run
    _id = run.create_user_alert(name=f"user_alert_{_uuid}", attach_to_run=False)
    _id_mapping = sv_send.sender(os.environ["SIMVUE_OFFLINE_DIRECTORY"], 2, 10, throw_exceptions=True)

    # Check alert is not added
    _online_run.refresh()
    assert sorted(_online_run.alerts) == sorted([_id_mapping.get(_id) for _id in _expected_alerts])

    # Try adding alerts with IDs, check there is no duplication
    _expected_alerts.append(_id)
    run.add_alerts(ids=_expected_alerts)
    _id_mapping = sv_send.sender(os.environ["SIMVUE_OFFLINE_DIRECTORY"], 2, 10, throw_exceptions=True)

    _online_run.refresh()
    assert sorted(_online_run.alerts) == sorted([_id_mapping.get(_id) for _id in _expected_alerts])

    run.close()

    client = sv_cl.Client()
    with contextlib.suppress(ObjectNotFoundError):
        client.delete_folder(
            f"/simvue_unit_testing/{_uuid}",
            remove_runs=True,
            recursive=True
        )
    for _id in [_id_mapping.get(_id) for _id in _expected_alerts]:
        client.delete_alert(_id)


@pytest.mark.run
def test_log_alert() -> None:
    _uuid = f"{uuid.uuid4()}".split("-")[0]

    run = sv_run.Run()
    run.init(
        name="test_log_alerts",
        folder=f"/simvue_unit_testing/{_uuid}",
        retention_period=os.environ.get("SIMVUE_TESTING_RETENTION_PERIOD", "2 mins"),
        tags=[platform.system(), "test_add_alerts"],
        visibility="tenant" if os.environ.get("CI") else None,
    )
    _run_id = run.id
    # Create a user alert
    _id = run.create_user_alert(
        name=f"user_alert_{_uuid}",
    )

    # Set alert state to critical by name
    run.log_alert(name=f"user_alert_{_uuid}", state="critical")

    client = sv_cl.Client()
    _alert = client.get_alerts(run_id=_run_id, critical_only=False, names_only=False)[0]
    assert _alert.get_status(_run_id) == "critical"

    # Set alert state to OK by ID
    run.log_alert(identifier=_id, state="ok")

    _alert.refresh()
    assert _alert.get_status(_run_id) == "ok"

    # Check invalid name throws sensible error
    with pytest.raises(RuntimeError) as e:
        run.log_alert(name="fake_name_1234321", state="critical")
    assert "Alert with name 'fake_name_1234321' could not be found." in str(e.value)

    # Check you cannot specify both ID and name
    with pytest.raises(RuntimeError) as e:
        run.log_alert(identifier="myid", name="myname", state="critical")
    assert "Please specify alert to update either by ID or by name." in str(e.value)

    with contextlib.suppress(ObjectNotFoundError):
        client.delete_folder(
            f"/simvue_unit_testing/{_uuid}",
            remove_runs=True,
            recursive=True
        )
    client.delete_alert(_id)


@pytest.mark.run
def test_abort_on_alert_process(mocker: pytest_mock.MockerFixture) -> None:
    def testing_exit(status: int) -> None:
        raise SystemExit(status)

    trigger = threading.Event()

    def abort_callback(abort_run=trigger) -> None:
        trigger.set()

    _uuid = f"{uuid.uuid4()}".split("-")[0]
    run = sv_run.Run(abort_callback=abort_callback)
    run.init(
        name="test_abort_on_alert_process",
        folder=f"/simvue_unit_testing/{_uuid}",
        retention_period=os.environ.get("SIMVUE_TESTING_RETENTION_PERIOD", "2 mins"),
        tags=[platform.system(), "test_abort_on_alert_process"],
        visibility="tenant" if os.environ.get("CI") else None,
    )

    mocker.patch("os._exit", testing_exit)
    N_PROCESSES: int = 3
    run.config(system_metrics_interval=1)
    run._heartbeat_interval = 1
    run._testing = True
    run.add_process(
        identifier=f"forever_long_{os.environ.get('PYTEST_XDIST_WORKER', 0)}",
        executable="bash",
        c="&".join(["sleep 10"] * N_PROCESSES),
    )
    process_id = list(run._executor._processes.values())[0].pid
    process = psutil.Process(process_id)
    assert len(child_processes := process.children(recursive=True)) == 3
    time.sleep(2)
    client = sv_cl.Client()
    client.abort_run(run.id, reason="testing abort")
    time.sleep(4)
    assert run._system_metrics_interval == 1
    for child in child_processes:
        assert not child.is_running()
    if run._status != "terminated":
        run.kill_all_processes()
        raise AssertionError("Run was not terminated")
    assert trigger.is_set()
    run.close()
    with contextlib.suppress(ObjectNotFoundError):
        client.delete_folder(
            f"/simvue_unit_testing/{_uuid}",
            remove_runs=True,
            recursive=True
        )


@pytest.mark.run
def test_abort_on_alert_python(
    speedy_heartbeat, create_plain_run: tuple[sv_run.Run, dict], mocker: pytest_mock.MockerFixture
) -> None:
    timeout: int = 20
    interval: int = 0
    run, _ = create_plain_run
    client = sv_cl.Client()
    client.abort_run(run.id, reason="Test abort")

    attempts: int = 0

    while run._status == "terminated" and attemps < 5:
        time.sleep(1)
        attempts += 1

    if attempts >= 5:
        raise AssertionError("Failed to terminate run")


@pytest.mark.run
def test_abort_on_alert_raise(
    create_plain_run: tuple[sv_run.Run, dict]
) -> None:

    run, _ = create_plain_run
    run.config(system_metrics_interval=1)
    run._heartbeat_interval = 1
    run._testing = True
    alert_id = run.create_user_alert("abort_test", trigger_abort=True)
    run.add_process(identifier=f"forever_long_other_{os.environ.get('PYTEST_XDIST_WORKER', 0)}", executable="bash", c="sleep 10")
    run.log_alert(identifier=alert_id, state="critical")
    _alert = Alert(identifier=alert_id)
    assert _alert.get_status(run.id) == "critical"
    counter = 0
    while run._status != "terminated" and counter < 15:
        time.sleep(1)
        assert run._sv_obj.abort_trigger, "Abort trigger was not set"
        counter += 1
    if counter >= 15:
        run.kill_all_processes()
        raise AssertionError("Run was not terminated")


@pytest.mark.run
def test_kill_all_processes(create_plain_run: tuple[sv_run.Run, dict]) -> None:
    run, _ = create_plain_run
    run.config(system_metrics_interval=1)
    run.add_process(identifier=f"forever_long_a_{os.environ.get('PYTEST_XDIST_WORKER', 0)}", executable="bash", c="sleep 10000")
    run.add_process(identifier=f"forever_long_b_{os.environ.get('PYTEST_XDIST_WORKER', 0)}", executable="bash", c="sleep 10000")
    processes = [
        psutil.Process(process.pid) for process in run._executor._processes.values()
    ]
    run.kill_all_processes()
    for process in processes:
        assert not process.is_running()
        assert all(not child.is_running() for child in process.children(recursive=True))


@pytest.mark.run
def test_run_created_with_no_timeout() -> None:
    _uuid = f"{uuid.uuid4()}".split("-")[0]
    with simvue.Run() as run:
        run.init(
            name="test_run_created_with_no_timeout",
            folder=f"/simvue_unit_testing/{_uuid}",
            retention_period=os.environ.get("SIMVUE_TESTING_RETENTION_PERIOD", "2 mins"),
            timeout=None,
            visibility="tenant" if os.environ.get("CI") else None,
        )
    client = simvue.Client()
    assert client.get_run(run.id)
    with contextlib.suppress(ObjectNotFoundError):
        client.delete_folder(
            f"/simvue_unit_testing/{_uuid}",
            remove_runs=True,
            recursive=True
        )


@pytest.mark.parametrize("mode", ("online", "offline"), ids=("online", "offline"))
@pytest.mark.run
def test_reconnect_functionality(mode, monkeypatch: pytest.MonkeyPatch) -> None:
    temp_d: tempfile.TemporaryDirectory | None = None
    _uuid = f"{uuid.uuid4()}".split("-")[0]

    if mode == "offline":
        temp_d = tempfile.TemporaryDirectory()
        monkeypatch.setenv("SIMVUE_OFFLINE_DIRECTORY", temp_d.name)

    with simvue.Run(mode=mode) as run:
        run.init(
            name="test_reconnect",
            folder=f"/simvue_unit_testing/{_uuid}",
            retention_period=os.environ.get("SIMVUE_TESTING_RETENTION_PERIOD", "2 mins"),
            timeout=None,
            running=False,
        )
        run_id = run.id
    if mode == "offline":
        _sender = Sender(cache_directory=os.environ["SIMVUE_OFFLINE_DIRECTORY"], max_workers=2, threading_threshold=10, throw_exceptions=True)
        _sender.upload()
        _id_mapping = _sender.id_mapping
        run_id = _id_mapping.get(run_id)

    client = simvue.Client()
    _created_run = client.get_run(run_id)
    assert _created_run.status == "created"

    with simvue.Run() as run:
        run.reconnect(run_id)
        assert run._sv_obj.status == "running"
        run.log_metrics({"test_metric": 1})
        run.log_event("Testing!")

    if mode == "offline":
        _sender = Sender(cache_directory=os.environ["SIMVUE_OFFLINE_DIRECTORY"], max_workers=2, threading_threshold=10, throw_exceptions=True)
        _sender.upload()
        _id_mapping = _sender.id_mapping

    _reconnected_run = client.get_run(run_id)
    assert dict(_reconnected_run.metrics)["test_metric"]["last"] == 1
    assert client.get_events(run_id)[0]["message"] == "Testing!"


@pytest.mark.run
def test_env_var_metadata() -> None:
    # Add some environment variables to glob
    _recorded_env = {
        "SIMVUE_RUN_TEST_VAR_1": "1",
        "SIMVUE_RUN_TEST_VAR_2": "hello"
    }
    os.environ.update(_recorded_env)
    with simvue.Run() as run:
        run.init(
            name="test_reconnect",
            folder="/simvue_unit_testing",
            retention_period="2 minutes",
            timeout=None,
            running=False,
            record_shell_vars={"SIMVUE_RUN_TEST_VAR_*"}
        )
    _recorded_meta = RunObject(identifier=run.id).metadata
    assert all(key in _recorded_meta.get("shell") for key in _recorded_env)

@pytest.mark.run
def test_reconnect_with_process() -> None:
    _uuid = f"{uuid.uuid4()}".split("-")[0]
    with simvue.Run() as run:
        run.init(
            name="test_reconnect_with_process",
            folder=f"/simvue_unit_testing/{_uuid}",
            retention_period=os.environ.get("SIMVUE_TESTING_RETENTION_PERIOD", "2 mins"),
            running=False,
            visibility="tenant" if os.environ.get("CI") else None,
        )

    with sv_run.Run() as new_run:
        new_run.reconnect(run.id)
        run.add_process(
            identifier=f"test_process_{os.environ.get('PYTEST_XDIST_WORKER', 0)}",
            executable="bash",
            c="echo 'Hello World!'",
        )

    client = sv_cl.Client()

    with contextlib.suppress(ObjectNotFoundError):
        client.delete_folder(
            f"/simvue_unit_testing/{_uuid}",
            remove_runs=True,
            recursive=True
        )

@pytest.mark.parametrize(
    "environment", ("python_conda", "python_poetry", "python_uv", "julia", "rust", "nodejs")
)
def test_run_environment_metadata(environment: str, mocker: pytest_mock.MockerFixture) -> None:
    """Tests that the environment information is compatible with the server."""
    from simvue.config.user import SimvueConfiguration
    from simvue.metadata import environment as env_func
    _data_dir = pathlib.Path(__file__).parents[1].joinpath("example_data")
    _target_dir = _data_dir
    if "python" in environment:
        _target_dir = _data_dir.joinpath(environment)
    _config = SimvueConfiguration.fetch(mode="online")

    with sv_run.Run(server_token=_config.server.token, server_url=_config.server.url) as run:
        _uuid = f"{uuid.uuid4()}".split("-")[0]
        run.init(
            name=f"test_run_environment_metadata_{environment}",
            folder=f"/simvue_unit_testing/{_uuid}",
            retention_period=os.environ.get("SIMVUE_TESTING_RETENTION_PERIOD", "2 mins"),
            running=False,
            visibility="tenant" if os.environ.get("CI") else None,
        )
        run.update_metadata(env_func(_target_dir))

