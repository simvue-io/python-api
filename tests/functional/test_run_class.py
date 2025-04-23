import json
import os
import pytest
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
from simvue.eco.api_client import CO2SignalData, CO2SignalResponse
from simvue.exception import SimvueRunError
from simvue.eco.emissions_monitor import TIME_FORMAT, CO2Monitor
import simvue.run as sv_run
import simvue.client as sv_cl
import simvue.sender as sv_send

from simvue.api.objects import Run as RunObject

if typing.TYPE_CHECKING:
    from .conftest import CountingLogHandler


@pytest.mark.run
def test_created_run() -> None:
    with sv_run.Run() as run_created:
        run_created.init(running=False, retention_period="1 min")
        _run = RunObject(identifier=run_created.id)
        assert _run.status == "created"


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
def test_run_with_emissions_online(speedy_heartbeat, mock_co2_signal, create_plain_run) -> None:
    run_created, _ = create_plain_run
    run_created.config(enable_emission_metrics=True)
    time.sleep(3)
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
        assert _total_metric_name in _metric_values


@pytest.mark.run
@pytest.mark.eco
@pytest.mark.offline
def test_run_with_emissions_offline(speedy_heartbeat, mock_co2_signal, create_plain_run_offline) -> None:
    run_created, _ = create_plain_run_offline
    run_created.config(enable_emission_metrics=True)
    time.sleep(2)
    id_mapping = sv_send.sender(os.environ["SIMVUE_OFFLINE_DIRECTORY"])
    _run = RunObject(identifier=id_mapping[run_created.id])
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
        assert _total_metric_name in _metric_values

