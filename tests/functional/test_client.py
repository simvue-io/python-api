from logging import critical
import pytest
import uuid
import random
import os.path
import typing
import glob
import pathlib
import time
import pytest_mock
import tempfile
import simvue.client as svc
from simvue.exception import ObjectNotFoundError
import simvue.run as sv_run
import simvue.api.objects as sv_api_obj
from simvue.api.objects.alert.base import AlertBase

@pytest.mark.dependency
@pytest.mark.client
def test_get_events(create_test_run: tuple[sv_run.Run, dict]) -> None:
    client = svc.Client()
    assert client.get_events(run_id=create_test_run[1]["run_id"])


@pytest.mark.dependency
@pytest.mark.client
@pytest.mark.parametrize(
    "from_run", (True, False), ids=("from_run", "all_runs")
)
@pytest.mark.parametrize(
    "names_only", (True, False), ids=("names_only", "all_details")
)
@pytest.mark.parametrize(
    "critical_only", (True, False), ids=("critical_only", "all_states")
)
def test_get_alerts(
    create_plain_run: tuple[sv_run.Run, dict],
    from_run: bool,
    names_only: bool,
    critical_only: bool,
) -> None:
    run, run_data = create_plain_run
    run_id = run.id
    unique_id = f"{uuid.uuid4()}".split("-")[0]
    _id_1 = run.create_user_alert(
        name=f"user_alert_1_{unique_id}", 
    )
    _id_2 = run.create_user_alert(
        name=f"user_alert_2_{unique_id}", 
    )
    _id_3 = run.create_user_alert(
        name=f"user_alert_3_{unique_id}",
        attach_to_run=False
    )
    run.log_alert(identifier=_id_1, state="critical")
    time.sleep(2)
    run.close()
    
    client = svc.Client()

    if critical_only and not from_run:
        with pytest.raises(RuntimeError) as e:
            _alerts = client.get_alerts(critical_only=critical_only, names_only=names_only)
        assert "critical_only is ambiguous when returning alerts with no run ID specified." in str(e.value)
    else:
        sorting = None if run_id else [("name", True), ("created", True)]
        _alerts = client.get_alerts(
            run_id=run_id if from_run else None,
            critical_only=critical_only,
            names_only=names_only,
            sort_by_columns=sorting
        )
    
        if names_only:
            assert all(isinstance(item, str) for item in _alerts)
        else:
            assert all(isinstance(item, AlertBase) for item in _alerts)            
            _alerts = [alert.name for alert in _alerts]
            
        assert f"user_alert_1_{unique_id}" in _alerts
            
        if not from_run:
            assert len(_alerts) > 2
            assert f"user_alert_3_{unique_id}" in _alerts
        else:
            assert f"user_alert_3_{unique_id}" not in _alerts
            if critical_only:
                assert len(_alerts) == 1
            else:
                assert len(_alerts) == 2
                assert f"user_alert_2_{unique_id}" in _alerts
            
@pytest.mark.dependency
@pytest.mark.client
def test_get_run_id_from_name(create_test_run: tuple[sv_run.Run, dict]) -> None:
    client = svc.Client()
    assert (
        client.get_run_id_from_name(create_test_run[1]["run_name"])
        == create_test_run[1]["run_id"]
    )


@pytest.mark.dependency
@pytest.mark.client
@pytest.mark.parametrize(
    "aggregate,use_name_labels",
    [
        (True, False),
        (False, False),
        (False, True)
    ],
    ids=("aggregate", "complete_ids", "complete_labels")
)
def test_get_metric_values(
    create_test_run: tuple[sv_run.Run, dict], aggregate: bool, use_name_labels: bool
) -> None:
    client = svc.Client()
    time.sleep(0.5)
    _metrics_dict = client.get_metric_values(
        run_ids=[create_test_run[1]["run_id"]],
        metric_names=[create_test_run[1]["metrics"][0]],
        xaxis="step",
        use_run_names=use_name_labels,
        aggregate=aggregate,
        output_format="dict",
    )
    assert _metrics_dict
    assert isinstance(_metrics_dict, dict)
    _first_entry: dict = next(iter(_metrics_dict.values()))
    assert create_test_run[1]["metrics"][0] in _metrics_dict.keys()
    if aggregate:
        _value_types = {i[1] for i in _first_entry}
        assert all(
            i in _value_types for i in ("average", "min", "max")
        ), f"Expected ('average', 'min', 'max') in {_value_types}"
    elif not use_name_labels:
        _runs = {i[1] for i in _first_entry}
        assert create_test_run[1]["run_id"] in _runs


@pytest.mark.dependency
@pytest.mark.client
def test_plot_metrics(create_test_run: tuple[sv_run.Run, dict]) -> None:
    try:
        import matplotlib
    except ImportError:
        pytest.skip("Plotting modules not found")

    client = svc.Client()
    client.plot_metrics(
        run_ids=[create_test_run[1]["run_id"]],
        metric_names=list(create_test_run[1]["metrics"]),
        xaxis="time",
    )


