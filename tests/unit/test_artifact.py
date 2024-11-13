import pytest
import uuid
import time
import pathlib
import tempfile

from simvue.api.objects import Artifact, Run
from simvue.api.objects.folder import Folder

@pytest.mark.api
def test_artifact_creation() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _folder_name = f"/simvue_unit_testing/{_uuid}"
    _folder = Folder.new(path=_folder_name)
    _run = Run.new(folder=_folder_name) 

    with tempfile.NamedTemporaryFile(suffix=".txt") as temp_f:
        _path = pathlib.Path(temp_f.name)
        with _path.open("w") as out_f:
            out_f.write("Hello World!")
        _artifact = Artifact.new(
            name=f"test_artifact_{_uuid}",
            run=_run.id,
            file_path=_path,
            category="input",
            storage=None,
            file_type=None
        )
        _artifact.commit()
        time.sleep(1)
        assert _artifact.name == f"test_artifact_{_uuid}"
        _artifact.delete()
    _run.delete()
    _folder.delete()
