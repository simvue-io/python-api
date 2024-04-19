import pytest
import simvue
import time
import os
import shutil
import tempfile


@pytest.mark.executor
@pytest.mark.parametrize("successful", (True, False), ids=("successful", "failing"))
def test_executor_add_process(
    successful: bool
) -> None:
    with tempfile.TemporaryDirectory() as temp_d:
        if os.path.exists(_simvue_cfg := os.path.join(os.getcwd(), "simvue.ini")):
            shutil.copy(_simvue_cfg, os.path.join(temp_d, "simvue.ini"))
        elif os.path.exists(_simvue_cfg := os.path.join(os.environ["HOME"], ".simvue.ini")):
            shutil.copy(_simvue_cfg, os.path.join(temp_d, "simvue.ini"))
        _cwd = os.getcwd()
        os.chdir(temp_d)
        run = simvue.Run()
        run.init(f"test_executor_{'success' if successful else 'fail'}", tags=["simvue_client_unit_tests"])
        run.add_process(
            identifier=f"test_add_process_{'success' if successful else 'fail'}",
            c=f"exit {0 if successful else 1}",
            executable="bash",
        )
        run.close()
        os.chdir(_cwd)

        if not successful:
            assert run._executor.exit_status != 0
        else:
            assert run._executor.exit_status == 0
        time.sleep(1)
        client = simvue.Client()
        _events = client.get_events(
            run._id,
            message_contains="successfully" if successful else "non-zero exit",
        )
        assert len(_events) == 1
