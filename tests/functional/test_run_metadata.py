import pytest
import random
from simvue.client import Client
from simvue.run import Run
from simvue.sender import sender
from conftest import RunTestInfo


def metadata_update(test_run: RunTestInfo, close_run: bool, offline: bool) -> None:
    metadata = {'a': 'string', 'b': 1, 'c': 2.5}
    run = Run("offline" if offline else "online")
    run.init(test_run.run_name, metadata=metadata, folder=test_run.folder, running=close_run, tags=["simvue-client-test", f"test_metadata_update_{'offline' if offline else 'online'}"])
    run.config(suppress_errors=False)

    if offline:
        sender(suppress_errors=False)
    
    run.update_metadata({'b': 2})

    metadata['b'] = 2

    if close_run:
        run.close()

    if offline:
        _run_ids = sender(suppress_errors=False)
        assert _run_ids, "No runs were retrieved"
        

    client = Client()
    data = client.get_run(run.id if not offline else _run_ids[-1])
    assert data['metadata'] == metadata

    runs = client.delete_runs(test_run.folder)
    assert len(runs) == 1


@pytest.mark.run
@pytest.mark.metadata
@pytest.mark.parametrize(
    "close_run", (True, False),
    ids=("close_run", "leave_running")
)
def test_metadata_update_online(create_a_run: RunTestInfo, close_run: bool) -> None:
    """
    Check metadata can be updated & retrieved
    """
    metadata_update(create_a_run, close_run, False)


@pytest.mark.run
@pytest.mark.metadata
@pytest.mark.offline
def test_metadata_update_offline(create_a_run: RunTestInfo) -> None:
    """
    Check metadata can be updated & retrieved
    """
    metadata_update(create_a_run, True, True)


def metadata(run_info: RunTestInfo, offline: bool) -> None:
    metadata = {'a': 'string', 'b': random.random(), 'c': random.random()}
    run = Run(mode='offline' if offline else 'online')
    run.init(run_info.run_name, metadata=metadata, folder=run_info.folder, tags=["simvue-client-test", f"test_metadata_{'offline' if offline else 'online'}"])
    run.config(suppress_errors=False)
    run.close()

    if offline:
        _run_ids = sender(suppress_errors=False)
        assert _run_ids, "No runs were retrieved"
        

    client = Client()
    data = client.get_run(run.id if not offline else _run_ids[-1])
    assert data['metadata'] == metadata

    runs = client.delete_runs(run_info.folder)
    assert len(runs) > 0



@pytest.mark.run
@pytest.mark.metadata
def test_metadata(create_a_run: RunTestInfo) -> None:
    metadata(create_a_run, False)


@pytest.mark.run
@pytest.mark.metadata
@pytest.mark.offline
def test_metadata_offline(create_a_run: RunTestInfo) -> None:
    metadata(create_a_run, True)
