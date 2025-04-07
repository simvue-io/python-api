import typing
import pytest
import uuid
import contextlib
import json
import time
import os

from simvue.api.objects.folder import Folder
from simvue.sender import sender
from simvue.client import Client
@pytest.mark.api
@pytest.mark.online
def test_folder_creation_online() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _path = f"/simvue_unit_testing/objects/folder/{_uuid}"
    _folder = Folder.new(path=_path)
    _folder.commit()
    assert _folder.id
    assert _folder.path == _path
    _folders = dict(Folder.get(count=10))
    assert _folders
    assert _folders[_folder.id]
    assert _folders[_folder.id]._read_only
    assert _folder.to_dict()
    with pytest.raises(AssertionError):
        _folders[_folder.id].name = "hello"
    _folder.delete(recursive=True, delete_runs=True, runs_only=False)


@pytest.mark.api
@pytest.mark.offline
def test_folder_creation_offline() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _path = f"/simvue_unit_testing/objects/folder/{_uuid}"
    _folder = Folder.new(path=_path, offline=True)
    _folder.commit()

    with _folder._local_staging_file.open() as in_f:
        _local_data = json.load(in_f)

    assert  _folder._local_staging_file.name.split(".")[0] == _folder.id
    assert _local_data.get("path", None) == _path

    sender(_folder._local_staging_file.parents[1], 2, 10, ["folders"])
    time.sleep(1)
    client = Client()

    _folder_new = client.get_folder(_path)
    assert _folder_new.path == _path

    _folder_new.delete()

    assert not _folder._local_staging_file.exists()


@pytest.mark.api
@pytest.mark.online
def test_get_folder_count() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _folder_name = f"/simvue_unit_testing/{_uuid}"
    _folder_1 = Folder.new(path=f"{_folder_name}/dir_1")
    _folder_2 = Folder.new(path=f"{_folder_name}/dir_2")
    assert len(list(Folder.get(count=2, offset=None))) == 2


@pytest.mark.api
@pytest.mark.online
def test_folder_modification_online() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _path = f"/simvue_unit_testing/objects/folder/{_uuid}"
    _description = "Test study"
    _tags = ["testing", "api"]
    _folder = Folder.new(path=_path)
    _folder.commit()
    time.sleep(1)
    _folder_new = Folder(identifier=_folder.id)
    _folder_new.read_only(False)
    _folder_new.tags = _tags
    _folder_new.description = _description
    _folder_new.commit()
    assert _folder_new.tags == _tags
    assert _folder.tags == _tags
    assert _folder_new.description == _description
    assert _folder.description == _description
    _folder.delete(recursive=True, delete_runs=True, runs_only=False)


@pytest.mark.api
@pytest.mark.offline
def test_folder_modification_offline() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _path = f"/simvue_unit_testing/objects/folder/{_uuid}"
    _description = "Test study"
    _tags = ["testing", "api"]
    _folder = Folder.new(path=_path, offline=True)
    _folder.commit()

    sender(_folder._local_staging_file.parents[1], 2, 10, ["folders"])
    time.sleep(1)

    client = Client()
    _folder_online = client.get_folder(_path)
    assert _folder_online.path == _path

    _folder_new = Folder(identifier=_folder.id)
    _folder_new.read_only(False)
    _folder_new.tags = _tags
    _folder_new.description = _description
    _folder_new.commit()

    with _folder._local_staging_file.open() as in_f:
        _local_data = json.load(in_f)
    assert  _folder._local_staging_file.name.split(".")[0] == _folder.id
    assert _local_data.get("description", None) == _description
    assert _local_data.get("tags", None) == _tags

    sender(_folder._local_staging_file.parents[1], 2, 10, ["folders"])
    time.sleep(1)

    _folder_online.refresh()
    assert _folder_online.path == _path
    assert _folder_online.description == _description
    assert _folder_online.tags == _tags

    _folder_online.read_only(False)
    _folder_online.delete()


@pytest.mark.api
@pytest.mark.online
def test_folder_get_properties() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _path = f"/simvue_unit_testing/objects/folder/{_uuid}"
    _folder = Folder.new(path=_path)
    _folder.commit()

    _failed = []

    for member in _folder._properties:
        try:
            getattr(_folder, member)
        except Exception as e:
            _failed.append((member, f"{e}"))
    with contextlib.suppress(Exception):
        _folder.delete()

    if _failed:
        raise AssertionError("\n" + "\n\t- ".join(": ".join(i) for i in _failed))
