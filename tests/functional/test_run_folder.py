import pytest
from simvue.run import Run
from simvue.client import Client
from conftest import RunTestInfo


@pytest.mark.run
@pytest.mark.folder
def test_folder_find_delete(create_a_run: RunTestInfo) -> None:
    """
    Create a run & folder, find the folder then delete it
    """
    run = Run()
    run.init(create_a_run.run_name, folder=create_a_run.folder)
    run.close()

    client = Client()
    data = client.get_folder(create_a_run.folder)
    assert data['path'] == create_a_run.folder

    client.delete_folder(create_a_run.folder, runs=True)

    client = Client()
    with pytest.raises(Exception) as context:
        client.get_folder(create_a_run.folder)
        assert 'Folder does not exist' in str(context.exception)


@pytest.mark.run
@pytest.mark.folder
def test_folder_metadata_find(create_a_run: RunTestInfo) -> None:
    """
    Create a run & folder with metadata, find it then delete it
    """
    run = Run()
    run.init(create_a_run.run_name, folder=create_a_run.folder)
    run.set_folder_details(path=create_a_run.folder, metadata={'atest': 5.0})
    run.close()

    client = Client()
    data = client.get_folders(['atest == 5.0'])

    assert any(i['path'] == create_a_run.folder for i in data)

    client.delete_folder(create_a_run.folder, runs=True)

    client = Client()
    with pytest.raises(Exception) as context:
        client.get_folder(create_a_run.folder)
        assert 'Folder does not exist' in str(context.exception)


@pytest.mark.run
@pytest.mark.folder
def test_folder_init(create_a_run: RunTestInfo) -> None:
    """
    Check specified folder of run
    """
    run = Run()
    run.init(create_a_run.run_name, folder=create_a_run.folder)
    run.close()

    client = Client()
    data = client.get_run(run.id)
    assert data['folder'] == create_a_run.folder

    runs = client.delete_runs(create_a_run.folder)
    assert len(runs) == 1
