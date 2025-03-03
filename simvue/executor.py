"""
Simvue Client Executor
======================

Adds functionality for executing commands from the command line as part of a Simvue run, the executor
monitors the exit code of the command setting the status to failure if non-zero.
Stdout and Stderr are sent to Simvue as artifacts.
"""

__author__ = "Kristian Zarebski"
__date__ = "2023-11-15"

import logging
import multiprocessing.synchronize
import sys
import multiprocessing
import threading
import os
import psutil
import subprocess
import contextlib
import pathlib
import time
import typing
from simvue.api.objects.alert.user import UserAlert

if typing.TYPE_CHECKING:
    import simvue

logger = logging.getLogger(__name__)


class CompletionCallback(typing.Protocol):
    def __call__(self, *, status_code: int, std_out: str, std_err: str) -> None: ...


def _execute_process(
    proc_id: str,
    command: list[str],
    runner_name: str,
    completion_callback: CompletionCallback | None = None,
    completion_trigger: multiprocessing.synchronize.Event | None = None,
    environment: dict[str, str] | None = None,
    cwd: pathlib.Path | None = None,
) -> tuple[subprocess.Popen, threading.Thread | None]:
    thread_out = None

    with open(f"{runner_name}_{proc_id}.err", "w") as err:
        with open(f"{runner_name}_{proc_id}.out", "w") as out:
            _result = subprocess.Popen(
                command,
                stdout=out,
                stderr=err,
                universal_newlines=True,
                env=environment,
                cwd=cwd,
            )

    if completion_callback or completion_trigger:

        def trigger_check(
            completion_callback: CompletionCallback | None,
            trigger_to_set: multiprocessing.synchronize.Event | None,
            process: subprocess.Popen,
        ) -> None:
            while process.poll() is None:
                time.sleep(1)
            if trigger_to_set:
                trigger_to_set.set()
            if completion_callback:
                std_err = pathlib.Path(f"{runner_name}_{proc_id}.err").read_text()
                std_out = pathlib.Path(f"{runner_name}_{proc_id}.out").read_text()
                completion_callback(
                    status_code=process.returncode,
                    std_out=std_out,
                    std_err=std_err,
                )

        thread_out = threading.Thread(
            target=trigger_check,
            args=(completion_callback, completion_trigger, _result),
        )
        thread_out.start()

    return _result, thread_out


