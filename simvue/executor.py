import typing
import subprocess
import multiprocessing
import logging
import os

if typing.TYPE_CHECKING:
    import simvue

logger = logging.getLogger(__name__)


class Executor:
    def __init__(self, simvue_runner: "simvue.Run", keep_logs: bool=False) -> None:
        self._runner = simvue_runner
        self._keep_logs = keep_logs
        self._manager = multiprocessing.Manager()
        self._exit_codes = self._manager.dict()
        self._std_err = self._manager.dict()
        self._std_out = self._manager.dict()
        self._processes: typing.Dict[str, multiprocessing.Process] = {}

    def add_process(
        self,
        identifier: str,
        executable: str | None = None,
        script: str | None = None,
        input_file: str | None = None,
        *args,
        **kwargs,
    ) -> None:
        _alert_kwargs = {
            k.replace("__", ""): v for k, v in kwargs.items() if k.startswith("__")
        }

        if script:
            self._runner.save(filename=script, category="code")

        if input_file:
            self._runner.save(filename=input_file, category="input")

        self._runner.add_alert(
            f"{identifier} Status",
            source="events",
            pattern="non-zero exit code",
            **_alert_kwargs,
        )

        def _exec_process(
            proc_id: str,
            command: typing.List[str],
            runner: "simvue.Run",
            exit_status_dict: typing.Dict[str, int],
            std_err: typing.Dict[str, str],
            std_out: typing.Dict[str, str]
        ) -> None:
            with open(f"{runner.name}_{proc_id}.err", "w") as err:
                with open(f"{runner.name}_{proc_id}.out", "w") as out:
                    _result = subprocess.run(command, stdout=out, stderr=err, text=True)

            with open(f"{runner.name}_{proc_id}.err") as err:
                std_err[proc_id] = err.read()

            with open(f"{runner.name}_{proc_id}.out") as out:
                std_out[proc_id] = out.read()

            exit_status_dict[proc_id] = _result.returncode

        _command: typing.List[str] = []

        if executable:
            _command += [executable]

        if script:
            _command += [script]

        if input_file:
            _command += [input_file]

        _command += list(args)

        for arg, value in kwargs.items():
            if arg.startswith("__"):
                continue
            if len(arg) == 1:
                if isinstance(value, bool) and value:
                    _command += [f"-{arg}"]
                else:
                    _command += [f"-{arg}", f"{value}"]
            else:
                if isinstance(value, bool) and value:
                    _command += [f"--{arg}"]
                else:
                    _command += [f"--{arg}", f"{value}"]

        self._processes[identifier] = multiprocessing.Process(
            target=_exec_process,
            args=(
                identifier,
                _command,
                self._runner,
                self._exit_codes,
                self._std_err,
                self._std_out
            ),
        )
        logger.debug(f"Executing process: {' '.join(_command)}")
        self._processes[identifier].start()

    @property
    def success(self) -> int:
        return all(i == 0 for i in self._exit_codes.values())

    def _log_events(self) -> None:
        for proc_id, code in self._exit_codes.items():
            if code != 0:
                _err = self._std_err[proc_id]
                _msg = f"Process {proc_id} returned non-zero exit code status {code} with:\n{_err}"
            else:
                _msg = f"Process {proc_id} completed successfully."
            self._runner.log_event(_msg)

    def _save_output(self) -> None:
        for proc_id in self._exit_codes.keys():
            # Only save the file if the contents are not empty
            if self._std_err[proc_id]:
                self._runner.save(f"{self._runner.name}_{proc_id}.err", category="output")
            if self._std_out[proc_id]:
                self._runner.save(f"{self._runner.name}_{proc_id}.out", category="output")
            
    
    def _clear_cache_files(self) -> None:
        if not self._keep_logs:
            for proc_id in self._exit_codes.keys():
                os.remove(f"{self._runner.name}_{proc_id}.err")
                os.remove(f"{self._runner.name}_{proc_id}.out")

    def wait_for_completion(self) -> None:
        for process in self._processes.values():
            process.join()
        self._log_events()
        self._save_output()
        if not self.success:
            self._runner.set_status("failed")
        self._clear_cache_files()
