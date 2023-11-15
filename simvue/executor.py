import typing
import subprocess
import multiprocessing
import logging

if typing.TYPE_CHECKING:
    import simvue

logger = logging.getLogger(__name__)

class Executor:
    def __init__(self, simvue_runner: "simvue.Run") -> None:
        self._runner = simvue_runner
        self._manager = multiprocessing.Manager()
        self._execution_triggers = self._manager.dict()
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
            self._runner.save(
                filename=script,
                category="code"
            )
        
        if input_file:
            self._runner.save(
                filename=input_file,
                category="input"
            )

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
        ) -> None:
            with open(f"{runner.name}_{proc_id}.err", "w") as err:
                with open(f"{runner.name}_{proc_id}.out", "w") as out:
                    _result = subprocess.run(command, stdout=out, stderr=err, text=True)

            if _result.returncode != 0:
                with open(f"{runner.name}_{proc_id}.err") as err:
                    runner.set_status('failed')
                    runner.log_event(
                        f"Process {proc_id} returned non-zero exit code status {_result.returncode} with:"
                        f"\n{err.read()}"
                    )
            else:
                runner.log_event(f"Process {proc_id} completed successfully")

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
                _command += [f"-{arg}", f"{value}"]
            else:
                _command += [f"--{arg}", f"{value}"]

        self._processes[identifier] = multiprocessing.Process(
            target=_exec_process, args=(identifier, _command, self._runner)
        )
        logger.debug(f"Executing process: {' '.join(_command)}")
        self._processes[identifier].start()

    def wait_for_completion(self) -> None:
        for process in self._processes.values():
            process.join()