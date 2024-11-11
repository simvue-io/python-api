import typing
import pytest
import uuid
import time

from simvue.api.objects.folder import Folder

@pytest.mark.api
def test_folder_creation() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _path = f"/simvue_unit_testing/objects/folder/{_uuid}"
    _folder = Folder.new(path=_path)
    assert _folder.id
    assert _folder.path == _path
    assert not _folder.visibility.public
    assert not _folder.visibility.tenant
    assert not _folder.visibility.users


@pytest.mark.api(depends=["test_folder_creation"])
def test_folder_modification() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _path = f"/simvue_unit_testing/objects/folder/{_uuid}"
    _description = "Test study"
    _tags = ["testing", "api"]
    _folder = Folder.new(path=_path)
    time.sleep(1)
    _folder_new = Folder(identifier=_folder.id)
    _folder_new.tags = _tags
    _folder_new.description = _description
    _folder_new.visibility.tenant = True
    assert _folder_new.tags == _tags
    assert _folder.tags == _tags
    assert _folder_new.description == _description
    assert _folder.description == _description
    assert _folder_new.visibility.tenant