@pytest.mark.run
@pytest.mark.parametrize(
    "timestamp",
    (datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f"), None),
    ids=("timestamp", "no_timestamp"),
)
@pytest.mark.parametrize("overload_buffer", (True, False), ids=("overload", "normal"))
@pytest.mark.parametrize(
    "visibility", ("bad_option", "tenant", "public", ["ciuser01"], None)
)
def test_log_metrics(
    overload_buffer: bool,
    timestamp: str | None,
    mocker: pytest_mock.MockerFixture,
    request: pytest.FixtureRequest,
    visibility: typing.Literal["public", "tenant"] | list[str] | None,
) -> None:
    METRICS = {"a": 10, "b": 1.2}

    # Have to create the run outside of fixtures because the resources dispatch
    # occurs immediately and is not captured by the handler when using the fixture
    run = sv_run.Run()
    run.config(suppress_errors=False)

    metrics_spy = mocker.spy(Metrics, "new")
    system_metrics_spy = mocker.spy(sv_run.Run, "_get_internal_metrics")

    if visibility == "bad_option":
        with pytest.raises(SimvueRunError, match="visibility") as e:
            run.init(
                name=f"test_run_{str(uuid.uuid4()).split('-', 1)[0]}",
                tags=[
                    "simvue_client_unit_tests",
                    request.node.name.replace("[", "_").replace("]", "_"),
                ],
                folder="/simvue_unit_testing",
                retention_period="1 hour",
                visibility=visibility,
            )
            run.config(system_metrics_interval=1)
        return

    run.init(
        name=f"test_run_{str(uuid.uuid4()).split('-', 1)[0]}",
        tags=[
            "simvue_client_unit_tests",
            request.node.name.replace("[", "_").replace("]", "_"),
        ],
        folder="/simvue_unit_testing",
        visibility=visibility,
        retention_period="1 hour",
    )
    run.config(system_metrics_interval=1)

    # Speed up the read rate for this test
    run._dispatcher._max_buffer_size = 10
    run._dispatcher._max_read_rate *= 10

    if overload_buffer:
        for i in range(run._dispatcher._max_buffer_size * 3):
            run.log_metrics({key: i for key in METRICS}, timestamp=timestamp)
    else:
        run.log_metrics(METRICS, timestamp=timestamp)
    time.sleep(2.0 if overload_buffer else 1.0)
    run.close()
    client = sv_cl.Client()
    _data = client.get_metric_values(
        run_ids=[run._id],
        metric_names=list(METRICS.keys()),
        xaxis="step",
        aggregate=False,
    )

    with contextlib.suppress(RuntimeError):
        client.delete_run(run._id)

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
def test_log_metrics_offline(create_plain_run_offline: tuple[sv_run.Run, dict]) -> None:
    METRICS = {"a": 10, "b": 1.2, "c": 2}
    run, _ = create_plain_run_offline
    run_name = run._name
    run.log_metrics(METRICS)
    time.sleep(1)
    sv_send.sender(os.environ["SIMVUE_OFFLINE_DIRECTORY"], 2, 10)
    run.close()
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
    "visibility", ("bad_option", "tenant", "public", ["ciuser01"], None)
)
def test_visibility(
    request: pytest.FixtureRequest,
    visibility: typing.Literal["public", "tenant"] | list[str] | None,
) -> None:

    run = sv_run.Run()
    run.config(suppress_errors=False)

    if visibility == "bad_option":
        with pytest.raises(SimvueRunError, match="visibility") as e:
            run.init(
                name=f"test_visibility_{str(uuid.uuid4()).split('-', 1)[0]}",
                tags=[
                    "simvue_client_unit_tests",
                    request.node.name.replace("[", "_").replace("]", "_"),
                ],
                folder="/simvue_unit_testing",
                retention_period="1 hour",
                visibility=visibility,
            )
        return

    run.init(
        name=f"test_visibility_{str(uuid.uuid4()).split('-', 1)[0]}",
        tags=[
            "simvue_client_unit_tests",
            request.node.name.replace("[", "_").replace("]", "_"),
        ],
        folder="/simvue_unit_testing",
        visibility=visibility,
        retention_period="1 hour",
    )
    time.sleep(1)
    _id = run._id
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
    "visibility", ("bad_option", "tenant", "public", ["ciuser01"], None)
)
def test_visibility_offline(
    request: pytest.FixtureRequest,
    monkeypatch,
    visibility: typing.Literal["public", "tenant"] | list[str] | None,
) -> None:
    with tempfile.TemporaryDirectory() as tempd:
        os.environ["SIMVUE_OFFLINE_DIRECTORY"] = tempd
        run = sv_run.Run(mode="offline")
        run.config(suppress_errors=False)

        if visibility == "bad_option":
            with pytest.raises(SimvueRunError, match="visibility") as e:
                run.init(
                    name=f"test_visibility_{str(uuid.uuid4()).split('-', 1)[0]}",
                    tags=[
                        "simvue_client_unit_tests",
                        request.node.name.replace("[", "_").replace("]", "_"),
                    ],
                    folder="/simvue_unit_testing",
                    retention_period="1 hour",
                    visibility=visibility,
                )
            return

        run.init(
            name=f"test_visibility_{str(uuid.uuid4()).split('-', 1)[0]}",
            tags=[
                "simvue_client_unit_tests",
                request.node.name.replace("[", "_").replace("]", "_"),
            ],
            folder="/simvue_unit_testing",
            visibility=visibility,
            retention_period="1 hour",
        )
        time.sleep(1)
        _id = run._id
        _id_mapping = sv_send.sender(os.environ["SIMVUE_OFFLINE_DIRECTORY"], 2, 10)
        run.close()
        _retrieved_run = RunObject(identifier=_id_mapping.get(_id))

        if visibility == "tenant":
            assert _retrieved_run.visibility.tenant
        elif visibility == "public":
            assert _retrieved_run.visibility.public
        elif not visibility:
            assert not _retrieved_run.visibility.tenant and not _retrieved_run.visibility.public
        else:
            assert _retrieved_run.visibility.users == visibility

@pytest.mark.run
def test_log_events_online(create_test_run: tuple[sv_run.Run, dict]) -> None:
    EVENT_MSG = "Hello world!"
    run, _ = create_test_run
    run.log_event(EVENT_MSG)
    time.sleep(1.0)
    run.close()
    client = sv_cl.Client()
    event_data = client.get_events(run.id, count_limit=1)
    assert event_data[0].get("message", EVENT_MSG)


