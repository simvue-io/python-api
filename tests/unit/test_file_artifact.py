import pytest
import uuid
import time
import pathlib
import tempfile
import json
from simvue.api.objects import FileArtifact, Run, Artifact
from simvue.api.objects.folder import Folder
from simvue.sender import sender
from simvue.client import Client

@pytest.mark.api
@pytest.mark.online
def test_file_artifact_creation_online() -> None:
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
            out_f.write(f"Hello World! {_uuid}")
        _artifact = FileArtifact.new(
            name=f"test_file_artifact_{_uuid}",
            file_path=_path,
            storage=None,
            mime_type=None,
            metadata=None
        )
        _artifact.attach_to_run(_run.id, "input")
        time.sleep(1)
        for member in _artifact._properties:
            try:
                getattr(_artifact, member)
            except Exception as e:
                _failed.append((member, f"{e}"))
        assert _artifact.name == f"test_file_artifact_{_uuid}"
        _content = b"".join(_artifact.download_content()).decode("UTF-8")
        assert _content == f"Hello World! {_uuid}"
        assert _artifact.to_dict()
    _run.delete()
    _folder.delete(recursive=True, delete_runs=True, runs_only=False)
    if _failed:
        raise AssertionError("\n\t-" + "\n\t- ".join(": ".join(i) for i in _failed))


@pytest.mark.api
@pytest.mark.offline
def test_file_artifact_creation_offline(offline_test: pathlib.Path) -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _folder_name = f"/simvue_unit_testing/{_uuid}"
    _folder = Folder.new(path=_folder_name, offline=True)
    _run = Run.new(name=f"test_file_artifact_creation_offline_{_uuid}",folder=_folder_name, offline=True) 

    _path = offline_test.joinpath("hello_world.txt")

    with _path.open("w") as out_f:
        out_f.write(f"Hello World! {_uuid}")

    _folder.commit()
    _run.commit()
    _artifact = FileArtifact.new(
        name=f"test_file_artifact_{_uuid}",
        file_path=_path,
        storage=None,
        mime_type=None,
        offline=True,
        metadata=None
    )
    _artifact.attach_to_run(_run._identifier, category="input")
    
    with _artifact._local_staging_file.open() as in_f:
        _local_data = json.load(in_f)
        
    assert _local_data.get("name") == f"test_file_artifact_{_uuid}"
    assert _local_data.get("runs") == {_run._identifier: "input"}
    
    _id_mapping = sender(offline_test.joinpath(".simvue"), 1, 10)
    time.sleep(1)
    
    _online_artifact = Artifact(_id_mapping[_artifact.id])
    assert _online_artifact.name == _artifact.name
    _content = b"".join(_online_artifact.download_content()).decode("UTF-8")
    assert _content == f"Hello World! {_uuid}"
    _run.delete()
    _folder.delete()

