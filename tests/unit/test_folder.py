import typing
import pytest
import uuid
import contextlib
import json
import time

from simvue.api.objects.folder import Folder

@pytest.mark.api
@pytest.mark.online
def test_folder_creation_online() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _path = f"/simvue_unit_testing/objects/folder/{_uuid}"
    _folder = Folder.new(path=_path)
    _folder.commit()
    assert _folder.id
    assert _folder.path == _path
    assert not _folder.visibility.public
    assert not _folder.visibility.tenant
    assert not _folder.visibility.users
    _folders = Folder.get(count=10)
    assert _folders
    assert _folders[_folder.id]
    assert _folders[_folder.id]._read_only
    with pytest.raises(AssertionError):
        _folders[_folder.id].name = "hello"
    _folder.delete()


@pytest.mark.api
@pytest.mark.offline
def test_folder_creation_offline() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _path = f"/simvue_unit_testing/objects/folder/{_uuid}"
    _folder = Folder.new(path=_path, offline=True)
    _folder.commit()
    assert _folder.id
    assert _folder.path == _path

    with pytest.raises(AttributeError):
        _folder.visibility.public

    _folder.delete()

    with _folder._local_staging_file.open() as in_f:
        _local_data = json.load(in_f)

    assert not _local_data.get(_folder._label, {}).get(_folder.id)


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
    _folder.delete()


@pytest.mark.api
@pytest.mark.offline
def test_folder_modification_offline() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _path = f"/simvue_unit_testing/objects/folder/{_uuid}"
    _description = "Test study"
    _tags = ["testing", "api"]
    _folder = Folder.new(path=_path, offline=True)
    _folder.commit()
    time.sleep(1)
    _folder_new = Folder(identifier=_folder.id)
    _folder_new.tags = _tags
    _folder_new.description = _description
    _folder_new.visibility.tenant = True
    _folder_new.commit()
    assert _folder_new.tags == _tags
    assert _folder.tags == _tags
    assert _folder_new.description == _description
    assert _folder.description == _description
    assert _folder_new.visibility.tenant
    _folder_new.delete()


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