@pytest.mark.run
@pytest.mark.offline
def test_log_events_offline(create_plain_run_offline: tuple[sv_run.Run, dict]) -> None:
    EVENT_MSG = "Hello offline world!"
    run, _ = create_plain_run_offline
    run_name = run._name
    run.log_event(EVENT_MSG)
    time.sleep(1)
    sv_send.sender(os.environ["SIMVUE_OFFLINE_DIRECTORY"], 2, 10)
    run.close()
    client = sv_cl.Client()
    event_data = client.get_events(client.get_run_id_from_name(run_name), count_limit=1)
    assert event_data[0].get("message", EVENT_MSG)


@pytest.mark.run
@pytest.mark.offline
def test_offline_tags(create_plain_run_offline: tuple[sv_run.Run, dict]) -> None:
    run, run_data = create_plain_run_offline
    time.sleep(1.0)
    sv_send.sender(os.environ["SIMVUE_OFFLINE_DIRECTORY"], 2, 10)
    run.close()
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
    run.close()
    time.sleep(1.0)
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
    time.sleep(1.0)
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
    run_name = run._name
    # Add an initial set of metadata
    run.update_metadata({"a": 10, "b": 1.2, "c": "word"})
    # Try updating a second time, check original dict isnt overwritten
    run.update_metadata({"d": "new"})
    # Try updating an already defined piece of metadata
    run.update_metadata({"a": 1})

    sv_send.sender(os.environ["SIMVUE_OFFLINE_DIRECTORY"], 2, 10)
    run.close()
    time.sleep(1.0)

    client = sv_cl.Client()
    run_info = client.get_run(client.get_run_id_from_name(run_name))

    for key, value in METADATA.items():
        assert run_info.metadata.get(key) == value


