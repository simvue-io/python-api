import pytest
import os.path
import json
import glob
import time
import tempfile
import simvue.client as svc


@pytest.mark.dependency
def test_get_events(create_test_run: dict) -> None:
    client = svc.Client()
    assert client.get_events(create_test_run["run_id"])


@pytest.mark.dependency
def test_get_alerts(create_test_run: dict) -> None:
    client = svc.Client()
    assert len(client.get_alerts(create_test_run["run_id"], triggered_only=False)) == 5


@pytest.mark.dependency
def test_get_metrics(create_test_run: dict) -> None:
    client = svc.Client()
    time.sleep(4)
    assert (
        len(
            client.get_metrics(
                run_id=create_test_run["run_id"],
                metric_name="metric_counter",
                xaxis="step",
            )
        )
        > 0
    )


@pytest.mark.dependency
def test_get_artifacts(create_test_run: dict) -> None:
    client = svc.Client()
    assert client.list_artifacts(create_test_run["run_id"])
    assert client.get_artifact(create_test_run["run_id"], name="test_attributes")


@pytest.mark.dependency
def test_get_artifact_as_file(create_test_run: dict) -> None:
    with tempfile.TemporaryDirectory() as tempd:
        client = svc.Client()
        client.get_artifact_as_file(create_test_run["run_id"], name="test_attributes", path=tempd)
        assert len(glob.glob(os.path.join(tempd, "*"))) == 1


@pytest.mark.dependency
def test_get_artifacts_as_files(create_test_run: dict) -> None:
    with tempfile.TemporaryDirectory() as tempd:
        client = svc.Client()
        client.get_artifacts_as_files(create_test_run["run_id"], path=tempd)
        assert len(glob.glob(os.path.join(tempd, "*"))) == 2


@pytest.mark.dependency
def test_get_runs(create_test_run: dict) -> None:
    client = svc.Client()
    assert client.get_runs(filters=None)


@pytest.mark.dependency(depends=["test_get_events", "test_get_artifacts", "test_get_artifacts_as_files"])
def test_run_deletion() -> None:
    test_data = json.load(open("test_attrs.json"))
    client = svc.Client()
    assert not client.delete_run(test_data["run_id"])


@pytest.mark.dependency(depends=["test_get_metrics", "test_get_runs", "test_get_artifacts_as_files"])
def test_runs_deletion() -> None:
    test_data = json.load(open("test_attrs.json"))
    client = svc.Client()
    assert len(client.delete_runs(test_data["folder"])) > 0


@pytest.mark.dependency(depends=["test_get_alerts", "test_runs_deletion", "test_get_artifacts_as_files"])
def test_folder_deletion() -> None:
    test_data = json.load(open("test_attrs.json"))
    client = svc.Client()
    # Runs should already have been removed so expect zero length list
    assert not len(client.delete_folder(test_data["folder"], runs=True))
