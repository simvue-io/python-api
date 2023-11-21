import pytest
import uuid
import os
import filecmp

from simvue.run import Run
from conftest import RunTestInfo

@pytest.mark.artifacts
def test_artifact_output(create_run_3: RunTestInfo) -> None:
    """
    Create a run & an artifact of type 'output' & check it can be downloaded
    """
    run = Run()
    folder = f"/test-{uuid.uuid4()}"
    run.init(create_run_3.run_name, folder=folder)

    content = str(uuid.uuid4())

    _out_file: str = os.path.join(create_run_3.session_dir, create_run_3.file_name)
    with open(_out_file, 'w') as fh:
        fh.write(content)

    run.save(_out_file, 'output')

    run.close()

    print(_out_file)
    print(os.path.join(create_run_3.session_dir, "test", create_run_3.file_name))

    assert filecmp.cmp(_out_file, os.path.join(create_run_3.session_dir, "test", create_run_3.file_name))

    runs = create_run_3.client.delete_runs(folder)
    assert len(runs) == 1
