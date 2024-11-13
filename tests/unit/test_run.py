import pytest
import time
import datetime
import uuid

from simvue.api.objects import Run, Folder

@pytest.mark.api
def test_run_creation() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _folder_name = f"/simvue_unit_testing/{_uuid}"
    _folder = Folder.new(path=_folder_name)
    _run = Run.new(folder=_folder_name)
    _folder.commit()
    _run.commit()
    assert _run.folder == _folder_name
    _run.delete()
    _folder.delete()


@pytest.mark.api
def test_run_modification() -> None:
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
    _new_run.name = "simvue_test_run"
    _new_run.description = "Simvue test run"
    _new_run.created = _now
    _new_run.tags = ["simvue", "test", "tag"]
    _new_run.ttl = 120
    assert _new_run.ttl != 120
    _new_run.commit()
    assert _new_run.ttl == 120
    assert _new_run.description == "Simvue test run"
    assert _new_run.created == _now
    assert sorted(_new_run.tags) == sorted(["simvue", "test", "tag"])
    assert _new_run.name == "simvue_test_run"
    _run.delete()
    _folder.delete()

