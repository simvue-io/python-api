"""
Low Level API: Run Class
"""

import uuid
import pathlib
import tempfile
import pytest

from simvue.api.objects import Run, FileArtifact, storage
from simvue.api.objects.folder import Folder


@pytest.mark.api
def test_add_artifact_to_run() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _folder = Folder.new(path=f"/simvue_unit_testing/{_uuid}")
    _folder.commit()
    _run = Run.new(folder=f"/simvue_unit_testing/{_uuid}")
    _run.status = "running"
    _run.commit()

    with tempfile.NamedTemporaryFile() as tempf:
        with open(tempf.name, "w") as in_f:
            in_f.write("Hello")

        _artifact = FileArtifact.new(
            name=f"test_{_uuid}",
            storage=None,
            file_path=pathlib.Path(tempf.name),
            mime_type=None,
            metadata=None
        )
        _artifact.attach_to_run(_run.id, "input")
    _run.status = "completed"
    _run.commit()
    assert _run.artifacts
    _run.delete()
    _folder.delete(recursive=True, delete_runs=True)