@pytest.mark.dependency
@pytest.mark.client
@pytest.mark.parametrize(
    "sorting", ([("metadata.test_identifier", True)], [("name", True), ("created", True)], None),
    ids=("sorted-metadata", "sorted-name-created", None)
)
def test_get_artifacts_entries(create_test_run: tuple[sv_run.Run, dict], sorting: list[tuple[str, bool]] | None) -> None:
    # TODO: Reinstate this test once server bug fixed
    if any("metadata" in a[0] for a in sorting or []):
        pytest.skip(reason="Server bug fix required for metadata sorting.")
    client = svc.Client()
    assert dict(client.list_artifacts(create_test_run[1]["run_id"], sort_by_columns=sorting))
    assert client.get_artifact(create_test_run[1]["run_id"], name="test_attributes")


@pytest.mark.dependency
@pytest.mark.client
@pytest.mark.parametrize("file_id", (1, 2, 3), ids=lambda x: f"file_{x}")
def test_get_artifact_as_file(
    create_test_run: tuple[sv_run.Run, dict], file_id: int
) -> None:
    with tempfile.TemporaryDirectory() as tempd:
        client = svc.Client()
        _file_name = create_test_run[1][f"file_{file_id}"]
        client.get_artifact_as_file(
            create_test_run[1]["run_id"],
            name=_file_name,
            output_dir=tempd,
        )
        assert pathlib.Path(tempd).joinpath(_file_name).exists(), f"Failed to download '{_file_name}'"


@pytest.mark.dependency
@pytest.mark.client
@pytest.mark.parametrize("category", (None, "code", "input", "output"))
def test_get_artifacts_as_files(
    create_test_run: tuple[sv_run.Run, dict],
    category: typing.Literal["code", "input", "output"],
) -> None:
    with tempfile.TemporaryDirectory() as tempd:
        client = svc.Client()
        client.get_artifacts_as_files(
            create_test_run[1]["run_id"], category=category, output_dir=tempd
        )
        files = [os.path.basename(i) for i in glob.glob(os.path.join(tempd, "*"))]
        
        if not category:
            expected_files = ["file_1", "file_2", "file_3"]
        elif category == "input":
            expected_files = ["file_1"]
        elif category == "output":
            expected_files = ["file_2"]
        elif category == "code":
            expected_files = ["file_3"]
            
        for file in ["file_1", "file_2", "file_3"]:
            if file in expected_files:
                assert create_test_run[1][file] in files
            else:
                assert create_test_run[1][file] not in files


@pytest.mark.dependency
@pytest.mark.client
@pytest.mark.parametrize(
    "output_format,sorting",
    [
        ("dict", None),
        ("dataframe", [("created", True), ("started", True)]),
        ("objects", [("metadata.test_identifier", True)]),
    ],
    ids=("dict-unsorted", "dataframe-datesorted", "objects-metasorted")
)
def test_get_runs(create_test_run: tuple[sv_run.Run, dict], output_format: str, sorting: list[tuple[str, bool]] | None) -> None:
    client = svc.Client()

    _result = client.get_runs(filters=None, output_format=output_format, count_limit=10, sort_by_columns=sorting)

    if output_format == "dataframe":
        assert not _result.empty
    else:
        assert _result


@pytest.mark.dependency
@pytest.mark.client
def test_get_run(create_test_run: tuple[sv_run.Run, dict]) -> None:
    client = svc.Client()
    assert client.get_run(run_id=create_test_run[1]["run_id"])


@pytest.mark.dependency
@pytest.mark.client
@pytest.mark.parametrize(
    "sorting", (None, [("metadata.test_identifier", True), ("path", True)], [("modified", False)]),
    ids=("no-sort", "sort-path-metadata", "sort-modified")
)
def test_get_folders(create_test_run: tuple[sv_run.Run, dict], sorting: list[tuple[str, bool]] | None) -> None:
    #TODO: Once server is fixed reinstate this test
    if "modified" in (a[0] for a in sorting or []):
        pytest.skip(reason="Server bug when sorting by 'modified'")
    client = svc.Client()
    assert (folders := client.get_folders(sort_by_columns=sorting))
    _id, _folder = next(folders)
    assert _folder.path
    assert client.get_folder(_folder.path)


@pytest.mark.dependency
@pytest.mark.client
def test_get_metrics_names(create_test_run: tuple[sv_run.Run, dict]) -> None:
    client = svc.Client()
    time.sleep(1)
    assert list(client.get_metrics_names(create_test_run[1]["run_id"]))


@pytest.mark.dependency
@pytest.mark.client
def test_get_tag(create_plain_run: tuple[sv_run.Run, dict]) -> None:
    _, run_data = create_plain_run
    client = svc.Client()
    time.sleep(1.0)
    assert any(tag.name == run_data["tags"][-1] for _, tag in client.get_tags())


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
    "test_get_folder",
    "test_get_tags"
]


