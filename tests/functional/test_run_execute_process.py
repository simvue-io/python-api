import contextlib
import pathlib
import time
import os
import sys
import tempfile
import pytest
import filecmp

from simvue import Run, Client
from simvue.executor import get_current_shell
from simvue.sender import Sender

@pytest.mark.executor
def test_monitor_processes(create_plain_run_offline: tuple[Run, dict]):
    _run: Run
    _run, _ = create_plain_run_offline

    if any(shell in os.environ.get("SHELL", "") for shell in ("zsh", "bash")):
        _run.add_process(f"process_1_{os.environ.get('PYTEST_XDIST_WORKER', 0)}", "Hello world!", executable="echo", n=True)
        _run.add_process(f"process_2_{os.environ.get('PYTEST_XDIST_WORKER', 0)}", "bash", debug=True, c="exit 0")
        _run.add_process(f"process_3_{os.environ.get('PYTEST_XDIST_WORKER', 0)}", "ls", "-ltr")
    else:
        _run.add_process(f"process_1_{os.environ.get('PYTEST_XDIST_WORKER', 0)}", Command="Write-Output 'Hello World!'", executable="powershell")
        _run.add_process(f"process_2_{os.environ.get('PYTEST_XDIST_WORKER', 0)}", Command="Get-ChildItem", executable="powershell")
        _run.add_process(f"process_3_{os.environ.get('PYTEST_XDIST_WORKER', 0)}", Command="exit 0", executable="powershell")
    _sender = Sender(_run._sv_obj._local_staging_file.parents[1], 1, 10, throw_exceptions=True)
    _sender.upload(["folders", "runs", "alerts"], )


@pytest.mark.executor
def test_abort_all_processes(create_plain_run: tuple[Run, dict]) -> None:
    _run, _ = create_plain_run
    _pwsh = any(shell in os.environ.get("SHELL", get_current_shell()) for shell in ("pwsh", "powershell"))
    _command = (
        "echo 'Using Bash...'; for i in {0..20}; do echo $i; sleep 1; done"
    ) if not _pwsh else (
        "Write-Output 'Using Powershell...'; for ($i = 0; $i -le 20; $i++){ Write-Output $i }"
    )


    _arguments = {"Command" if _pwsh else "c": _command}
    _executable="powershell" if _pwsh else "bash"

    for i in range(1, 3):
        _run.add_process(
            f"process_{i}_{os.environ.get('PYTEST_XDIST_WORKER', 0)}",
            executable=_executable,
            **_arguments
        )
        assert _run.executor.get_command(
            f"process_{i}_{os.environ.get('PYTEST_XDIST_WORKER', 0)}"
        ) == f"{_executable} {'-Command' if _pwsh else '-c'} {_command}"


    time.sleep(3)

    _run.kill_all_processes()

    # Check that for when one of the processes has stopped
    _attempts: int = 0
    _first_out = next(pathlib.Path.cwd().glob(f"*process_*_{os.environ.get('PYTEST_XDIST_WORKER', 0)}.out"))

    while _first_out.stat().st_size == 0 and _attempts < 10:
        time.sleep(1)
        _attempts += 1

    if _attempts >= 10:
        raise AssertionError("Failed to terminate processes")

    # Check the Python process did not error
    _out_err = pathlib.Path.cwd().glob(f"*process_*_{os.environ.get('PYTEST_XDIST_WORKER', 0)}.err")
    for file in _out_err:
        with file.open() as in_f:
            # Simvue Executor appends message informing user it aborted the process itself
            _lines = in_f.readlines()
            assert len(_lines) == 1
            assert "Process was aborted by Simvue executor." in _lines[0]

    # Now check the counter in the process was terminated
    # just beyond the sleep time
    _out_files = pathlib.Path.cwd().glob(f"*process_*_{os.environ.get('PYTEST_XDIST_WORKER', 0)}.out")
    for file in _out_files:
        with file.open() as in_f:
            assert (lines := in_f.readlines()[1:])
            assert int(lines[0].strip()) < 4


@pytest.mark.executor
def test_processes_cwd(create_plain_run: dict[Run, dict]) -> None:
    """Check that cwd argument works correctly in add_process.

    Create a temporary directory, and a python file inside that directory. Check that if only the file name
    is passed to add_process as the script, and the directory is specified as the cwd argument, that the process
    runs correctly and the script is uploaded as expected.
    """
    run, _ = create_plain_run
    with tempfile.TemporaryDirectory() as temp_dir:
        with tempfile.NamedTemporaryFile(
            delete=False,
            dir=temp_dir,
            prefix=os.environ.get("PYTEST_XDIST_WORKER", "0"),
            suffix=".py"
        ) as temp_file:
            with open(temp_file.name, "w") as out_f:
                out_f.writelines([
                    "import os\n",
                    f"f = open('new_file_{os.environ.get('PYTEST_XDIST_WORKER', 0)}.txt', 'w')\n",
                    "f.write('Test Line')\n",
                    "f.close()"
                ])

            run_id = run.id
            run.add_process(
                identifier=f"sleep_10_process_{os.environ.get('PYTEST_XDIST_WORKER', 0)}",
                executable="python",
                script=temp_file.name,
                cwd=temp_dir
            )
            time.sleep(1)
            run.save_file(os.path.join(temp_dir, f"new_file_{os.environ.get('PYTEST_XDIST_WORKER', 0)}.txt"), 'output')

            client = Client()

            # Check that the script was uploaded to the run correctly
            os.makedirs(os.path.join(temp_dir, "downloaded"))
            client.get_artifact_as_file(run_id, os.path.basename(temp_file.name), output_dir=os.path.join(temp_dir, "downloaded"))
            assert filecmp.cmp(os.path.join(temp_dir, "downloaded", os.path.basename(temp_file.name)), temp_file.name)

            client.get_artifact_as_file(run_id, f"new_file_{os.environ.get('PYTEST_XDIST_WORKER', 0)}.txt", output_dir=os.path.join(temp_dir, "downloaded"))
            with open(os.path.join(temp_dir, "downloaded", f"new_file_{os.environ.get('PYTEST_XDIST_WORKER', 0)}.txt"), "r") as new_file:
                assert new_file.read() == "Test Line"
    with contextlib.suppress(FileNotFoundError):
        os.unlink(temp_file.name)

