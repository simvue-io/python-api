import pytest
import tempfile
import configparser
import os
import pytest_mock
import logging
import shutil
import uuid
import requests
import glob
import dataclasses

import simvue.utilities as sv_util

SIMVUE_API_VERSION = os.getenv('SIMVUE_API_VERSION', 1)
CURRENT_RUN_DIR = os.getcwd()
TEST_RUN_ID = f"{uuid.uuid4()}".split('-')[0]

logging.getLogger("simvue").setLevel(logging.DEBUG)
logger = logging.getLogger("SimvueTest")
logger.setLevel(logging.DEBUG)



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
def create_a_run(
    session_directory: str,
    mocker: pytest_mock.MockerFixture,
    check_env: None,
) -> RunTestInfo:
    _run_id: str = str(uuid.uuid4()).split("-")[0]
    _run_name = f'client_test_{_run_id}'
    _file_name = f'test_{_run_id}'
    _test_dir = os.path.join(session_directory, "test")
    _folder = f"/simvue-client-tests/run_{TEST_RUN_ID}"
    os.makedirs(_test_dir, exist_ok=True)
    os.chdir(session_directory)
    return RunTestInfo(_run_name, _file_name, session_directory, _folder)


# Create post-test hook
def pytest_runtest_makereport(item, call) -> None:
    """Make sure the session returns to the current directory
    
    Important as in some tests the directory is changed to a temporary
    one that is then destroyed and this breaks Pytest if the test fails
    """

    os.chdir(CURRENT_RUN_DIR)

    if not (_contents := os.listdir(sv_util.get_offline_directory())):
        return

    logger.info(f"Clearing offline run directory: {sv_util.get_offline_directory()}")
    logger.debug(f"Contents: {_contents}")

    # clear runs in directory after test but do not remove directory itself
    for root, dir, files in os.walk(sv_util.get_offline_directory()):
        for file in files:
            os.unlink(os.path.join(root, file))
        for directory in dir:
            shutil.rmtree(os.path.join(root, directory))

    _process_err: list[str] = glob.glob(os.path.join(os.getcwd(), "client_test_*_process_*.err"))
    _process_out: list[str] = glob.glob(os.path.join(os.getcwd(), "client_test_*_process_*.out"))

    for file in _process_err + _process_out:
        os.remove(file)


    if not os.environ.get("SIMVUE_TESTS_KEEP_RUNS"):
        _url, _token = sv_util.get_auth()

        _headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {_token}"
        }

        _res = requests.get(f'{_url}/api/runs?filters["has tag.simvue-client-test]', headers=_headers)
        _runs = [i["id"] for i in _res.json()["data"]]

        for run in _runs:
            requests.delete(f'{_url}/api/runs/{run}', headers=_headers)