@pytest.mark.run
@pytest.mark.parametrize("multi_threaded", (True, False), ids=("multi", "single"))
def test_runs_multiple_parallel(
    multi_threaded: bool, request: pytest.FixtureRequest
) -> None:
    N_RUNS: int = 2
    if multi_threaded:

        def thread_func(index: int) -> tuple[int, list[dict[str, typing.Any]], str]:
            with sv_run.Run() as run:
                run.config(suppress_errors=False)
                run.init(
                    name=f"test_runs_multiple_{index + 1}",
                    tags=[
                        "simvue_client_unit_tests",
                        request.node.name.replace("[", "_").replace("]", "_"),
                    ],
                    folder="/simvue_unit_testing",
                    retention_period="1 hour",
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
                    name="test_runs_multiple_unthreaded_1",
                    tags=[
                        "simvue_client_unit_tests",
                        request.node.name.replace("[", "_").replace("]", "_"),
                    ],
                    folder="/simvue_unit_testing",
                    retention_period="1 hour",
                )
                run_2.config(suppress_errors=False)
                run_2.init(
                    name="test_runs_multiple_unthreaded_2",
                    tags=["simvue_client_unit_tests", "test_multi_run_unthreaded"],
                    folder="/simvue_unit_testing",
                    retention_period="1 hour",
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
                    assert client.get_metric_values(
                        run_ids=[run_id],
                        metric_names=[f"var_{i}"],
                        xaxis="step",
                        output_format="dict",
                        aggregate=False,
                    )

        with contextlib.suppress(RuntimeError):
            client.delete_run(run_1._id)
            client.delete_run(run_2._id)


@pytest.mark.run
def test_runs_multiple_series(request: pytest.FixtureRequest) -> None:
    N_RUNS: int = 2

    metrics = []
    run_ids = []

    for index in range(N_RUNS):
        with sv_run.Run() as run:
            run_metrics = []
            run.config(suppress_errors=False)
            run.init(
                name=f"test_runs_multiple_series_{index}",
                tags=[
                    "simvue_client_unit_tests",
                    request.node.name.replace("[", "_").replace("]", "_"),
                ],
                folder="/simvue_unit_testing",
                retention_period="1 hour",
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
        assert client.get_metric_values(
            run_ids=[run_id],
            metric_names=[f"var_{i}"],
            xaxis="step",
            output_format="dict",
            aggregate=False,
        )

    with contextlib.suppress(RuntimeError):
        for run_id in run_ids:
            client.delete_run(run_id)


@pytest.mark.run
@pytest.mark.parametrize("post_init", (True, False), ids=("pre-init", "post-init"))
def test_suppressed_errors(
    setup_logging: "CountingLogHandler", post_init: bool, request: pytest.FixtureRequest
) -> None:
    setup_logging.captures = ["Skipping call to"]

    with sv_run.Run(mode="offline") as run:
        decorated_funcs = [
            name
            for name, method in inspect.getmembers(run, inspect.ismethod)
            if hasattr(method, "__fail_safe")
        ]

        if post_init:
            decorated_funcs.remove("init")
            run.init(
                name="test_suppressed_errors",
                folder="/simvue_unit_testing",
                tags=[
                    "simvue_client_unit_tests",
                    request.node.name.replace("[", "_").replace("]", "_"),
                ],
                retention_period="1 hour",
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


@pytest.mark.run
def test_bad_run_arguments() -> None:
    with sv_run.Run() as run:
        with pytest.raises(RuntimeError):
            run.init("sdas", [34])


@pytest.mark.run
def test_set_folder_details(request: pytest.FixtureRequest) -> None:
    with sv_run.Run() as run:
        folder_name: str = "/simvue_unit_tests"
        description: str = "test description"
        tags: list[str] = [
            "simvue_client_unit_tests",
            request.node.name.replace("[", "_").replace("]", "_"),
        ]
        run.init(folder=folder_name)
        run.set_folder_details(tags=tags, description=description)

    client = sv_cl.Client()
    _folder = client.get_folder(folder_path=folder_name)

    assert _folder.tags
    assert sorted(_folder.tags) == sorted(tags)

    assert _folder.description == description


@pytest.mark.run
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
    create_plain_run: typing.Tuple[sv_run.Run, dict],
    valid_mimetype: bool,
    preserve_path: bool,
    name: str | None,
    allow_pickle: bool,
    empty_file: bool,
    category: typing.Literal["input", "output", "code"],
    capfd,
) -> None:
    simvue_run, _ = create_plain_run
    file_type: str = "text/plain" if valid_mimetype else "text/text"
    with tempfile.TemporaryDirectory() as tempd:
        with open(
            (out_name := pathlib.Path(tempd).joinpath("test_file.txt")),
            "w",
        ) as out_f:
            out_f.write("" if empty_file else "test data entry")

        if valid_mimetype:
            simvue_run.save_file(
                out_name,
                category=category,
                file_type=file_type,
                preserve_path=preserve_path,
                name=name,
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
        simvue_run.close()
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
    create_plain_run_offline: typing.Tuple[sv_run.Run, dict],
    preserve_path: bool,
    name: str | None,
    allow_pickle: bool,
    empty_file: bool,
    category: typing.Literal["input", "output", "code"],
    capfd,
) -> None:
    simvue_run, _ = create_plain_run_offline
    run_name = simvue_run._name
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
        )

        simvue_run.save_file(
            out_name,
            category=category,
            preserve_path=preserve_path,
            name=name,
        )
        sv_send.sender(os.environ["SIMVUE_OFFLINE_DIRECTORY"], 2, 10)
        simvue_run.close()
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
            run_id=client.get_run_id_from_name(run_name),
            name=f"{name or stored_name}",
            output_dir=tempd,
        )
        assert out_loc.joinpath(name or out_name.name).exists()


@pytest.mark.run
def test_update_tags_running(
    create_plain_run: typing.Tuple[sv_run.Run, dict],
    request: pytest.FixtureRequest,
) -> None:
    simvue_run, _ = create_plain_run

    tags = [
        "simvue_client_unit_tests",
        request.node.name.replace("[", "_").replace("]", "_"),
    ]

    simvue_run.set_tags(tags)

    time.sleep(1)
    client = sv_cl.Client()
    run_data = client.get_run(simvue_run._id)
    assert sorted(run_data.tags) == sorted(tags)

    simvue_run.update_tags(["additional"])

    time.sleep(1)
    run_data = client.get_run(simvue_run._id)
    assert sorted(run_data.tags) == sorted(tags + ["additional"])


