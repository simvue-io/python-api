import pytest
import uuid
import time
import pathlib
import tempfile

from simvue.api.objects import Artifact, Run
from simvue.api.objects.folder import Folder

@pytest.mark.api
def test_artifact_creation_online() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _folder_name = f"/simvue_unit_testing/{_uuid}"
    _folder = Folder.new(path=_folder_name)
    _run = Run.new(folder=_folder_name) 
    _folder.commit()
    _run.commit()

    _failed = []

    with tempfile.NamedTemporaryFile(suffix=".txt") as temp_f:
        _path = pathlib.Path(temp_f.name)
        with _path.open("w") as out_f:
            out_f.write("Hello World!")
        _artifact = Artifact.new_file(
            name=f"test_artifact_{_uuid}",
            run=_run.id,
            file_path=_path,
            category="input",
            storage=None,
            file_type=None
        )
        time.sleep(1)
        for member in _artifact._properties:
            try:
                getattr(_artifact, member)
            except Exception as e:
                _failed.append((member, f"{e}"))
        assert _artifact.name == f"test_artifact_{_uuid}"
        _artifact.delete()
    if _failed:
        raise AssertionError("\n" + "\n\t- ".join(": ".join(i) for i in _failed))
    _run.delete()
    _folder.delete()


@pytest.mark.api
def test_artifact_creation_offline() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _folder_name = f"/simvue_unit_testing/{_uuid}"
    _folder = Folder.new(path=_folder_name, offline=True)
    _run = Run.new(folder=_folder_name, offline=True) 

    with tempfile.NamedTemporaryFile(suffix=".txt") as temp_f:
        _path = pathlib.Path(temp_f.name)
        with _path.open("w") as out_f:
            out_f.write("Hello World!")
        _artifact = Artifact.new_file(
            name=f"test_artifact_{_uuid}",
            run=_run.id,
            file_path=_path,
            category="input",
            storage=None,
            file_type=None,
            offline=True
        )
        _folder.commit()
        _run.commit()
        _artifact.commit()
        time.sleep(1)
        assert _artifact.name == f"test_artifact_{_uuid}"
        _artifact.delete()
    _run.delete()
    _folder.delete()


