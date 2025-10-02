import contextlib
import pytest
import os
import uuid
import time
import pathlib
import tempfile
import json
from simvue.api.objects import FileArtifact, Run, Artifact
from simvue.api.objects.folder import Folder
from simvue.sender import sender
from simvue.client import Client
import logging

@pytest.mark.api
@pytest.mark.online
@pytest.mark.parametrize(
    "snapshot",
    (True, False)
)
def test_file_artifact_creation_online(offline_cache_setup, snapshot) -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _folder_name = f"/simvue_unit_testing/{_uuid}"
    _folder = Folder.new(path=_folder_name)
    _run = Run.new(folder=_folder_name) 
    _folder.commit()
    _run.commit()

    _failed = []

    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as temp_f:
        _path = pathlib.Path(temp_f.name)
        with _path.open("w") as out_f:
            out_f.write(f"Hello World! {_uuid}")
        _artifact = FileArtifact.new(
            name=f"test_file_artifact_{_uuid}",
            file_path=_path,
            storage=None,
            mime_type=None,
            metadata=None,
            snapshot=snapshot
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
        
        # If snapshotting, check no local copy remains
        if snapshot:
            assert len(list(_artifact._local_staging_file.parent.iterdir())) == 0

    _run.delete()
    _folder.delete(recursive=True, delete_runs=True, runs_only=False)
    with contextlib.suppress(FileNotFoundError):
        os.unlink(temp_f.name)
    if _failed:
        raise AssertionError("\n\t-" + "\n\t- ".join(": ".join(i) for i in _failed))


@pytest.mark.api
@pytest.mark.offline
@pytest.mark.parametrize(
    "snapshot",
    (True, False)
)
def test_file_artifact_creation_offline(offline_cache_setup, snapshot) -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _folder_name = f"/simvue_unit_testing/{_uuid}"
    _folder = Folder.new(path=_folder_name, offline=True)
    _run = Run.new(name=f"test_file_artifact_creation_offline_{_uuid}",folder=_folder_name, offline=True) 

    _path = pathlib.Path(offline_cache_setup.name).joinpath("hello_world.txt")

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
        metadata=None,
        snapshot=snapshot
    )
    _artifact.attach_to_run(_run._identifier, category="input")
    
    with _artifact._local_staging_file.open() as in_f:
        _local_data = json.load(in_f)
        
    assert _local_data.get("name") == f"test_file_artifact_{_uuid}"
    assert _local_data.get("runs") == {_run._identifier: "input"}
    
    # If snapshot, check artifact definition file and a copy of the actual file exist in staging area
    assert len(list(_artifact._local_staging_file.parent.iterdir())) == 2 if snapshot else 1
    
    _id_mapping = sender(pathlib.Path(offline_cache_setup.name), 1, 10)
    time.sleep(1)
    
    # Check file(s) deleted after upload
    assert len(list(_artifact._local_staging_file.parent.iterdir())) == 0
    
    _online_artifact = Artifact(_id_mapping[_artifact.id])
    assert _online_artifact.name == _artifact.name
    _content = b"".join(_online_artifact.download_content()).decode("UTF-8")
    assert _content == f"Hello World! {_uuid}"
    _run.delete()
    _folder.delete()
    
    
@pytest.mark.api
@pytest.mark.offline
@pytest.mark.parametrize(
    "snapshot",
    (True, False)
)
def test_file_artifact_creation_offline_updated(offline_cache_setup, caplog, snapshot) -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _folder_name = f"/simvue_unit_testing/{_uuid}"
    _folder = Folder.new(path=_folder_name, offline=True)
    _run = Run.new(name=f"test_file_artifact_creation_offline_updated_{_uuid}",folder=_folder_name, offline=True) 

    _path = pathlib.Path(offline_cache_setup.name).joinpath("hello_world.txt")

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
        metadata=None,
        snapshot=snapshot
    )
    _artifact.attach_to_run(_run._identifier, category="input")
    
    with _artifact._local_staging_file.open() as in_f:
        _local_data = json.load(in_f)
        
    assert _local_data.get("name") == f"test_file_artifact_{_uuid}"
    assert _local_data.get("runs") == {_run._identifier: "input"}
    
    # Change the file after the artifact is created, but before it is sent
    with _path.open("w") as out_f:
        out_f.write("File changed!")
    
    if not snapshot:
        with caplog.at_level(logging.ERROR): 
            _id_mapping = sender(pathlib.Path(offline_cache_setup.name), 1, 10)
        assert "The SHA256 you specified did not match the calculated checksum." in caplog.text
        return
    else:
        _id_mapping = sender(pathlib.Path(offline_cache_setup.name), 1, 10)
    time.sleep(1)
    
    _online_artifact = Artifact(_id_mapping[_artifact.id])
    assert _online_artifact.name == _artifact.name
    _content = b"".join(_online_artifact.download_content()).decode("UTF-8")
    # Since it was snapshotted, should be the state of the file before it was changed
    assert _content == f"Hello World! {_uuid}"
    _run.delete()
    _folder.delete()