@pytest.mark.run
def test_update_tags_created(
    create_pending_run: typing.Tuple[sv_run.Run, dict],
    request: pytest.FixtureRequest,
) -> None:
    simvue_run, _ = create_pending_run

    tags = [
        "simvue_client_unit_tests",
        request.node.name.replace("[", "_").replace("]", "_"),
    ]

    simvue_run.set_tags(tags)

    time.sleep(1)
    client = sv_cl.Client()
    run_data = client.get_run(simvue_run._id)
    assert sorted(run_data.tags) == sorted(tags)

    simvue_run.update_tags(["additional"])

    time.sleep(1)
    run_data = client.get_run(simvue_run._id)
    assert sorted(run_data.tags) == sorted(tags + ["additional"])


@pytest.mark.offline
@pytest.mark.run
def test_update_tags_offline(
    create_plain_run_offline: typing.Tuple[sv_run.Run, dict],
) -> None:
    simvue_run, _ = create_plain_run_offline
    run_name = simvue_run._name

    simvue_run.set_tags(
        [
            "simvue_client_unit_tests",
        ]
    )

    simvue_run.update_tags(["additional"])

    sv_send.sender(os.environ["SIMVUE_OFFLINE_DIRECTORY"], 2, 10)
    simvue_run.close()
    time.sleep(1.0)

    client = sv_cl.Client()
    run_data = client.get_run(client.get_run_id_from_name(run_name))

    time.sleep(1)
    run_data = client.get_run(simvue_run._id)
    assert sorted(run_data.tags) == sorted(["simvue_client_unit_tests", "additional"])


