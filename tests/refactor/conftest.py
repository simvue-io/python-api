import pytest
import typing
import uuid
import time
import tempfile
import json
import pathlib
import simvue.run as sv_run


@pytest.fixture
def create_test_run() -> typing.Generator[typing.Tuple[sv_run.Run, dict], None, None]:
    with sv_run.Run() as run:
        yield run, setup_test_run(run)


@pytest.fixture
def create_test_run_offline() -> typing.Generator[typing.Tuple[sv_run.Run, dict], None, None]:
    with sv_run.Run("offline") as run:
        yield run, setup_test_run(run)

def setup_test_run(run: sv_run.Run):
    TEST_DATA = {
        "event_contains": "sent event",
        "metadata": {
            "test_engine": "pytest",
            "test_identifier": str(uuid.uuid4()).split('-', 1)[0]
        },
        "folder": "/simvue_unit_testing"
    }
    run.config(suppress_errors=False)
    run.init(
        name=f"test_run_{TEST_DATA['metadata']['test_identifier']}",
        tags=["simvue_client_unit_tests"],
        folder=TEST_DATA["folder"]
    )
    for i in range(5):
        run.log_event(f"{TEST_DATA['event_contains']} {i}")

    for i in range(5):
        run.add_alert(name=f"alert_{i}", source="events", frequency=1, pattern=TEST_DATA['event_contains'])

    for i in range(5):
        run.log_metrics({"metric_counter": i, "metric_val": i*i - 1})

    run.update_metadata(TEST_DATA["metadata"])

    TEST_DATA["metrics"] = ("metric_counter", "metric_val")
    TEST_DATA["run_id"] = run._id
    TEST_DATA["run_name"] = run._name
    TEST_DATA["url"] = run._url
    TEST_DATA["headers"] = run._headers
    TEST_DATA["pid"] = run._pid
    TEST_DATA["resources_metrics_interval"] = run._resources_metrics_interval
    json.dump(TEST_DATA, open("test_attrs.json", "w"), indent=2)

    with tempfile.NamedTemporaryFile(suffix=".txt") as temp_f:
        with open(temp_f.name, "w") as out_f:
            out_f.write("This is a test file")
        run.save(temp_f.name, category="input", name="test_file")
        TEST_DATA["file_1"] = "test_file"

    run.save("test_attrs.json", category="output", name="test_attributes")
    TEST_DATA["file_2"] = "test_attributes"

    with tempfile.NamedTemporaryFile(suffix=".py") as temp_f:
        pathlib.Path(temp_f.name).touch()
        run.save(temp_f.name, category="code", name="test_script")
        TEST_DATA["file_3"] = "test_script"

    time.sleep(1.)
    return TEST_DATA
