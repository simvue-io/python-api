import pytest
import typing
import uuid
import time
import tempfile
import json
import simvue.run as sv_run

@pytest.fixture
def create_test_run() -> typing.Generator[dict, None, None]:
    with sv_run.Run() as run:
        TEST_DATA = {
            "event_contains": "sent event",
            "metadata": {
                "test_engine": "pytest",
                "test_identifier": str(uuid.uuid4()).split('-', 1)[0]
            },
            "folder": "/simvue_unit_testing"
        }
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
            run.log_metrics({"metric_counter": i})

        run.update_metadata(TEST_DATA["metadata"])

        TEST_DATA["run_id"] = run._id
        TEST_DATA["run_name"] = run._name
        json.dump(TEST_DATA, open("test_attrs.json", "w"), indent=2)

        with tempfile.NamedTemporaryFile(suffix=".txt") as temp_f:
            with open(temp_f.name, "w") as out_f:
                out_f.write("This is a test file")
            run.save(temp_f.name, category="input", name="test_file")

        run.save("test_attrs.json", category="output", name="test_attributes")

        time.sleep(1.)
        yield TEST_DATA
