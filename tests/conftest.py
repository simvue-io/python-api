import contextlib
from _pytest import monkeypatch
from numpy import fix
import pytest
import datetime
import pytest_mock
import typing
import uuid
import time
import tempfile
import os
import json
import pathlib
import logging
import requests

import simvue.eco.api_client as sv_eco
import simvue.run as sv_run
import simvue.api.objects as sv_api_obj
import simvue.config.user as sv_cfg
import simvue.utilities

from simvue.api.objects.artifact import Artifact
from simvue.exception import ObjectNotFoundError

MAX_BUFFER_SIZE: int = 10

def pytest_addoption(parser):
    parser.addoption("--debug-simvue", action="store_true", default=False)
    parser.addoption("--retention-period", default="2 mins")


class CountingLogHandler(logging.Handler):
    def __init__(self, level=logging.DEBUG):
        super().__init__(level)
        self.counts = []
        self.captures = []

    def emit(self, record):
        if len(self.captures) != len(self.counts):
            self.counts = [0] * len(self.captures)

        for i, capture in enumerate(self.captures):
            if capture in record.msg:
                if "resource" in record.msg:
                    print(f"[{i}={self.counts[i]}]: {record.msg}")
                self.counts[i] += 1


def clear_out_files() -> None:
    out_files = list(pathlib.Path.cwd().glob("test_*.out"))
    out_files += list(pathlib.Path.cwd().glob("test_*.err"))

    for file_obj in out_files:
        file_obj.unlink()


@pytest.fixture()
def offline_cache_setup(monkeypatch: monkeypatch.MonkeyPatch):
    # Will be executed before test
    cache_dir = tempfile.TemporaryDirectory()
    monkeypatch.setenv("SIMVUE_OFFLINE_DIRECTORY", cache_dir.name)
    yield cache_dir
    # Will be executed after test
    cache_dir.cleanup()
    monkeypatch.setenv("SIMVUE_OFFLINE_DIRECTORY", None)


@pytest.fixture
def mock_co2_signal(monkeypatch: monkeypatch.MonkeyPatch) -> dict[str, dict | str]:
    _mock_data = {
        "zone":"GB",
        "carbonIntensity":85,
        "datetime":"2025-04-04T12:00:00.000Z",
        "updatedAt":"2025-04-04T11:41:12.947Z",
        "createdAt":"2025-04-01T12:43:58.056Z",
        "emissionFactorType":"lifecycle",
        "isEstimated":True,
        "estimationMethod":"TIME_SLICER_AVERAGE"
    }
    class MockCo2SignalAPIResponse:
        def json(*_, **__) -> dict:
            return _mock_data

        @property
        def status_code(self) -> int:
            return 200

    _req_get = requests.get

    def _mock_get(*args, **kwargs) -> requests.Response:
        if sv_eco.CO2_SIGNAL_API_ENDPOINT in args or kwargs.get("url") == sv_eco.CO2_SIGNAL_API_ENDPOINT:
            return MockCo2SignalAPIResponse()
        else:
            return _req_get(*args, **kwargs)
    def _mock_location_info(self) -> None:
        self._logger.info("📍 Determining current user location.")
        self._latitude: float
        self._longitude: float
        self._latitude, self._longitude = (-1, -1)
        self._two_letter_country_code: str = "GB"

    monkeypatch.setattr(requests, "get", _mock_get)
    monkeypatch.setattr(sv_eco.APIClient, "_get_user_location_info", _mock_location_info)

    _fetch = sv_cfg.SimvueConfiguration.fetch
    @classmethod
    def _mock_fetch(cls, *args, **kwargs) -> sv_cfg.SimvueConfiguration:
        _conf = _fetch(*args, **kwargs)
        _conf.eco.co2_signal_api_token = "test_token"
        _conf.metrics.enable_emission_metrics = True
        return _conf
    monkeypatch.setattr(sv_cfg.SimvueConfiguration, "fetch", _mock_fetch)
    return _mock_data


@pytest.fixture
def speedy_heartbeat(monkeypatch: monkeypatch.MonkeyPatch) -> None:
    monkeypatch.setattr(sv_run, "HEARTBEAT_INTERVAL", 1)


