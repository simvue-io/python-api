import pathlib
import time
import os
import sys
import tempfile
import pytest
import filecmp
import simvue.sender as sv_send

from simvue import Run, Client
from simvue.sender import sender

@pytest.mark.executor
@pytest.mark.offline
def test_monitor_processes(create_plain_run_offline: tuple[Run, dict]):
    _run: Run
    _run, _ = create_plain_run_offline
    _run.add_process("process_1", "Hello world!", executable="echo", n=True)
    _run.add_process("process_2", "bash" if sys.platform != "win32" else "powershell", debug=True, c="exit 0")
    _run.add_process("process_3", "ls", "-ltr")
    sender(_run._sv_obj._local_staging_file.parents[1], 1, 10, ["folders", "runs", "alerts"])


@pytest.mark.executor
def test_abort_all_processes(create_plain_run: tuple[Run, dict]) -> None:
    _run, _ = create_plain_run
    with tempfile.NamedTemporaryFile(suffix=".py") as temp_f:
        with open(temp_f.name, "w") as out_f:
            out_f.writelines([
                "import time\n",
                "count = 0\n"
                "while True:\n",
                "    print(count)\n"
                "    time.sleep(1)\n"
                "    count += 1"
            ])

        for i in range(1, 3):
            _run.add_process(f"process_{i}", executable="python", script=temp_f.name)
            assert _run.executor.get_command(f"process_{i}") == f"python {temp_f.name}"

        time.sleep(3)

        _run.kill_all_processes()

        # Check the Python process did not error
        _out_err = pathlib.Path.cwd().glob("*process_*.err")
        for file in _out_err:
            with file.open() as in_f:
                assert not in_f.readlines()

        # Now check the counter in the process was terminated
        # just beyond the sleep time
        _out_files = pathlib.Path.cwd().glob("*process_*.out")
        for file in _out_files:
            with file.open() as in_f:
                assert (lines := in_f.readlines())
                assert int(lines[0].strip()) < 4


def test_processes_cwd(create_plain_run: dict[Run, dict]) -> None:
    """Check that cwd argument works correctly in add_process.

    Create a temporary directory, and a python file inside that directory. Check that if only the file name
    is passed to add_process as the script, and the directory is specified as the cwd argument, that the process
    runs correctly and the script is uploaded as expected.
    """
    run, _ = create_plain_run
    with tempfile.TemporaryDirectory() as temp_dir:
        with tempfile.NamedTemporaryFile(dir=temp_dir, suffix=".py") as temp_file:
            with open(temp_file.name, "w") as out_f:
                out_f.writelines([
                    "import os\n",
                    "f = open('new_file.txt', 'w')\n",
                    "f.write('Test Line')\n",
                    "f.close()"
                ])

            run_id = run.id
            run.add_process(
                identifier="sleep_10_process",
                executable="python",
                script=temp_file.name,
                cwd=temp_dir
            )
            time.sleep(1)
            run.save_file(os.path.join(temp_dir, "new_file.txt"), 'output')

            client = Client()

            # Check that the script was uploaded to the run correctly
            os.makedirs(os.path.join(temp_dir, "downloaded"))
            client.get_artifact_as_file(run_id, os.path.basename(temp_file.name), output_dir=os.path.join(temp_dir, "downloaded"))
            assert filecmp.cmp(os.path.join(temp_dir, "downloaded", os.path.basename(temp_file.name)), temp_file.name)

            client.get_artifact_as_file(run_id, "new_file.txt", output_dir=os.path.join(temp_dir, "downloaded"))
            with open(os.path.join(temp_dir, "downloaded", "new_file.txt"), "r") as new_file:
                assert new_file.read() == "Test Line"

