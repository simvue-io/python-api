import pytest
import simvue
import time
import sys
import multiprocessing
    

@pytest.mark.executor
@pytest.mark.parametrize("successful", (True, False), ids=("successful", "failing"))
def test_executor_add_process(
    successful: bool
) -> None:
    run = simvue.Run()
    completion_trigger = multiprocessing.Event()
    run.init(
        f"test_executor_{'success' if successful else 'fail'}",
        tags=["simvue_client_unit_tests"],
        folder="/simvue_unit_test_folder"
    )

    run.add_process(
        identifier=f"test_add_process_{'success' if successful else 'fail'}",
        c=f"exit {0 if successful else 1}",
        executable="bash" if sys.platform != "win32" else "powershell",
        completion_trigger=completion_trigger
    )

    while not completion_trigger.is_set():
        time.sleep(1)

    if successful:
        run.close()
    else:
        with pytest.raises(SystemExit):
            run.close()

    time.sleep(1)
    client = simvue.Client()
    _events = client.get_events(
        run._id,
        message_contains="successfully" if successful else "non-zero exit",
    )
    assert len(_events) == 1