@pytest.fixture(autouse=True)
def setup_logging(pytestconfig, monkeypatch) -> CountingLogHandler:
    logging.basicConfig(level=logging.WARNING)
    handler = CountingLogHandler()
    logging.getLogger("simvue").setLevel(logging.DEBUG if pytestconfig.getoption("debug_simvue") else logging.WARNING)
    logging.getLogger("simvue").addHandler(handler)
    if (_retention := pytestconfig.getoption("retention_period")):
        monkeypatch.setenv("SIMVUE_TESTING_RETENTION_PERIOD", _retention)
    return handler


@pytest.fixture
def log_messages(caplog):
    yield caplog.messages


@pytest.fixture
def prevent_script_exit(monkeypatch: monkeypatch.MonkeyPatch) -> None:
    _orig_func = sv_run.Run._terminate_run
    monkeypatch.setattr(sv_run.Run, "_terminate_run", lambda *args, **kwargs: _orig_func(*args, force_exit=False, **kwargs))


@pytest.fixture
def create_test_run(request, prevent_script_exit) -> typing.Generator[typing.Tuple[sv_run.Run, dict], None, None]:
    with sv_run.Run() as run:
        _test_run_data = setup_test_run(run, True, request)
        yield run, _test_run_data
    with contextlib.suppress(ObjectNotFoundError):
        sv_api_obj.Folder(identifier=run._folder.id).delete(recursive=True, delete_runs=True, runs_only=False)
    for alert_id in _test_run_data.get("alert_ids", []):
        with contextlib.suppress(ObjectNotFoundError):
            sv_api_obj.Alert(identifier=alert_id).delete()
    clear_out_files()


@pytest.fixture
def create_test_run_offline(request, monkeypatch: pytest.MonkeyPatch, prevent_script_exit) -> typing.Generator[typing.Tuple[sv_run.Run, dict], None, None]:
    def testing_exit(status: int) -> None:
        raise SystemExit(status)
    with tempfile.TemporaryDirectory() as temp_d:
        monkeypatch.setenv("SIMVUE_OFFLINE_DIRECTORY", temp_d)
        with sv_run.Run("offline") as run:
            yield run, setup_test_run(run, True, request)
    with contextlib.suppress(ObjectNotFoundError):
        sv_api_obj.Folder(identifier=run._folder.id).delete(recursive=True, delete_runs=True, runs_only=False)
    for alert_id in _test_run_data.get("alert_ids", []):
        with contextlib.suppress(ObjectNotFoundError):
            sv_api_obj.Alert(identifier=alert_id).delete()
    clear_out_files()


@pytest.fixture
def create_plain_run(request, prevent_script_exit, mocker) -> typing.Generator[typing.Tuple[sv_run.Run, dict], None, None]:
    def testing_exit(status: int) -> None:
        raise SystemExit(status)
    with sv_run.Run() as run:
        run.metric_spy = mocker.spy(run, "_get_internal_metrics")
        yield run, setup_test_run(run, False, request)
    clear_out_files()


@pytest.fixture
def create_pending_run(request, prevent_script_exit) -> typing.Generator[typing.Tuple[sv_run.Run, dict], None, None]:
    with sv_run.Run() as run:
        yield run, setup_test_run(run, False, request, True)
    clear_out_files()


@pytest.fixture
def create_plain_run_offline(request,prevent_script_exit,monkeypatch) -> typing.Generator[typing.Tuple[sv_run.Run, dict], None, None]:
    with tempfile.TemporaryDirectory() as temp_d:
        monkeypatch.setenv("SIMVUE_OFFLINE_DIRECTORY", temp_d)
        with sv_run.Run("offline") as run:
            yield run, setup_test_run(run, False, request)
    clear_out_files()


@pytest.fixture(scope="function")
def create_run_object(mocker: pytest_mock.MockFixture) -> sv_api_obj.Run:
    def testing_exit(status: int) -> None:
        raise SystemExit(status)
    _fix_use_id: str = str(uuid.uuid4()).split('-', 1)[0]
    _folder = sv_api_obj.Folder.new(path=f"/simvue_unit_testing/{_fix_use_id}")
    _folder.commit()
    _run = sv_api_obj.Run.new(folder=f"/simvue_unit_testing/{_fix_use_id}")
    yield _run
    _run.delete()
    _folder.delete(recursive=True, runs_only=False, delete_runs=True)


