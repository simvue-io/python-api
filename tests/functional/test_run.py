import pytest
import os
import uuid
import random
import time

from simvue.run import Run
from simvue.sender import sender
from simvue.client import Client
from conftest import SIMVUE_API_VERSION, RunTestInfo



def context_run(run_info: RunTestInfo, offline: bool) -> None:
    """
    Create a run using a context manager & check that it exists
    """
    with Run() as run:
        run.init(run_info.run_name, folder=run_info.folder)

    if offline:
        sender()

    client = Client()
    data = client.get_run(run.id)
    assert run_info.run_name == data["name"]

    runs = client.delete_runs(run_info.folder)
    assert len(runs) == 1


@pytest.mark.run
def test_context_run(create_a_run: RunTestInfo) -> None:
    context_run(create_a_run, False)


@pytest.mark.run
@pytest.mark.offline
def test_context_run_offline(create_a_run: RunTestInfo) -> None:
    context_run(create_a_run, True)


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
@pytest.mark.events
def test_events(create_a_run: RunTestInfo) -> None:
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


@pytest.mark.run
@pytest.mark.metrics
def test_run_metrics(create_a_run: RunTestInfo) -> None:
    """
    Try logging metrics and retrieving them
    """
    run = Run()
    run.init(create_a_run.run_name, folder=create_a_run.folder)
    run.log_metrics({'a': 1.0})
    run.log_metrics({'a': 1.2})

    run.log_metrics({'b': 2.0}, step=10, time=2.0)
    run.log_metrics({'b': 2.3}, step=11, time=3.0)

    run.close()

    time.sleep(5)

    client = Client()
    data_a = client.get_metrics(run.id, 'a', 'step')
    data_b = client.get_metrics(run.id, 'b', 'step')
    data_b_time = client.get_metrics(run.id, 'b', 'time')

    data_a_val = [[0, 1.0, create_a_run.run_name, 'a'], [1, 1.2, create_a_run.run_name, 'a']]
    data_b_val = [[10, 2.0, create_a_run.run_name, 'b'], [11, 2.3, create_a_run.run_name, 'b']]
    data_b_time_val = [[2.0, 2.0, create_a_run.run_name, 'b'], [3.0, 2.3, create_a_run.run_name, 'b']]

    assert data_a == data_a_val
    assert data_b == data_b_val
    assert data_b_time == data_b_time_val

    metrics_names = client.get_metrics_names(run.id)
    assert metrics_names == ['a', 'b']

    runs = client.delete_runs(create_a_run.folder)
    assert len(runs) == 1
