import typing
import subprocess
import multiprocessing

class Executor:
    def __init__(self, simvue_runner: "simvue.Run") -> None:
        self._runner = simvue_runner
        self._manager = multiprocessing.Manager()
        self._execution_triggers = self._manager.dict()
        self._processes: typing.Dict[str, multiprocessing.Process] = {}

    def add_process(self, identifier: str, *args, **kwargs) -> None:
        _alert_kwargs = {k.replace("__", ""): v for k, v in kwargs.items() if k.startswith("__")}
        self._runner.add_alert(f"{identifier} Status", source="events", pattern="non-zero exit code", **_alert_kwargs)
        def _exec_process(
            proc_id: str,
            command: typing.List[str],
            runner: "simvue.Run",
        ) -> None:
            with open(f"{runner.name}_{proc_id}.err", "w") as err:
                with open(f"{runner.name}_{proc_id}.out", "w") as out:
                    _result = subprocess.run(command, stdout=out, stderr=err, text=True)

            if _result.returncode != 0:
                runner.log_event(f"Process {proc_id} returned non-zero exit code status {_result.returncode}")
            else:
                runner.log_event(f"Process {proc_id} completed successfully")
        
        _command: typing.List[str] = list(args)

        for arg, value in kwargs.items():
            if arg.startswith("__"):
                continue
            if len(arg) == 1:
                _command += [f"-{arg}", f"{value}"]
            else:
                _command += [f"--{arg}", f"{value}"]

        self._processes[identifier] = multiprocessing.Process(
            target=_exec_process,
            args=(identifier, _command, self._runner)
        )
        self._processes[identifier].start()

        

            
            