def setup_test_run(run: sv_run.Run, create_objects: bool, request: pytest.FixtureRequest, created_only: bool=False):
    fix_use_id: str = str(uuid.uuid4()).split('-', 1)[0]
    _test_name: str = request.node.name.replace("[", "_").replace("]", "")
    TEST_DATA = {
        "event_contains": "sent event",
        "metadata": {
            "test_engine": "pytest",
            "test_identifier": f"{_test_name}_{fix_use_id}"
        },
        "folder": f"/simvue_unit_testing/{fix_use_id}",
        "tags": ["simvue_client_unit_tests", _test_name]
    }

    if os.environ.get("CI"):
        TEST_DATA["tags"].append("ci")

    run.config(suppress_errors=False)
    run.init(
        name=TEST_DATA['metadata']['test_identifier'],
        tags=TEST_DATA["tags"],
        folder=TEST_DATA["folder"],
        visibility="tenant" if os.environ.get("CI") else None,
        retention_period=os.environ.get("SIMVUE_TESTING_RETENTION_PERIOD", "2 mins"),
        timeout=60,
        no_color=True,
        running=not created_only
    )

    if run._dispatcher:
        run._dispatcher._max_buffer_size = MAX_BUFFER_SIZE

    _alert_ids = []

    if create_objects:
        for i in range(5):
            run.log_event(f"{TEST_DATA['event_contains']} {i}")

        TEST_DATA['created_alerts'] = []


        for i in range(5):
            _aid = run.create_event_alert(
                name=f"test_alert/alert_{i}/{fix_use_id}",
                frequency=1,
                pattern=TEST_DATA['event_contains']
            )
            TEST_DATA['created_alerts'].append(f"test_alert/alert_{i}/{fix_use_id}")
            _alert_ids.append(_aid)

        _ta_id = run.create_metric_threshold_alert(
            name=f'test_alert/value_below_1/{fix_use_id}',
            frequency=1,
            rule='is below',
            threshold=1,
            metric='metric_counter',
            window=2
        )
        _mr_id = run.create_metric_range_alert(
            name=f'test_alert/value_within_1/{fix_use_id}',
            frequency=1,
            rule = "is inside range",
            range_low = 2,
            range_high = 5,
            metric='metric_counter',
            window=2
        )
        _alert_ids += [_ta_id, _mr_id]
        TEST_DATA['created_alerts'] += [
            f"test_alert/value_below_1/{fix_use_id}",
            f"test_alert/value_within_1/{fix_use_id}"
        ]

        for i in range(5):
            run.log_metrics({"metric_counter": i, "metric_val": i*i - 1})

    run.update_metadata(TEST_DATA["metadata"])

    if create_objects:
        TEST_DATA["metrics"] = ("metric_counter", "metric_val")

    TEST_DATA["run_id"] = run.id
    TEST_DATA["run_name"] = run.name
    TEST_DATA["url"] = run._user_config.server.url
    TEST_DATA["headers"] = run._headers
    TEST_DATA["pid"] = run._pid
    TEST_DATA["system_metrics_interval"] = run._system_metrics_interval

    if create_objects:
        with tempfile.TemporaryDirectory() as tempd:
            with open((test_file := os.path.join(tempd, "test_file.txt")), "w") as out_f:
                out_f.write("This is a test file")
            run.save_file(test_file, category="input", name="test_file")
            TEST_DATA["file_1"] = "test_file"

            with open((test_json := os.path.join(tempd, f"test_attrs_{fix_use_id}.json")), "w") as out_f:
                json.dump(TEST_DATA, out_f, indent=2)
            run.save_file(test_json, category="output", name="test_attributes")
            TEST_DATA["file_2"] = "test_attributes"

            with open((test_script := os.path.join(tempd, "test_script.py")), "w") as out_f:
                out_f.write(
                    "print('Hello World!')"
                )
            run.save_file(test_script, category="code", name="test_code_upload")
            TEST_DATA["file_3"] = "test_code_upload"

    TEST_DATA["alert_ids"] = _alert_ids

    return TEST_DATA

