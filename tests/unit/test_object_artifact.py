import pytest
import uuid
import time
import pathlib
import numpy
import json
from simvue.api.objects import ObjectArtifact, Run, Artifact
from simvue.api.objects.folder import Folder
from simvue.sender import sender
from simvue.serialization import _deserialize_numpy_array

@pytest.mark.api
@pytest.mark.online
def test_object_artifact_creation_online() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _folder_name = f"/simvue_unit_testing/{_uuid}"
    _folder = Folder.new(path=_folder_name)
    _run = Run.new(name=f"test_object_artifact_run_{_uuid}", folder=_folder_name) 
    _folder.commit()
    _run.commit()

    _array = numpy.array(range(10))
    _artifact = ObjectArtifact.new(
        name=f"test_object_artifact_{_uuid}",
        obj=_array,
        storage=None,
        metadata=None
    )
    _artifact.attach_to_run(_run.id, "input")
    time.sleep(1)
    
    _downloaded = _deserialize_numpy_array(next(_artifact.download_content()))
    assert numpy.array_equal(_downloaded, _array)
    
    _run.delete()
    _folder.delete(recursive=True, delete_runs=True, runs_only=False)


@pytest.mark.api
@pytest.mark.offline
def test_object_artifact_creation_offline(offline_test: pathlib.Path) -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _folder_name = f"/simvue_unit_testing/{_uuid}"
    _folder = Folder.new(path=_folder_name, offline=True)
    _run = Run.new(name=f"test_object_artifact_offline_run_{_uuid}", folder=_folder_name, offline=True) 
    _folder.commit()
    _run.commit()

    _array = numpy.array(range(10))
    _artifact = ObjectArtifact.new(
        name=f"test_object_artifact_offline_{_uuid}",
        obj=_array,
        storage=None,
        metadata=None,
        offline=True
    )
    _artifact.attach_to_run(_run.id, "input")
    
    with _artifact._local_staging_file.open() as in_f:
        _local_data = json.load(in_f)
        
    assert _local_data.get("name") == f"test_object_artifact_offline_{_uuid}"
    assert _local_data.get("mime_type") == "application/vnd.simvue.numpy.v1"
    assert _local_data.get("runs") == {_run.id: "input"}
        
    _id_mapping = sender(offline_test.joinpath(".simvue"), 1, 10)
    time.sleep(1)
    
    _online_artifact = Artifact(_id_mapping.get(_artifact.id))
    
    assert _online_artifact.name == f"test_object_artifact_offline_{_uuid}"
    assert _online_artifact.mime_type == "application/vnd.simvue.numpy.v1"
    
    _downloaded = _deserialize_numpy_array(next(_online_artifact.download_content()))
    assert numpy.array_equal(_downloaded, _array)
    _run.delete()
    _folder.delete(recursive=True, delete_runs=True, runs_only=False)

