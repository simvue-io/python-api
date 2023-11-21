import pytest
import tempfile
import configparser
import os
import uuid
import dataclasses

from simvue.client import Client

SIMVUE_API_VERSION = os.getenv('SIMVUE_API_VERSION', 1)

def create_config(directory: str) -> None:
    """
    Rewrite offline cache into config file
    """
    config = configparser.ConfigParser()
    config.read('simvue.ini')

    config['offline'] = {}
    config['offline']['cache'] = os.path.join(directory, 'offline')
    os.makedirs(os.path.join(directory, 'offline'), exist_ok=True)

    with open(os.path.join(directory, 'simvue.ini'), 'w') as configfile:
        config.write(configfile)


@pytest.fixture
def test_directory() -> str:
    with tempfile.TemporaryDirectory() as temp_d:
        create_config(temp_d)
        yield temp_d

@pytest.fixture(scope="session")
def session_directory() -> str:
    with tempfile.TemporaryDirectory() as temp_d:
        create_config(temp_d)
        yield temp_d


@dataclasses.dataclass
class RunTestInfo:
    run_name: str
    file_name: str
    client: Client
    session_dir: str
    
def _create_a_run(temp_dir: str) -> RunTestInfo:
    _client = Client()
    _run_id = f'{uuid.uuid4()}'
    _file_name = f'test-{uuid.uuid4()}'
    _test_dir = os.path.join(temp_dir, "test")
    os.makedirs(_test_dir, exist_ok=True)
    return RunTestInfo(_run_id, _file_name, _client, temp_dir)


@pytest.fixture(scope="session")
def create_run_1(session_directory: str) -> RunTestInfo:
    return _create_a_run(session_directory)
    

@pytest.fixture(scope="session")
def create_run_2(session_directory: str) -> RunTestInfo:
    return _create_a_run(session_directory)

@pytest.fixture(scope="session")
def create_run_3(session_directory: str) -> RunTestInfo:
    return _create_a_run(session_directory)