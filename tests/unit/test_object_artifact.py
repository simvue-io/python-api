import os
import pytest
import uuid
import time
import pathlib
import numpy

from simvue.api.objects import ObjectArtifact, Run
from simvue.api.objects.folder import Folder
from simvue.sender import sender
from simvue.client import Client

@pytest.mark.api
@pytest.mark.online
def test_object_artifact_creation_online() -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _folder_name = f"/simvue_unit_testing/{_uuid}"
    _folder = Folder.new(path=_folder_name)
    _run = Run.new(folder=_folder_name) 
    _folder.commit()
    _run.commit()

    _failed = []

    _array = numpy.array(range(10))
    _artifact = ObjectArtifact.new(
        name=f"test_object_artifact_{_uuid}",
        obj=_array,
        storage=None,
        metadata=None
    )
    _artifact.attach_to_run(_run.id, "input")
    time.sleep(1)
    for member in _artifact._properties:
        try:
            getattr(_artifact, member)
        except Exception as e:
            _failed.append((member, f"{e}"))
            
    _downloaded = _artifact.download_content()
    import pdb; pdb.set_trace()
    _run.delete()
    _folder.delete(recursive=True, delete_runs=True, runs_only=False)
    if _failed:
        raise AssertionError("\n\t-" + "\n\t- ".join(": ".join(i) for i in _failed))


@pytest.mark.api
@pytest.mark.offline
def test_object_artifact_creation_offline(offline_test: pathlib.Path) -> None:
    _uuid: str = f"{uuid.uuid4()}".split("-")[0]
    _folder_name = f"/simvue_unit_testing/{_uuid}"
    _folder = Folder.new(path=_folder_name, offline=True)
    _run = Run.new(name=f"test_object_artifact_creation_offline_{_uuid}",folder=_folder_name, offline=True) 

    _path = offline_test.joinpath("hello_world.txt")

    with _path.open("w") as out_f:
        out_f.write("Hello World!")

    _folder.commit()
    _run.commit()
    _array = numpy.array(range(10))
    _artifact = ObjectArtifact.new(
        name=f"test_object_artifact_{_uuid}",
        obj=_array,
        storage=None,
        metadata=None
    )
    _artifact.attach_to_run(_run._identifier, category="input")
    assert _artifact.name == f"test_object_artifact_{_uuid}"
    sender(offline_test.joinpath(".simvue"), 1, 10)
    time.sleep(1)
    client = Client()
    _run_id = client.get_run_id_from_name(f"test_object_artifact_creation_offline_{_uuid}")
    assert client.get_artifact(_run_id, _artifact.name) is not None
    _run.delete()
    _folder.delete()