@pytest.mark.run
@pytest.mark.parametrize("object_type", ("DataFrame", "ndarray"))
def test_save_object(
    create_plain_run: typing.Tuple[sv_run.Run, dict], object_type: str
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
        folder="/simvue_unit_tests",
        retention_period="1 min",
        tags=["test_add_alerts"],
        visibility="tenant",
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
    _online_run = RunObject(identifier=run._id)
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
    time.sleep(1)

    # Check that there is no duplication
    _online_run.refresh()
    assert sorted(_online_run.alerts) == sorted(_expected_alerts)

    # Create another run without adding to run
    _id = run.create_user_alert(name=f"user_alert_{_uuid}", attach_to_run=False)
    time.sleep(1)

    # Check alert is not added
    _online_run.refresh()
    assert sorted(_online_run.alerts) == sorted(_expected_alerts)

    # Try adding alerts with IDs, check there is no duplication
    _expected_alerts.append(_id)
    run.add_alerts(ids=_expected_alerts)
    time.sleep(1)

    _online_run.refresh()
    assert sorted(_online_run.alerts) == sorted(_expected_alerts)

    run.close()

    client = sv_cl.Client()
    client.delete_run(run._id)
    for _id in _expected_alerts:
        client.delete_alert(_id)


@pytest.mark.run
def test_log_alert() -> None:
    _uuid = f"{uuid.uuid4()}".split("-")[0]

    run = sv_run.Run()
    run.init(
        name="test_log_alerts",
        folder="/simvue_unit_tests",
        retention_period="1 min",
        tags=["test_add_alerts"],
        visibility="tenant",
    )
    _run_id = run._id
    # Create a user alert
    _id = run.create_user_alert(
        name=f"user_alert_{_uuid}",
    )

    # Set alert state to critical by name
    run.log_alert(name=f"user_alert_{_uuid}", state="critical")
    time.sleep(1)

    client = sv_cl.Client()
    _alert = client.get_alerts(run_id=_run_id, critical_only=False, names_only=False)[0]
    assert _alert.get_status(_run_id) == "critical"

    # Set alert state to OK by ID
    run.log_alert(identifier=_id, state="ok")
    time.sleep(2)

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


@pytest.mark.run
def test_abort_on_alert_process(mocker: pytest_mock.MockerFixture) -> None:
    def testing_exit(status: int) -> None:
        raise SystemExit(status)

    trigger = threading.Event()

    def abort_callback(abort_run=trigger) -> None:
        trigger.set()

    run = sv_run.Run(abort_callback=abort_callback)
    run.init(
        name="test_abort_on_alert_process",
        folder="/simvue_unit_tests",
        retention_period="1 min",
        tags=["test_abort_on_alert_process"],
        visibility="tenant",
    )

    mocker.patch("os._exit", testing_exit)
    N_PROCESSES: int = 3
    run.config(system_metrics_interval=1)
    run._heartbeat_interval = 1
    run._testing = True
    run.add_process(
        identifier="forever_long",
        executable="bash",
        c="&".join(["sleep 10"] * N_PROCESSES),
    )
    process_id = list(run._executor._processes.values())[0].pid
    process = psutil.Process(process_id)
    assert len(child_processes := process.children(recursive=True)) == 3
    time.sleep(2)
    client = sv_cl.Client()
    client.abort_run(run._id, reason="testing abort")
    time.sleep(4)
    assert run._system_metrics_interval == 1
    for child in child_processes:
        assert not child.is_running()
    if run._status != "terminated":
        run.kill_all_processes()
        raise AssertionError("Run was not terminated")
    assert trigger.is_set()


@pytest.mark.run
def test_abort_on_alert_python(
    speedy_heartbeat, create_plain_run: typing.Tuple[sv_run.Run, dict], mocker: pytest_mock.MockerFixture
) -> None:
    timeout: int = 20
    interval: int = 0
    run, _ = create_plain_run
    client = sv_cl.Client()
    client.abort_run(run.id, reason="Test abort")
    time.sleep(2)
    assert run._status == "terminated"


@pytest.mark.run
def test_abort_on_alert_raise(
    create_plain_run: typing.Tuple[sv_run.Run, dict]
) -> None:

    run, _ = create_plain_run
    run.config(system_metrics_interval=1)
    run._heartbeat_interval = 1
    run._testing = True
    alert_id = run.create_user_alert("abort_test", trigger_abort=True)
    run.add_process(identifier="forever_long", executable="bash", c="sleep 10")
    time.sleep(2)
    run.log_alert(identifier=alert_id, state="critical")
    time.sleep(1)
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
def test_kill_all_processes(create_plain_run: typing.Tuple[sv_run.Run, dict]) -> None:
    run, _ = create_plain_run
    run.config(system_metrics_interval=1)
    run.add_process(identifier="forever_long_1", executable="bash", c="sleep 10000")
    run.add_process(identifier="forever_long_2", executable="bash", c="sleep 10000")
    processes = [
        psutil.Process(process.pid) for process in run._executor._processes.values()
    ]
    time.sleep(2)
    run.kill_all_processes()
    time.sleep(4)
    for process in processes:
        assert not process.is_running()
        assert all(not child.is_running() for child in process.children(recursive=True))


@pytest.mark.run
def test_run_created_with_no_timeout() -> None:
    with simvue.Run() as run:
        run.init(
            name="test_run_created_with_no_timeout",
            folder="/simvue_unit_testing",
            retention_period="2 minutes",
            timeout=None,
        )
    client = simvue.Client()
    assert client.get_run(run._id)


@pytest.mark.parametrize("mode", ("online", "offline"), ids=("online", "offline"))
@pytest.mark.run
def test_reconnect(mode, monkeypatch: pytest.MonkeyPatch) -> None:
    temp_d: tempfile.TemporaryDirectory | None = None

    if mode == "offline":
        temp_d = tempfile.TemporaryDirectory()
        monkeypatch.setenv("SIMVUE_OFFLINE_DIRECTORY", temp_d.name)

    with simvue.Run(mode=mode) as run:
        run.init(
            name="test_reconnect",
            folder="/simvue_unit_testing",
            retention_period="2 minutes",
            timeout=None,
            running=False,
        )
        run_id = run.id
    if mode == "offline":
        _id_mapping = sv_send.sender(os.environ["SIMVUE_OFFLINE_DIRECTORY"], 2, 10)
        run_id = _id_mapping.get(run_id)

    client = simvue.Client()
    _created_run = client.get_run(run_id)
    assert _created_run.status == "created"
    time.sleep(1)

    with simvue.Run() as run:
        run.reconnect(run_id)
        run.log_metrics({"test_metric": 1})
        run.log_event("Testing!")

    if mode == "offline":
        _id_mapping = sv_send.sender(os.environ["SIMVUE_OFFLINE_DIRECTORY"], 2, 10)

    _reconnected_run = client.get_run(run_id)
    assert dict(_reconnected_run.metrics)["test_metric"]["last"] == 1
    assert client.get_events(run_id)[0]["message"] == "Testing!"

    if temp_d:
        temp_d.cleanup()