class Executor:
    """Command Line command executor

    Adds execution of command line commands as part of a Simvue run, the status of these commands is monitored
    and if non-zero cause the Simvue run to be stated as 'failed'. The executor accepts commands either as a
    set of positional arguments or more specifically as components, two of these 'input_file' and 'script' then
    being used to set the relevant metadata within the Simvue run itself.
    """

    def __init__(self, simvue_runner: "simvue.Run", keep_logs: bool = True) -> None:
        """Initialise an instance of the Simvue executor attaching it to a Run.

        Parameters
        ----------
        simvue_runner : simvue.Run
            An instance of the Simvue runner used to send command execution feedback
        keep_logs : bool, optional
            whether to keep the stdout and stderr logs locally, by default False
        """
        self._runner = simvue_runner
        self._keep_logs = keep_logs
        self._completion_callbacks: dict[str, CompletionCallback] | None = {}
        self._completion_triggers: dict[
            str, multiprocessing.synchronize.Event | None
        ] = {}
        self._completion_processes: dict[str, threading.Thread] | None = {}
        self._alert_ids: dict[str, str] = {}
        self.command_str: dict[str, str] = {}
        self._processes: dict[str, subprocess.Popen] = {}
        self._all_processes: list[psutil.Process] = []

    def std_out(self, process_id: str) -> str | None:
        if not os.path.exists(out_file := f"{self._runner.name}_{process_id}.out"):
            return None

        with open(out_file) as out:
            return out.read() or None

    def std_err(self, process_id: str) -> str | None:
        if not os.path.exists(err_file := f"{self._runner.name}_{process_id}.err"):
            return None

        with open(err_file) as err:
            return err.read() or None

    def add_process(
        self,
        identifier: str,
        *args,
        executable: str | None = None,
        script: pathlib.Path | None = None,
        input_file: pathlib.Path | None = None,
        env: dict[str, str] | None = None,
        cwd: pathlib.Path | None = None,
        completion_callback: CompletionCallback | None = None,
        completion_trigger: multiprocessing.synchronize.Event | None = None,
        **kwargs,
    ) -> None:
        """Add a process to be executed to the executor.

        This process can take many forms, for example a be a set of positional arguments:

        ```python
        executor.add_process("my_process", "ls", "-ltr")
        ```

        Provide explicitly the components of the command:

        ```python
        executor.add_process("my_process", executable="bash", debug=True, c="return 1")
        executor.add_process("my_process", executable="bash", script="my_script.sh", input="parameters.dat")
        ```

        or a mixture of both. In the latter case arguments which are not 'executable', 'script', 'input'
        are taken to be options to the command, for flags `flag=True` can be used to set the option and
        for options taking values `option=value`.

        When the process has completed if a function has been provided for the `completion_callback` argument
        this will be called, this callback is expected to take the following form:

        ```python
        def callback_function(status_code: int, std_out: str, std_err: str) -> None:
            ...
        ```

        Note `completion_trigger` is not supported on Windows operating systems.

        Parameters
        ----------
        identifier : str
            A unique identifier for this process
        executable : str | None, optional
            the main executable for the command, if not specified this is taken to be the first
            positional argument, by default None
        script : str | None, optional
            the script to run, note this only work if the script is not an option, if this is the case
            you should provide it as such and perform the upload manually, by default None
        input_file : str | None, optional
            the input file to run, note this only work if the input file is not an option, if this is the case
            you should provide it as such and perform the upload manually, by default None
        env : dict[str, str], optional
            environment variables for process
        cwd: pathlib.Path | None, optional
            working directory to execute the process within
        completion_callback : typing.Callable | None, optional
            callback to run when process terminates
        completion_trigger : multiprocessing.Event | None, optional
            this trigger event is set when the processes completes (not supported on Windows)
        """
        pos_args = list(args)

        if not self._runner.name:
            raise RuntimeError("Cannot add process, expected Run instance to have name")

        if sys.platform == "win32" and completion_trigger:
            logger.warning(
                "Completion trigger for 'add_process' may fail on Windows "
                "due to function pickling restrictions"
            )

        if script:
            self._runner.save_file(file_path=script, category="code")

        if input_file:
            self._runner.save_file(file_path=input_file, category="input")

        command: list[str] = []

        if executable:
            command += [f"{executable}"]
        else:
            command += [pos_args[0]]
            pos_args.pop(0)
        if script:
            command += [f"{script}"]

        if input_file:
            command += [f"{input_file}"]

        for arg, value in kwargs.items():
            if arg.startswith("__"):
                continue

            arg = arg.replace("_", "-")

            if len(arg) == 1:
                command += (
                    [f"-{arg}"]
                    if isinstance(value, bool) and value
                    else [f"-{arg}", f"{value}"]
                )
            elif isinstance(value, bool) and value:
                command += [f"--{arg}"]
            else:
                command += [f"--{arg}", f"{value}"]

        command += pos_args

        self.command_str[identifier] = " ".join(command)
        self._completion_callbacks[identifier] = completion_callback
        self._completion_triggers[identifier] = completion_trigger

        self._processes[identifier], self._completion_processes[identifier] = (
            _execute_process(
                identifier,
                command,
                self._runner.name,
                completion_callback,
                completion_trigger,
                env,
                cwd,
            )
        )

        self._alert_ids[identifier] = self._runner.create_user_alert(
            name=f"{identifier}_exit_status"
        )

        if not self._alert_ids[identifier]:
            raise RuntimeError(f"Expected alert identifier for process '{identifier}'")

    @property
    def processes(self) -> list[psutil.Process]:
        """Create an array containing a list of processes"""
        if not self._processes:
            return []

        _current_processes: list[psutil.Process] = []

        for process in self._processes.values():
            with contextlib.suppress(psutil.NoSuchProcess):
                _current_processes.append(psutil.Process(process.pid))

        with contextlib.suppress(psutil.NoSuchProcess, psutil.ZombieProcess):
            for process in _current_processes:
                for child in process.children(recursive=True):
                    if child not in _current_processes:
                        _current_processes.append(child)

        _current_pids = set([_process.pid for _process in _current_processes])
        _previous_pids = set([_process.pid for _process in self._all_processes])

        # Find processes which used to exist, which are no longer running
        _expired_process_pids = _previous_pids - _current_pids

        # Remove these processes from list of all processes
        self._all_processes = [
            _process
            for _process in self._all_processes
            if _process.pid not in _expired_process_pids
        ]

        # Find new processes
        _new_process_pids = _current_pids - _previous_pids
        _new_processes = [
            _process
            for _process in _current_processes
            if _process.pid in _new_process_pids
        ]

        # Get CPU usage stats for each of those new processes, so that next time it's measured by the heartbeat the value is accurate
        if _new_processes:
            [_process.cpu_percent() for _process in _new_processes]
            time.sleep(0.1)

        # Add these to the list of all processes
        self._all_processes += _new_processes

        return self._all_processes

    @property
    def success(self) -> int:
        """Return whether all attached processes completed successfully"""
        return all(i.returncode == 0 for i in self._processes.values())

    @property
    def exit_status(self) -> int:
        """Returns the first non-zero exit status if applicable"""
        if _non_zero := [
            i.returncode for i in self._processes.values() if i.returncode != 0
        ]:
            return _non_zero[0]

        return 0

    def get_error_summary(self) -> dict[str, str] | None:
        """Returns the summary messages of all errors"""
        return {
            identifier: self._get_error_status(identifier)
            for identifier, value in self._processes.items()
            if value.returncode
        }

    def get_command(self, process_id: str) -> str:
        """Returns the command executed within the given process.

        Parameters
        ----------
        process_id : str
            Unique identifier for the process

        Returns
        -------
        str
            command as a string
        """
        if process_id not in self._processes:
            raise KeyError(f"Failed to retrieve '{process_id}', no such process")
        return self.command_str[process_id]

    def _get_error_status(self, process_id: str) -> str | None:
        err_msg: str | None = None

        # Return last 10 lines of stdout if stderr empty
        if not (err_msg := self.std_err(process_id)) and (
            std_out := self.std_out(process_id)
        ):
            err_msg = "  Tail STDOUT:\n\n"
            start_index = -10 if len(lines := std_out.split("\n")) > 10 else 0
            err_msg += "\n".join(lines[start_index:])
        return err_msg

    def _update_alerts(self) -> None:
        """Send log events for the result of each process"""
        # Wait for the dispatcher to send the latest information before
        # allowing the executor to finish (and as such the run instance to exit)
        _wait_limit: float = 1
        for proc_id, process in self._processes.items():
            # We don't want to override the user's setting for the alert status
            # This is so that if a process incorrectly reports its return code,
            # the user can manually set the correct status depending on logs etc.
            _alert = UserAlert(identifier=self._alert_ids[proc_id])
            _is_set = _alert.get_status(run_id=self._runner._id)

            if process.returncode != 0:
                # If the process fails then purge the dispatcher event queue
                # and ensure that the stderr event is sent before the run closes
                if self._runner._dispatcher:
                    self._runner._dispatcher.purge()
                if not _is_set:
                    self._runner.log_alert(
                        identifier=self._alert_ids[proc_id], state="critical"
                    )
            else:
                if not _is_set:
                    self._runner.log_alert(
                        identifier=self._alert_ids[proc_id], state="ok"
                    )

            _current_time: float = 0
            while (
                self._runner._dispatcher
                and not self._runner._dispatcher.empty
                and _current_time < _wait_limit
            ):
                time.sleep((_current_time := _current_time + 0.1))

    def _save_output(self) -> None:
        """Save the output to Simvue"""
        for proc_id in self._processes.keys():
            # Only save the file if the contents are not empty
            if self.std_err(proc_id):
                self._runner.save_file(
                    f"{self._runner.name}_{proc_id}.err", category="output"
                )
            if self.std_out(proc_id):
                self._runner.save_file(
                    f"{self._runner.name}_{proc_id}.out", category="output"
                )

    def kill_process(
        self, process_id: int | str, kill_children_only: bool = False
    ) -> None:
        """Kill a running process by ID

        If argument is a string this is a process handled by the client,
        else it is a PID of a external monitored process

        Parameters
        ----------
        process_id : int | str
            either the identifier for a client created process or the PID
            of an external process
        kill_children_only : bool, optional
            if process_id is an integer, whether to kill only its children
        """
        if isinstance(process_id, str):
            if not (process := self._processes.get(process_id)):
                logger.error(
                    f"Failed to terminate process '{process_id}', no such identifier."
                )
                return
            try:
                parent = psutil.Process(process.pid)
            except psutil.NoSuchProcess:
                return
        elif isinstance(process_id, int):
            try:
                parent = psutil.Process(process_id)
            except psutil.NoSuchProcess:
                return

        for child in parent.children(recursive=True):
            logger.debug(f"Terminating child process {child.pid}: {child.name()}")
            child.kill()

        for child in parent.children(recursive=True):
            child.wait()

        if not kill_children_only and process:
            logger.debug(f"Terminating process {process.pid}: {process.args}")
            process.kill()
            process.wait()

        self._save_output()

    def kill_all(self) -> None:
        """Kill all running processes"""
        for process in self._processes.keys():
            self.kill_process(process)

    def _clear_cache_files(self) -> None:
        """Clear local log files if required"""
        if not self._keep_logs:
            for proc_id in self._processes.keys():
                os.remove(f"{self._runner.name}_{proc_id}.err")
                os.remove(f"{self._runner.name}_{proc_id}.out")

    def wait_for_completion(self) -> None:
        """Wait for all processes to finish then perform tidy up and upload"""
        for identifier, process in self._processes.items():
            process.wait()

        self._update_alerts()
        self._save_output()

        if not self.success:
            self._runner.set_status("failed")
        self._clear_cache_files()
