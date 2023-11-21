import pytest
import os
import uuid
import random

from simvue.run import Run
from simvue.client import Client
from conftest import SIMVUE_API_VERSION


@pytest.mark.run
def test_run_metadata(test_directory: str) -> None:
    os.chdir(test_directory)
    name = f"test-{uuid.uuid4()}"
    folder = f"/test-{uuid.uuid4()}"
    metadata = {'a': 'string', 'b': random.random(), 'c': random.random()}
    run = Run(mode='offline')
    run.init(name, metadata=metadata, folder=folder)
    run.close()

    run_id = name
    if SIMVUE_API_VERSION:
        run_id = run.id

    client = Client()
    data = client.get_run(run_id, metadata=True)
    assert data['metadata'] == metadata

    runs = client.delete_runs(folder)
    assert len(runs) == 1