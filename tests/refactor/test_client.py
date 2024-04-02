import pytest
import os.path
import json
import glob
import time
import tempfile
import simvue.client as svc


@pytest.mark.dependency
@pytest.mark.client
def test_get_events(create_test_run: dict) -> None:
    client = svc.Client()
    assert client.get_events(create_test_run["run_id"])


@pytest.mark.dependency
@pytest.mark.client
def test_get_alerts(create_test_run: dict) -> None:
    client = svc.Client()
    assert len(client.get_alerts(create_test_run["run_id"], critical_only=False)) == 5


@pytest.mark.dependency
@pytest.mark.client
def test_get_run_id_from_name(create_test_run: dict) -> None:
    client = svc.Client()
    assert client.get_run_id_from_name(create_test_run["run_name"]) == create_test_run["run_id"]


@pytest.mark.dependency
@pytest.mark.client
def test_get_metrics(create_test_run: dict) -> None:
    client = svc.Client()
    time.sleep(4)
    assert (
        len(
            client.get_metrics(
                run_id=create_test_run["run_id"],
                metric_name=create_test_run["metrics"][0],
                xaxis="step",
            )
        )
        > 0
    )


@pytest.mark.dependency
@pytest.mark.client
@pytest.mark.parametrize(
    "aggregate", (True, False),
    ids=("aggregated", "normal")
)
@pytest.mark.parametrize(
    "format", ("list", "dataframe")
)
def test_multiple_metric_retrieval(create_test_run: dict, aggregate: bool, format: str) -> None:
    client = svc.Client()
    if format == "dataframe":
        try:
            import pandas 
        except ImportError:
            pytest.skip(reason="Pandas not available")
    client.get_metrics_multiple(
        run_ids=[create_test_run["run_id"]],
        metric_names=list(create_test_run["metrics"]),
        xaxis="time",
        aggregate=aggregate,
        format=format
    )


@pytest.mark.dependency
@pytest.mark.client
def test_plot_metrics(create_test_run: dict) -> None:
    try:
        import matplotlib
    except ImportError:
        pytest.skip("Plotting modules not found")
    
    client = svc.Client()
    client.plot_metrics(
        run_ids=[create_test_run["run_id"]],
        metric_names=list(create_test_run["metrics"]),
        xaxis="time"
    )


@pytest.mark.dependency
@pytest.mark.client
def test_get_artifacts(create_test_run: dict) -> None:
    client = svc.Client()
    assert client.list_artifacts(create_test_run["run_id"])
    assert client.get_artifact(create_test_run["run_id"], name="test_attributes")


@pytest.mark.dependency
@pytest.mark.client
@pytest.mark.parametrize(
    "file_id", (1, 2, 3),
    ids=lambda x: f"file_{x}"
)
def test_get_artifact_as_file(create_test_run: dict, file_id: int) -> None:
    with tempfile.TemporaryDirectory() as tempd:
        client = svc.Client()
        client.get_artifact_as_file(create_test_run["run_id"], name=create_test_run[f"file_{file_id}"], path=tempd)
        assert create_test_run[f"file_{file_id}"] in [os.path.basename(i) for i in glob.glob(os.path.join(tempd, "*"))]


@pytest.mark.dependency
@pytest.mark.client
def test_get_artifacts_as_files(create_test_run: dict) -> None:
    with tempfile.TemporaryDirectory() as tempd:
        client = svc.Client()
        client.get_artifacts_as_files(create_test_run["run_id"], path=tempd)
        files = [os.path.basename(i) for i in glob.glob(os.path.join(tempd, "*"))]
        assert create_test_run["file_1"] in files
        assert create_test_run["file_2"] in files


@pytest.mark.dependency
@pytest.mark.client
def test_get_runs(create_test_run: dict) -> None:
    client = svc.Client()
    assert client.get_runs(filters=None)


@pytest.mark.dependency
@pytest.mark.client
def test_get_run(create_test_run: dict) -> None:
    client = svc.Client()
    assert client.get_run(run_id=create_test_run["run_id"])


@pytest.mark.dependency
@pytest.mark.client
def test_get_folder(create_test_run: dict) -> None:
    client = svc.Client()
    assert (folders := client.get_folders())
    assert (folder_id := folders[0].get("id"))
    assert client.get_folder(folder_id)


@pytest.mark.dependency
@pytest.mark.client
def test_get_metrics_names(create_test_run: dict) -> None:
    client = svc.Client()
    time.sleep(1)
    assert client.get_metrics_names(create_test_run["run_id"])


PRE_DELETION_TESTS: list[str] = [
    "test_get_metrics",
    "test_get_runs",
    "test_get_run",
    "test_get_artifact_as_file",
    "test_get_artifacts_as_files",
    "test_get_folders",
    "test_get_metrics_names",
    "test_get_metrics_multiple",
    "test_plot_metrics",
    "test_get_run_id_from_name",
    "test_get_folder"
]

@pytest.mark.dependency
@pytest.mark.client(depends=PRE_DELETION_TESTS)
def test_run_deletion() -> None:
    test_data = json.load(open("test_attrs.json"))
    client = svc.Client()
    assert not client.delete_run(test_data["run_id"])


@pytest.mark.dependency
@pytest.mark.client(depends=PRE_DELETION_TESTS)
def test_runs_deletion() -> None:
    test_data = json.load(open("test_attrs.json"))
    client = svc.Client()
    assert len(client.delete_runs(test_data["folder"])) > 0


@pytest.mark.dependency
@pytest.mark.client(depends=PRE_DELETION_TESTS)
def test_folder_deletion() -> None:
    test_data = json.load(open("test_attrs.json"))
    client = svc.Client()
    # Runs should already have been removed so expect zero length list
    assert not len(client.delete_folder(test_data["folder"], remove_runs=True))
