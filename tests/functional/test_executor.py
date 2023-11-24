import pytest
import uuid
import time
import tempfile

from simvue.run import Run
from conftest import RunTestInfo

@pytest.mark.executor
def test_monitor_process(create_a_run: RunTestInfo) -> None:
    with Run(mode='offline') as _run:
        _run.init(f"test_exec_monitor_{uuid.uuid4()}")
        _run.add_process("process_1", "Hello world!", executable="echo", n=True)
        _run.add_process("process_2", "bash", debug=True, c="'return 1'")
        _run.add_process("process_3", "ls", "-ltr")


@pytest.mark.executor
def test_abort_all_processes(create_a_run: RunTestInfo) -> None:
    start_time = time.time()
    with Run(mode='offline') as _run:
        with tempfile.NamedTemporaryFile(suffix=".py") as temp_f:
            with open(temp_f.name, "w") as out_f:
                out_f.writelines([
                    "import time\n",
                    "while True:\n"
                    "    time.sleep(5)\n"
                ])
            _run.init(f"test_exec_monitor_{uuid.uuid4()}")

            for i in range(1, 3):
                _run.add_process(f"process_{i}", executable="python", script=temp_f.name)
                assert _run.executor.get_command(f"process_{i}") == f"python {temp_f.name}"
            
            time.sleep(5)

            _run.kill_all_processes()
    end_time = time.time()

    assert end_time - start_time < 10, f"{end_time - start_time} >= 10"