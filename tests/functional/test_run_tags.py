import pytest
from simvue.client import Client
from simvue.run import Run
from simvue.sender import sender
from conftest import RunTestInfo


def run_tags(run_info: RunTestInfo, offline: bool) -> None:
    """
    Check tags can be specified & retrieved
    """
    tags = ['a1', 'b2']
    run = Run()
    run.init(run_info.run_name, tags=tags, folder=run_info.folder)
    run.close()

    if offline:
        sender()

    client = Client()
    data = client.get_run(run.id, tags=True)
    assert tags == data['tags']

    runs = client.delete_runs(run_info.folder)
    assert len(runs) == 1


@pytest.mark.run
@pytest.mark.tags
def test_run_tags(create_a_run: RunTestInfo) -> None:
    """
    Check tags can be specified & retrieved
    """
    run_tags(create_a_run, False)


@pytest.mark.run
@pytest.mark.tags
@pytest.mark.offline
def test_run_tags_offline(create_a_run: RunTestInfo) -> None:
    """
    Check tags can be specified & retrieved
    """
    run_tags(create_a_run, True)


def run_tags_update(run_info: RunTestInfo, close_run: bool, offline: bool) -> None:
    """
    Check tags can be updated & retrieved
    """
    tags = ['a1']
    run = Run()
    run.init(run_info.run_name, tags=tags, folder=run_info.folder)

    if offline:
        sender()

    run.update_tags(['a1', 'b2'])
    tags.append('b2')

    if close_run:
        run.close()
    
    if offline:
        sender()

    client = Client()
    data = client.get_run(run.id, tags=True)
    assert tags == data['tags']

    runs = client.delete_runs(run_info.folder)
    assert len(runs) == 1

@pytest.mark.run
@pytest.mark.tags
@pytest.mark.parametrize(
    "close_run", (True, False),
    ids=("close_run", "leave_running")
)
def test_run_tags_update(create_a_run: RunTestInfo, close_run: bool) -> None:
    run_tags_update(create_a_run, close_run, False)


@pytest.mark.run
@pytest.mark.tags
@pytest.mark.offline
def test_run_tags_update(create_a_run: RunTestInfo) -> None:
    run_tags_update(create_a_run, True, True)
