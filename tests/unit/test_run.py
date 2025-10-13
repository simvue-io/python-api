import contextlib
import json
import pytest
import time
import datetime
import uuid
from simvue.api.objects.run import RunBatchArgs
from simvue.sender import sender
from simvue.api.objects import Run, Folder
from simvue.client import Client

@pytest.mark.api
@pytest.mark.online
def test_run_creation_online() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _folder_name = f"/simvue_unit_testing/{_uuid}"
    _folder = Folder.new(path=_folder_name)
    _run = Run.new(folder=_folder_name)
    _folder.commit()
    _run.commit()
    assert _run.folder == _folder_name
    _run.delete()
    _folder.delete(recursive=True, delete_runs=True, runs_only=False)


@pytest.mark.api
@pytest.mark.offline
def test_run_creation_offline(offline_cache_setup) -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _run_name = f"simvue_offline_run_{_uuid}"
    _folder_name = f"/simvue_unit_testing/{_uuid}"
    _folder = Folder.new(path=_folder_name, offline=True)
    _run = Run.new(name=_run_name,folder=_folder_name, offline=True)
    _folder.commit()
    _run.commit()
    assert _run.name == _run_name
    assert _run.folder == _folder_name

    with _run._local_staging_file.open() as in_f:
        _local_data = json.load(in_f)
    assert _local_data.get("name") == f"simvue_offline_run_{_uuid}"
    assert _local_data.get("folder") == _folder_name

    sender(_run._local_staging_file.parents[1], 1, 10, ["folders", "runs"], throw_exceptions=True)
    time.sleep(1)

    # Get online ID and retrieve run
    _online_id = _run._local_staging_file.parents[1].joinpath("server_ids", f"{_run._local_staging_file.name.split('.')[0]}.txt").read_text()
    _online_run = Run(_online_id)

    assert _online_run.name == _run_name
    assert _online_run.folder == _folder_name

    _run.delete()
    _run._local_staging_file.parents[1].joinpath("server_ids", f"{_run._local_staging_file.name.split('.')[0]}.txt").unlink()
    client = Client()
    client.delete_folder(_folder_name, recursive=True, remove_runs=True)

@pytest.mark.api
@pytest.mark.online
def test_run_modification_online() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _folder_name = f"/simvue_unit_testing/{_uuid}"
    _folder = Folder.new(path=_folder_name)
    _run = Run.new(folder=_folder_name)
    _folder.commit()
    _run.commit()
    assert _run.folder == _folder_name
    time.sleep(1)
    _now = datetime.datetime.now()
    _new_run = Run(identifier=_run.id)
    assert _new_run.status == "created"
    _new_run.read_only(False)
    _new_run.status = "running"
    _new_run.name = "simvue_test_run"
    _new_run.description = "Simvue test run"
    _new_run.tags = ["simvue", "test", "tag"]
    _new_run.ttl = 120
    assert _new_run.ttl != 120
    _new_run.commit()
    time.sleep(1)
    assert _run.ttl == 120
    assert _run.description == "Simvue test run"
    assert sorted(_run.tags) == sorted(["simvue", "test", "tag"])
    assert _run.name == "simvue_test_run"
    assert _run.status == "running"
    _run.abort("test_run_abort")
    assert _new_run.abort_trigger
    _run.delete()
    _folder.delete(recursive=True, delete_runs=True, runs_only=False)


@pytest.mark.api
@pytest.mark.offline
def test_run_modification_offline(offline_cache_setup) -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _run_name = f"simvue_offline_run_{_uuid}"
    _folder_name = f"/simvue_unit_testing/{_uuid}"
    _folder = Folder.new(path=_folder_name, offline=True)
    _run = Run.new(name=_run_name, folder=_folder_name, offline=True)
    _folder.commit()
    _run.commit()
    assert _run.name == _run_name
    assert _run.folder == _folder_name
    time.sleep(1)
    _new_run = Run(identifier=_run.id, offline=True)
    # Property has not been committed to offline
    # object so not yet available
    with pytest.raises(AttributeError):
        _new_run.ttl
    _new_run.read_only(False)
    _new_run.name = "simvue_test_run"
    _new_run.description = "Simvue test run"
    _new_run.ttl = 120

    _new_run.commit()

    assert _new_run.ttl == 120
    assert _new_run.description == "Simvue test run"
    assert _new_run.name == "simvue_test_run"

    sender(_run._local_staging_file.parents[1], 1, 10, ["folders", "runs"], throw_exceptions=True)
    time.sleep(1)

    # Get online ID and retrieve run
    _online_id = _run._local_staging_file.parents[1].joinpath("server_ids", f"{_run._local_staging_file.name.split('.')[0]}.txt").read_text()
    _online_run = Run(_online_id)

    assert _online_run.ttl == 120
    assert _online_run.description == "Simvue test run"
    assert _online_run.name == "simvue_test_run"
    assert _online_run.folder == _folder_name

    # Now add a new set of tags in offline mode and send
    _new_run.tags = ["simvue", "test", "tag"]
    _new_run.commit()

    # Shouldn't yet be available in the online run since it hasnt been sent
    _online_run.refresh()
    assert _online_run.tags == []

    sender(_run._local_staging_file.parents[1], 1, 10, ["folders", "runs"], throw_exceptions=True)
    time.sleep(1)

    _online_run.refresh()
    assert sorted(_new_run.tags) == sorted(["simvue", "test", "tag"])
    assert sorted(_online_run.tags) == sorted(["simvue", "test", "tag"])

    _run.delete()
    _run._local_staging_file.parents[1].joinpath("server_ids", f"{_run._local_staging_file.name.split('.')[0]}.txt").unlink()
    client = Client()
    client.delete_folder(_folder_name, recursive=True, remove_runs=True)


@pytest.mark.api
@pytest.mark.online
def test_get_run_count() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _folder_name = f"/simvue_unit_testing/{_uuid}"
    _folder = Folder.new(path=_folder_name)
    _run_1 = Run.new(folder=_folder_name)
    _run_2 = Run.new(folder=_folder_name)
    assert len(list(Run.get(count=2, offset=None))) == 2


@pytest.mark.api
@pytest.mark.online
def test_run_get_properties() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _folder_name = f"/simvue_unit_testing/{_uuid}"
    _folder = Folder.new(path=_folder_name)
    _run = Run.new(name="test_run_get_properties", folder=_folder_name)
    _run.status = "running"
    _run.ttl = 60
    _folder.commit()
    _run.commit()
    _failed = []
    assert _run.to_dict()

    for member in _run._properties:
        try:
            getattr(_run, member)
        except Exception as e:
            _failed.append((member, f"{e}"))
    with contextlib.suppress(Exception):
        _run.delete()
        _folder.delete()

    if _failed:
        raise AssertionError("\n" + "\n\t- ".join(": ".join(i) for i in _failed))


@pytest.mark.api
@pytest.mark.online
def test_batch_run_creation() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _folder: Folder = Folder.new(path=f"/simvue_unit_testing/{_uuid}")
    _folder.commit()
    _runs = [
        RunBatchArgs(name=f"batched_run_{i}")
        for i in range(10)
    ]
    _counter: int = 0
    for i, _id in enumerate(Run.batch_create(entries=_runs, folder=f"/simvue_unit_testing/{_uuid}", metadata={"batch_id": 0})):
        _run = Run(identifier=_id)
        assert _run.name == f"batched_run_{i}"
        assert _run.metadata["batch_id"] == 0
        _counter +=1
    assert _counter == 10
    with contextlib.suppress(Exception):
        _folder.delete(recursive=True, delete_runs=True)
