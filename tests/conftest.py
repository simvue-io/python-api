import pytest
import tempfile
import configparser
import os
import uuid
import dataclasses

SIMVUE_API_VERSION = os.getenv('SIMVUE_API_VERSION', 1)


@pytest.fixture
def check_env(request) -> None:
    for item in request.session.items:
        if item.get_closest_marker('online') is not None:
            for env_var in ("SIMVUE_TOKEN", "SIMVUE_URL"):
                if not os.getenv(env_var, None):
                    raise AssertionError(
                        f"Environment variable {env_var} must be set for this test"
                    )


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
def session_directory() -> str:
    with tempfile.TemporaryDirectory() as temp_d:
        create_config(temp_d)
        yield temp_d

@dataclasses.dataclass
class RunTestInfo:
    run_name: str
    file_name: str
    session_dir: str
    folder: str
    

@pytest.fixture
def create_a_run(session_directory: str, check_env: None) -> RunTestInfo:
    _run_id = f'{uuid.uuid4()}'
    _file_name = f'test-{uuid.uuid4()}'
    _test_dir = os.path.join(session_directory, "test")
    _folder = f"/test-{uuid.uuid4()}"
    os.makedirs(_test_dir, exist_ok=True)
    os.chdir(session_directory)
    return RunTestInfo(_run_id, _file_name, session_directory, _folder)