@pytest.mark.dependency
@pytest.mark.client(depends=PRE_DELETION_TESTS)
def test_run_deletion(create_test_run: tuple[sv_run.Run, dict]) -> None:
    run, run_data = create_test_run
    run.close()
    client = svc.Client()
    assert not client.delete_run(run_data["run_id"])


@pytest.mark.dependency
@pytest.mark.client(depends=PRE_DELETION_TESTS)
def test_runs_deletion(create_test_run: tuple[sv_run.Run, dict]) -> None:
    run, run_data = create_test_run
    run.close()
    client = svc.Client()
    assert len(client.delete_runs(run_data["folder"])) > 0


@pytest.mark.dependency
@pytest.mark.client(depends=PRE_DELETION_TESTS)
def test_get_tags(create_plain_run: tuple[sv_run.Run, dict]) -> None:
    run, run_data = create_plain_run
    tags = run_data["tags"]
    run.close()
    time.sleep(1.0)
    client = svc.Client()
    retrieved = [t.name for _, t in client.get_tags()]
    assert all(t in retrieved for t in tags)


@pytest.mark.dependency
@pytest.mark.client(depends=PRE_DELETION_TESTS + ["test_runs_deletion"])
def test_folder_deletion(create_test_run: tuple[sv_run.Run, dict]) -> None:
    run, run_data = create_test_run
    run.close()
    client = svc.Client()
    # This test is called last, one run created so expect length 1
    assert len(client.delete_folder(run_data["folder"], remove_runs=True)) == 1
    assert not client.get_folder(run_data["folder"])


@pytest.mark.client
def test_run_folder_metadata_find(create_plain_run: tuple[sv_run.Run, dict]) -> None:
    run, run_data = create_plain_run
    rand_val = random.randint(0, 1000)
    run.set_folder_details(metadata={'atest': rand_val})
    run.close()
    time.sleep(1.0)
    client = svc.Client()
    data = client.get_folders(filters=[f'metadata.atest == {rand_val}'])

    assert run_data["folder"] in [i.path for _, i in data]


@pytest.mark.client
def test_tag_deletion(create_plain_run: tuple[sv_run.Run, dict]) -> None:
    run, run_data = create_plain_run
    unique_id = f"{uuid.uuid4()}".split("-")[0]
    run.update_tags([f"delete_me_{unique_id}"])
    run.close()
    time.sleep(1.0)
    client = svc.Client()
    tags = client.get_tags()
    client.delete_run(run.id)
    time.sleep(1.0)
    tag_identifier = [identifier for identifier, tag in tags if tag.name == f"delete_me_{unique_id}"][0]
    client.delete_tag(tag_identifier)
    time.sleep(1.0)
    assert not client.get_tag(tag_identifier)


@pytest.mark.dependency
@pytest.mark.client
@pytest.mark.parametrize("aggregate", (True, False), ids=("aggregated", "normal"))
@pytest.mark.parametrize("output_format", ("dict", "dataframe"))
@pytest.mark.parametrize("xaxis", ("step", "time", "timestamp"))
def test_multiple_metric_retrieval(
    create_test_run: tuple[sv_run.Run, dict],
    aggregate: bool,
    output_format: typing.Literal["dict", "dataframe"],
    xaxis: typing.Literal["step", "time", "timestamp"],
) -> None:
    client = svc.Client()
    if output_format == "dataframe":
        try:
            import pandas
        except ImportError:
            pytest.skip(reason="Pandas not available")

    if aggregate and xaxis == "timestamp":
        with pytest.raises(AssertionError):
            client.get_metric_values(
                run_ids=[create_test_run[1]["run_id"]],
                metric_names=list(create_test_run[1]["metrics"]),
                xaxis=xaxis,
                aggregate=aggregate,
                output_format=output_format,
            )
        return

    client.get_metric_values(
        run_ids=[create_test_run[1]["run_id"]],
        metric_names=list(create_test_run[1]["metrics"]),
        xaxis=xaxis,
        aggregate=aggregate,
        output_format=output_format,
    )


@pytest.mark.client
def test_alert_deletion() -> None:
    _alert = sv_api_obj.UserAlert.new(name="test_alert", notification="none", description=None)
    _alert.commit()
    _client = svc.Client()
    time.sleep(1)
    _client.delete_alert(alert_id=_alert.id)

    with pytest.raises(ObjectNotFoundError) as e:
        sv_api_obj.Alert(identifier=_alert.id)


@pytest.mark.client
def test_abort_run(create_plain_run: tuple[sv_run.Run, dict]) -> None:
    run, run_data = create_plain_run
    _uuid = f"{uuid.uuid4()}".split("-")[0]
    run.update_tags([f"delete_me_{_uuid}"])
    time.sleep(1)
    _client = svc.Client()
    _client.abort_run(run.id, reason="Test abort")
    time.sleep(1)
    assert run._status == "terminated"


