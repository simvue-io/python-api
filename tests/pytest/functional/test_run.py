import pytest
import os
import uuid
import random
import time

from simvue.run import Run
from simvue.sender import sender
from simvue.client import Client
from conftest import SIMVUE_API_VERSION, RunTestInfo


@pytest.mark.run
def test_run_metadata(session_directory: str) -> None:
    os.chdir(session_directory)
    name = f"test-{uuid.uuid4()}"
    folder = f"/test-{uuid.uuid4()}"
    metadata = {"a": "string", "b": random.random(), "c": random.random()}
    run = Run(mode="offline")
    run.init(name, metadata=metadata, folder=folder)
    run.close()

    run_id = name
    if SIMVUE_API_VERSION:
        run_id = run.id

    client = Client()
    data = client.get_run(run_id, metadata=True)
    assert data["metadata"] == metadata

    runs = client.delete_runs(folder)
    assert len(runs) == 1


@pytest.mark.run
def test_context_run(create_a_run: RunTestInfo) -> None:
    """
    Create a run using a context manager & check that it exists
    """
    name = f"test-{uuid.uuid4()}"
    folder = f"/test-{uuid.uuid4()}"
    with Run() as run:
        run.init(name, folder=folder)

    client = Client()
    data = client.get_run(run.id)
    assert name == data["name"]

    runs = client.delete_runs(folder)
    assert len(runs) == 1



def basic_run(run: RunTestInfo, mode: str) -> None:
    """
    Create a run in the created state, then reconnect to it
    """
    run_create = Run(mode)
    run_create.init(run.run_name, folder=run.folder, running=False)
    uid = run_create.uid

    assert run.run_name == run_create.name

    if mode == "offline":
        sender()

    client = Client()
    data = client.get_run(run_create.id)

    assert data["status"] == "created"

    run_start = Run(mode)
    run_start.reconnect(run_create.id, uid if mode == "offline" else None)

    if mode == "offline":
        sender()

    data = client.get_run(run_start.id)
    assert data["status"] == "running"

    run_start.close()

    runs = client.delete_runs(run.folder)
    assert len(runs) == 1


@pytest.mark.run
def test_basic_run_online(create_a_run: RunTestInfo) -> None:
    basic_run(create_a_run, "online")


@pytest.mark.run
@pytest.mark.offline
def test_basic_run_offline(create_a_run: RunTestInfo) -> None:
    basic_run(create_a_run, "offline")


@pytest.mark.run
def test_run_events(create_a_run: RunTestInfo) -> None:
    """
    Try logging events and retrieving them
    """
    run = Run()
    run.init(create_a_run.run_name, folder=create_a_run.folder)

    run.log_event('test-event-1', timestamp='2022-01-03 16:42:30.849617')
    run.log_event('test-event-2', timestamp='2022-01-03 16:42:31.849617')

    run.close()

    time.sleep(5)

    client = Client()
    data = client.get_events(run.id)

    data_compare = [{'timestamp': '2022-01-03 16:42:30.849617', 'message': 'test-event-1'},
                    {'timestamp': '2022-01-03 16:42:31.849617', 'message': 'test-event-2'}]

    assert data == data_compare

    runs = client.delete_runs(create_a_run.folder)
    assert len(runs) == 1
