import pytest
import uuid
import os
import filecmp

from simvue.run import Run
from conftest import RunTestInfo
from simvue.client import Client

@pytest.mark.artifacts
@pytest.mark.parametrize(
    "created", (True, False),
    ids=("created", "normal")
)
@pytest.mark.parametrize(
    "file_type", ("input", "output", "code")
)
def test_artifact_output(create_a_run: RunTestInfo, created: bool, file_type: str) -> None:
    """
    Create a run & an artifact of type 'output' & check it can be downloaded
    """
    run = Run()
    run.init(create_a_run.run_name, folder=create_a_run.folder, running=not created)

    content = str(uuid.uuid4())

    _out_file: str = os.path.join(create_a_run.session_dir, create_a_run.file_name)
    
    with open(_out_file, 'w') as fh:
        fh.write(content)

    if created:
        with pytest.raises(Exception) as e:
            run.save(_out_file, file_type)
            assert "Cannot upload output files for runs in the created state" in f"{e.value}"
    else:
        run.save(_out_file, file_type)
        run.close()

    client = Client()

    if not created:
        client.get_artifact_as_file(run.id, create_a_run.file_name, os.path.join(create_a_run.session_dir, "test"))
        assert filecmp.cmp(_out_file, os.path.join(create_a_run.session_dir, "test", create_a_run.file_name))

    runs = client.delete_runs(create_a_run.folder)
    assert len(runs) == 1


@pytest.mark.artifacts
def test_get_artifact_invalid_run(create_a_run: RunTestInfo) -> None:
    """
    Try to obtain a file from a run which doesn't exist
    """
    client = Client()
    with pytest.raises(Exception) as context:
        client.get_artifact(create_a_run.run_name, create_a_run.folder)   
        assert 'Run does not exist' in str(context.exception)
