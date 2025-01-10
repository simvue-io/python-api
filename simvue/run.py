"""
Simvue Run
==========

Main class for recording metrics and information to Simvue during code execution.
This forms the central API for users.
"""

import contextlib
import logging
import pathlib
import mimetypes
import multiprocessing.synchronize
import threading
import humanfriendly
import os
import multiprocessing
import pydantic
import re
import sys
import traceback as tb
import time
import functools
import platform
import typing
import warnings
import uuid

import click
import psutil

from simvue.api.objects.alert.fetch import Alert
from simvue.api.objects.folder import Folder, get_folder_from_path
from simvue.exception import ObjectNotFoundError, SimvueRunError


from .config.user import SimvueConfiguration

from .factory.dispatch import Dispatcher
from .executor import Executor
from .metrics import get_gpu_metrics, get_process_cpu, get_process_memory
from .models import FOLDER_REGEX, NAME_REGEX, MetricKeyString
from .system import get_system
from .metadata import git_info, environment
from .eco import SimvueEmissionsTracker
from .utilities import (
    skip_if_failed,
    validate_timestamp,
    simvue_timestamp,
)
from .api.objects import (
    Run as RunObject,
    Artifact,
    MetricsThresholdAlert,
    MetricsRangeAlert,
    UserAlert,
    EventsAlert,
)

try:
    from typing import Self
except ImportError:
    from typing_extensions import Self


if typing.TYPE_CHECKING:
    from .factory.dispatch import DispatcherBaseClass

UPLOAD_TIMEOUT: int = 30
HEARTBEAT_INTERVAL: int = 60
RESOURCES_METRIC_PREFIX: str = "resources"

logger = logging.getLogger(__name__)


def check_run_initialised(
    function: typing.Callable[..., typing.Any],
) -> typing.Callable[..., typing.Any]:
    @functools.wraps(function)
    def _wrapper(self: Self, *args: typing.Any, **kwargs: typing.Any) -> typing.Any:
        if self._user_config.run.mode == "disabled":
            return True

        if self._retention and time.time() - self._timer > self._retention:
            self._active = False
            raise RuntimeError("Cannot update expired Simvue Run")

        if not self._sv_obj:
            raise RuntimeError(
                "Simvue Run must be initialised before calling "
                f"'{function.__name__}'"
            )
        return function(self, *args, **kwargs)

    return _wrapper


class Run:
    """Track simulation details based on token and URL

    The Run class provides a way of monitoring simulation runs by logging metrics
    and creating alerts based on such metrics. The recommended usage is as a
    context manager to ensure the run is closed upon completion.
    """

    @pydantic.validate_call
    def __init__(
        self,
        mode: typing.Literal["online", "offline", "disabled"] = "online",
        abort_callback: typing.Optional[typing.Callable[[Self], None]] = None,
        server_token: typing.Optional[pydantic.SecretStr] = None,
        server_url: typing.Optional[str] = None,
        debug: bool = False,
    ) -> None:
        """Initialise a new Simvue run

        If `abort_callback` is provided the first argument must be this Run instance

        Parameters
        ----------
        mode : Literal['online', 'offline', 'disabled'], optional
            mode of running
                online - objects sent directly to Simvue server
                offline - everything is written to disk for later dispatch
                disabled - disable monitoring completely
        abort_callback : Callable | None, optional
            callback executed when the run is aborted
        server_token : str, optional
            overwrite value for server token, default is None
        server_url : str, optional
            overwrite value for server URL, default is None
        debug : bool, optional
            run in debug mode, default is False
        """
        self._uuid: str = f"{uuid.uuid4()}"
        self._name: typing.Optional[str] = None

        # monitor duration with respect to retention period
        self._timer: float = 0
        self._retention: typing.Optional[float] = None

        self._testing: bool = False
        self._abort_on_alert: typing.Literal["run", "terminate", "ignore"] = "terminate"
        self._abort_callback: typing.Optional[typing.Callable[[Self], None]] = (
            abort_callback
        )
        self._dispatch_mode: typing.Literal["direct", "queued"] = "queued"

        self._executor = Executor(self)
        self._dispatcher: typing.Optional[DispatcherBaseClass] = None

        self._id: typing.Optional[str] = None
        self._folder: Folder | None = None
        self._term_color: bool = True
        self._suppress_errors: bool = False
        self._queue_blocking: bool = False
        self._status: typing.Optional[
            typing.Literal[
                "created", "running", "completed", "failed", "terminated", "lost"
            ]
        ] = None
        self._data: dict[str, typing.Any] = {}
        self._step: int = 0
        self._active: bool = False
        self._user_config = SimvueConfiguration.fetch(
            server_url=server_url, server_token=server_token, mode=mode
        )

        logging.getLogger(self.__class__.__module__).setLevel(
            logging.DEBUG
            if (debug is not None and debug)
            or (debug is None and self._user_config.client.debug)
            else logging.INFO
        )

        self._aborted: bool = False
        self._resources_metrics_interval: typing.Optional[int] = (
            HEARTBEAT_INTERVAL
            if self._user_config.metrics.resources_metrics_interval < 1
            else self._user_config.metrics.resources_metrics_interval
        )
        self._headers: dict[str, str] = {
            "Authorization": f"Bearer {self._user_config.server.token.get_secret_value()}"
        }
        self._sv_obj: typing.Optional[RunObject] = None
        self._pid: typing.Optional[int] = 0
        self._shutdown_event: typing.Optional[threading.Event] = None
        self._configuration_lock = threading.Lock()
        self._heartbeat_termination_trigger: typing.Optional[threading.Event] = None
        self._storage_id: typing.Optional[str] = None
        self._heartbeat_thread: typing.Optional[threading.Thread] = None

        self._heartbeat_interval: int = HEARTBEAT_INTERVAL
        self._emission_metrics_interval: int | None = (
            HEARTBEAT_INTERVAL
            if (
                (_interval := self._user_config.metrics.emission_metrics_interval)
                and _interval < 1
            )
            else self._user_config.metrics.emission_metrics_interval
        )
        self._emissions_tracker: typing.Optional[SimvueEmissionsTracker] = (
            SimvueEmissionsTracker("simvue", self, self._emission_metrics_interval)
            if self._user_config.metrics.enable_emission_metrics
            else None
        )

    def __enter__(self) -> Self:
        return self

    def _handle_exception_throw(
        self,
        exc_type: typing.Optional[typing.Type[BaseException]],
        value: BaseException,
        traceback: typing.Optional[
            typing.Union[typing.Type[BaseException], BaseException]
        ],
    ) -> None:
        _exception_thrown: typing.Optional[str] = (
            exc_type.__name__ if exc_type else None
        )
        _is_running: bool = self._status == "running"
        _is_running_online: bool = self._id is not None and _is_running
        _is_running_offline: bool = (
            self._user_config.run.mode == "offline" and _is_running
        )
        _is_terminated: bool = (
            _exception_thrown is not None and _exception_thrown == "KeyboardInterrupt"
        )

        if not _exception_thrown and _is_running:
            return

        # Abort executor processes
        self._executor.kill_all()

        if not _is_running:
            return

        if not self._active:
            return

        _traceback_out: list[str] = tb.format_exception(exc_type, value, traceback)
        _event_msg: str = (
            "\n".join(_traceback_out)
            if _traceback_out
            else f"An exception was thrown: {_exception_thrown}"
        )

        self.log_event(_event_msg)
        self.set_status("terminated" if _is_terminated else "failed")

        # If the dispatcher has already been aborted then this will
        # fail so just continue without the event
        with contextlib.suppress(RuntimeError):
            self.log_event(f"{_exception_thrown}: {value}")

        if not traceback:
            return

        with contextlib.suppress(RuntimeError):
            self.log_event(f"Traceback: {traceback}")

    def __exit__(
        self,
        exc_type: typing.Optional[typing.Type[BaseException]],
        value: BaseException,
        traceback: typing.Optional[
            typing.Union[typing.Type[BaseException], BaseException]
        ],
    ) -> None:
        logger.debug(
            "Automatically closing run '%s' in status %s",
            self._id if self._user_config.run.mode == "online" else "unregistered",
            self._status,
        )

        # Exception handling
        self._handle_exception_throw(exc_type, value, traceback)

        self._tidy_run()

    @property
    def duration(self) -> float:
        """Return current run duration"""
        return time.time() - self._start_time

    @property
    def time_stamp(self) -> str:
        """Return current timestamp"""
        return simvue_timestamp()

    @property
    def processes(self) -> list[psutil.Process]:
        """Create an array containing a list of processes"""

        process_list = self._executor.processes

        if not self._parent_process:
            return process_list

        process_list += [self._parent_process]

        # Attach child processes relating to the process set by set_pid
        with contextlib.suppress(psutil.NoSuchProcess, psutil.ZombieProcess):
            for child in self._parent_process.children(recursive=True):
                if child not in process_list:
                    process_list.append(child)

        return list(set(process_list))

    def _get_sysinfo(self) -> dict[str, typing.Any]:
        """Retrieve system administration

        Returns
        -------
        dict[str, typing.Any]
            retrieved system specifications
        """
        cpu = get_process_cpu(self.processes)
        memory = get_process_memory(self.processes)
        gpu = get_gpu_metrics(self.processes)
        data: dict[str, typing.Any] = {}

        if memory is not None and cpu is not None:
            data = {
                f"{RESOURCES_METRIC_PREFIX}/cpu.usage.percent": cpu,
                f"{RESOURCES_METRIC_PREFIX}/memory.usage": memory,
            }
            if gpu:
                for item in gpu:
                    data[item] = gpu[item]
        return data

    def _create_heartbeat_callback(
        self,
    ) -> typing.Callable[[threading.Event], None]:
        if (
            self._user_config.run.mode == "online"
            and (not self._user_config.server.url or not self._id)
        ) or not self._heartbeat_termination_trigger:
            raise RuntimeError("Could not commence heartbeat, run not initialised")

        def _heartbeat(
            heartbeat_trigger: typing.Optional[
                threading.Event
            ] = self._heartbeat_termination_trigger,
            abort_callback: typing.Optional[
                typing.Callable[[Self], None]
            ] = self._abort_callback,
        ) -> None:
            if not heartbeat_trigger:
                raise RuntimeError("Expected initialisation of heartbeat")

            last_heartbeat = time.time()
            last_res_metric_call = time.time()

            while not heartbeat_trigger.is_set():
                time.sleep(0.1)

                with self._configuration_lock:
                    if (
                        self._resources_metrics_interval
                        and (res_time := time.time()) - last_res_metric_call
                        > self._resources_metrics_interval
                    ):
                        # Set join on fail to false as if an error is thrown
                        # join would be called on this thread and a thread cannot
                        # join itself!
                        self._add_metrics_to_dispatch(
                            self._get_sysinfo(), join_on_fail=False
                        )
                        last_res_metric_call = res_time

                if time.time() - last_heartbeat < self._heartbeat_interval:
                    continue

                last_heartbeat = time.time()

                # Check if the user has aborted the run
                with self._configuration_lock:
                    if self._sv_obj and self._sv_obj.abort_trigger:
                        self._alert_raised_trigger.set()
                        logger.debug("Received abort request from server")

                        if abort_callback is not None:
                            abort_callback(self)  # type: ignore

                        if self._abort_on_alert != "ignore":
                            self.kill_all_processes()
                            if self._dispatcher and self._shutdown_event:
                                self._shutdown_event.set()
                                self._dispatcher.purge()
                                self._dispatcher.join()
                            if self._active:
                                self.set_status("terminated")
                            click.secho(
                                "[simvue] Run was aborted.",
                                fg="red" if self._term_color else None,
                                bold=self._term_color,
                            )
                        if self._abort_on_alert == "terminate":
                            os._exit(1)

                if self._sv_obj:
                    self._sv_obj.send_heartbeat()

        return _heartbeat

    def _create_dispatch_callback(
        self,
    ) -> typing.Callable:
        """Generates the relevant callback for posting of metrics and events

        The generated callback is assigned to the dispatcher instance and is
        executed on metrics and events objects held in a buffer.
        """

        if self._user_config.run.mode == "online" and not self._id:
            raise RuntimeError("Expected identifier for run")

        if not self._user_config.server.url or not self._sv_obj:
            raise RuntimeError("Cannot commence dispatch, run not initialised")

        def _dispatch_callback(
            buffer: list[typing.Any],
            category: str,
            run_obj: RunObject = self._sv_obj,
        ) -> None:
            run_obj.log_entries(entries=buffer, entry_type=category)

        return _dispatch_callback

    def _start(self, reconnect: bool = False) -> bool:
        """Start a run

        Parameters
        ----------
        reconnect : bool, optional
            whether this is a reconnect to an existing run, by default False

        Returns
        -------
        bool
            if successful
        """
        if self._user_config.run.mode == "disabled":
            return True

        if self._user_config.run.mode != "offline":
            self._uuid = "notused"

        logger.debug("Starting run")

        if self._sv_obj:
            self._sv_obj.status = self._status
            self._sv_obj.commit()

        self._start_time = time.time()

        if self._pid == 0:
            self._pid = os.getpid()

        self._parent_process = psutil.Process(self._pid) if self._pid else None

        self._shutdown_event = threading.Event()
        self._heartbeat_termination_trigger = threading.Event()
        self._alert_raised_trigger = threading.Event()

        try:
            self._dispatcher = Dispatcher(
                mode=self._dispatch_mode,
                termination_trigger=self._shutdown_event,
                object_types=["events", "metrics"],
                callback=self._create_dispatch_callback(),
            )

            self._heartbeat_thread = threading.Thread(
                target=self._create_heartbeat_callback()
            )

        except RuntimeError as e:
            self._error(e.args[0])
            return False

        self._active = True

        self._dispatcher.start()
        self._heartbeat_thread.start()

        return True

    def _error(self, message: str, join_threads: bool = True) -> None:
        """Raise an exception if necessary and log error

        Parameters
        ----------
        message : str
            message to display in exception or logger message
        join_threads : bool
            whether to join the threads on failure. This option exists to
            prevent join being called in nested thread calls to this function.

        Raises
        ------
        RuntimeError
            exception throw
        """
        if self._emissions_tracker:
            with contextlib.suppress(Exception):
                self._emissions_tracker.stop()

        # Stop heartbeat
        if self._heartbeat_termination_trigger and self._heartbeat_thread:
            self._heartbeat_termination_trigger.set()
            if join_threads:
                self._heartbeat_thread.join()

        # Finish stopping all threads
        if self._shutdown_event:
            self._shutdown_event.set()

        # Purge the queue as we can no longer send metrics
        if self._dispatcher and self._dispatcher.is_alive():
            self._dispatcher.purge()
            if join_threads:
                self._dispatcher.join()

        if not self._suppress_errors:
            raise SimvueRunError(message)

        # Simvue support now terminated as the instance of Run has entered
        # the dormant state due to exception throw so set listing to be 'lost'
        if self._status == "running" and self._sv_obj:
            self._sv_obj.name = self._name
            self._sv_obj.status = "lost"
            self._sv_obj.commit()

        logger.error(message)

        self._aborted = True

    @skip_if_failed("_aborted", "_suppress_errors", False)
    @pydantic.validate_call
    def init(
        self,
        name: typing.Annotated[str | None, pydantic.Field(pattern=NAME_REGEX)] = None,
        *,
        metadata: dict[str, typing.Any] = None,
        tags: typing.Optional[list[str]] = None,
        description: typing.Optional[str] = None,
        folder: typing.Annotated[
            str, pydantic.Field(None, pattern=FOLDER_REGEX)
        ] = None,
        running: bool = True,
        retention_period: typing.Optional[str] = None,
        timeout: typing.Optional[int] = 180,
        visibility: typing.Union[
            typing.Literal["public", "tenant"], list[str], None
        ] = None,
        no_color: bool = False,
    ) -> bool:
        """Initialise a Simvue run

        Parameters
        ----------
        name : str, optional
            the name to allocate this run, if not specified a name will be
            selected at random, by default None
        metadata : typing.dict[str, typing.Any], optional
            any metadata relating to the run as key-value pairs, by default None
        tags : typing.list[str], optional
            a list of tags for this run, by default None
        description : str, optional
            description of the run, by default None
        folder : str, optional
            folder within which to store the run, by default "/"
        running : bool, optional
            whether to set the status as running or created, the latter implying
            the run will be commenced at a later time. Default is True.
        retention_period : str, optional
            describer for time period to retain run, the default of None
            removes this constraint.
        timeout: int, optional
            specify the timeout of the run, if None there is no timeout
        visibility : Literal['public', 'tenant'] | list[str], optional
            set visibility options for this run, either:
                * public - run viewable to all.
                * tenant - run viewable to all within the current tenant.
                * A list of usernames with which to share this run
        no_color : bool, optional
            disable terminal colors. Default False.

        Returns
        -------
        bool
            whether the initialisation was successful
        """
        if self._user_config.run.mode == "disabled":
            logger.warning(
                "Simvue monitoring has been deactivated for this run, metrics and artifacts will not be recorded."
            )
            return True

        description = description or self._user_config.run.description
        tags = (tags or []) + (self._user_config.run.tags or [])
        folder = folder or self._user_config.run.folder
        name = name or self._user_config.run.name
        metadata = (metadata or {}) | (self._user_config.run.metadata or {})

        self._term_color = not no_color

        try:
            self._folder = get_folder_from_path(path=folder)
        except ObjectNotFoundError:
            self._folder = Folder.new(
                path=folder, offline=self._user_config.run.mode == "offline"
            )
            self._folder.commit()  # type: ignore

        if isinstance(visibility, str) and visibility not in ("public", "tenant"):
            self._error(
                "invalid visibility option, must be either None, 'public', 'tenant' or a list of users"
            )

        if self._user_config.run.mode not in ("online", "offline"):
            self._error("invalid mode specified, must be online, offline or disabled")
            return False

        if not self._user_config.server.token or not self._user_config.server.url:
            self._error(
                "Unable to get URL and token from environment variables or config file"
            )
            return False

        if name and not re.match(r"^[a-zA-Z0-9\-\_\s\/\.:]+$", name):
            self._error("specified name is invalid")
            return False

        self._name = name

        self._status = "running" if running else "created"

        # Parse the time to live/retention time if specified
        try:
            if retention_period:
                self._retention: typing.Optional[int] = int(
                    humanfriendly.parse_timespan(retention_period)
                )
            else:
                self._retention = None
        except humanfriendly.InvalidTimespan as e:
            self._error(e.args[0])
            return False

        self._timer = time.time()

        self._sv_obj = RunObject.new(
            folder=folder, offline=self._user_config.run.mode == "offline"
        )

        if description:
            self._sv_obj.description = description

        if name:
            self._sv_obj.name = name

        self._sv_obj.visibility = {
            "users": visibility if isinstance(visibility, list) else [],
            "tenant": visibility == "tenant",
            "public": visibility == "public",
        }
        self._sv_obj.ttl = self._retention
        self._sv_obj.status = self._status
        self._sv_obj.tags = tags
        self._sv_obj.metadata = (metadata or {}) | git_info(os.getcwd()) | environment()
        self._sv_obj.heartbeat_timeout = timeout

        if self._status == "running":
            self._sv_obj.system = get_system()

        self._data = self._sv_obj._staging
        self._sv_obj.commit()

        if self._user_config.run.mode == "online":
            name = self._sv_obj.name

        self._id = self._sv_obj.id

        if not name:
            return False

        elif name is not True:
            self._name = name

        if self._status == "running":
            self._start()

        if self._user_config.run.mode == "online":
            click.secho(
                f"[simvue] Run {self._name} created",
                bold=self._term_color,
                fg="green" if self._term_color else None,
            )
            click.secho(
                f"[simvue] Monitor in the UI at {self._user_config.server.url}/dashboard/runs/run/{self._id}",
                bold=self._term_color,
                fg="green" if self._term_color else None,
            )

        if self._emissions_tracker and self._status == "running":
            self._emissions_tracker.post_init()
            self._emissions_tracker.start()

        return True

    @skip_if_failed("_aborted", "_suppress_errors", None)
    @pydantic.validate_call(config={"arbitrary_types_allowed": True})
    def add_process(
        self,
        identifier: str,
        *cmd_args,
        executable: typing.Optional[typing.Union[str, pathlib.Path]] = None,
        script: typing.Optional[pydantic.FilePath] = None,
        input_file: typing.Optional[pydantic.FilePath] = None,
        completion_callback: typing.Optional[
            typing.Callable[[int, str, str], None]
        ] = None,
        completion_trigger: typing.Optional[multiprocessing.synchronize.Event] = None,
        env: typing.Optional[typing.Dict[str, str]] = None,
        cwd: typing.Optional[pathlib.Path] = None,
        **cmd_kwargs,
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

        Note `completion_callback` is not supported on Windows operating systems.

        Alternatively you can use `completion_trigger` to create a multiprocessing event which will be set
        when the process has completed.

        Parameters
        ----------
        identifier : str
            A unique identifier for this process
        executable : str | None, optional
            the main executable for the command, if not specified this is taken to be the first
            positional argument, by default None
        *positional_arguments : Any, ..., optional
            all other positional arguments are taken to be part of the command to execute
        script : pydantic.FilePath | None, optional
            the script to run, note this only work if the script is not an option, if this is the case
            you should provide it as such and perform the upload manually, by default None
        input_file : pydantic.FilePath | None, optional
            the input file to run, note this only work if the input file is not an option, if this is the case
            you should provide it as such and perform the upload manually, by default None
        completion_callback : typing.Callable | None, optional
            callback to run when process terminates (not supported on Windows)
        completion_trigger : multiprocessing.Event | None, optional
            this trigger event is set when the processes completes
        env : typing.Dict[str, str], optional
            environment variables for process
        cwd: typing.Optional[pathlib.Path], optional
            working directory to execute the process within. Note that executable, input and script file paths should
            be absolute or relative to the directory where this method is called, not relative to the new working directory.
        **kwargs : Any, ..., optional
            all other keyword arguments are interpreted as options to the command
        """
        if platform.system() == "Windows" and completion_trigger:
            raise RuntimeError(
                "Use of 'completion_trigger' on Windows based operating systems is unsupported "
                "due to function pickling restrictions for multiprocessing"
            )

        if isinstance(executable, pathlib.Path) and not executable.is_file():
            raise FileNotFoundError(f"Executable '{executable}' is not a valid file")

        cmd_list: typing.List[str] = []
        pos_args = list(cmd_args)
        executable_str: typing.Optional[str] = None

        # Assemble the command for saving to metadata as string
        if executable:
            executable_str = f"{executable}"
            cmd_list += [executable_str]
        else:
            cmd_list += [pos_args[0]]
            executable = pos_args[0]
            pos_args.pop(0)

        for kwarg, val in cmd_kwargs.items():
            _quoted_val: str = f'"{val}"'
            if len(kwarg) == 1:
                if isinstance(val, bool) and val:
                    cmd_list += [f"-{kwarg}"]
                else:
                    cmd_list += [f"-{kwarg}{(f' {_quoted_val}') if val else ''}"]
            else:
                kwarg = kwarg.replace("_", "-")
                if isinstance(val, bool) and val:
                    cmd_list += [f"--{kwarg}"]
                else:
                    cmd_list += [f"--{kwarg}{(f' {_quoted_val}') if val else ''}"]

        cmd_list += pos_args
        cmd_str = " ".join(cmd_list)

        # Store the command executed in metadata
        self.update_metadata({f"{identifier}_command": cmd_str})

        # Add the process to the executor
        self._executor.add_process(
            identifier,
            *cmd_args,
            executable=executable_str,
            script=script,
            input_file=input_file,
            completion_callback=completion_callback,  # type: ignore
            completion_trigger=completion_trigger,
            env=env,
            cwd=cwd,
            **cmd_kwargs,
        )

    @pydantic.validate_call
    def kill_process(self, process_id: str) -> None:
        """Kill a running process by ID

        Parameters
        ----------
        process_id : str
            the unique identifier for the added process
        """
        self._executor.kill_process(process_id)

    def kill_all_processes(self) -> None:
        """Kill all currently running processes."""
        # Dont kill the manually attached process if it is the current script
        # but do kill its children. The kill process method of executor by
        # default refers to its own processes but can also be used on a PID
        if self._parent_process:
            self._executor.kill_process(
                process_id=self._parent_process.pid,
                kill_children_only=self._parent_process.pid == os.getpid(),
            )
        self._executor.kill_all()

    @property
    def executor(self) -> Executor:
        """Return the executor for this run"""
        return self._executor

    @property
    def name(self) -> typing.Optional[str]:
        """Return the name of the run"""
        return self._name

    @property
    def uid(self) -> str:
        """Return the local unique identifier of the run"""
        return self._uuid

    @property
    def id(self) -> typing.Optional[str]:
        """Return the unique id of the run"""
        return self._id

    @skip_if_failed("_aborted", "_suppress_errors", False)
    @pydantic.validate_call
    def reconnect(self, run_id: str) -> bool:
        """Reconnect to a run in the created state

        Parameters
        ----------
        run_id : str
            identifier of run to connect to

        Returns
        -------
        bool
            whether reconnection succeeded
        """
        self._status = "running"

        self._id = run_id
        self._sv_obj = RunObject(identifier=self._id)
        self._start(reconnect=True)

        return True

    @skip_if_failed("_aborted", "_suppress_errors", None)
    @pydantic.validate_call
    def set_pid(self, pid: int) -> None:
        """Set pid of process to be monitored

        Parameters
        ----------
        pid : int
            PID of the process to be monitored
        """
        self._pid = pid

    @skip_if_failed("_aborted", "_suppress_errors", False)
    @pydantic.validate_call
    def config(
        self,
        *,
        suppress_errors: typing.Optional[bool] = None,
        queue_blocking: typing.Optional[bool] = None,
        resources_metrics_interval: typing.Optional[pydantic.PositiveInt] = None,
        emission_metrics_interval: typing.Optional[pydantic.PositiveInt] = None,
        enable_emission_metrics: typing.Optional[bool] = None,
        disable_resources_metrics: typing.Optional[bool] = None,
        storage_id: typing.Optional[str] = None,
        abort_on_alert: typing.Optional[
            typing.Union[typing.Literal["run", "all", "ignore"], bool]
        ] = None,
    ) -> bool:
        """Optional configuration

        Parameters
        ----------
        suppress_errors : bool, optional
            disable exception throwing instead putting Simvue into a
            dormant state if an error occurs
        queue_blocking : bool, optional
            block thread queues during metric/event recording
        resources_metrics_interval : int, optional
            frequency at which to collect resource metrics
        enable_emission_metrics : bool, optional
            enable monitoring of emission metrics
        disable_resources_metrics : bool, optional
            disable monitoring of resource metrics
        storage_id : str, optional
            identifier of storage to use, by default None
        abort_on_alert : Literal['ignore', run', 'terminate'], optional
            whether to abort when an alert is triggered.
            If 'run' then the current run is aborted.
            If 'terminate' then the script itself is terminated.
            If 'ignore' then alerts will not affect this run

        Returns
        -------
        bool
            if configuration was successful
        """

        with self._configuration_lock:
            if suppress_errors is not None:
                self._suppress_errors = suppress_errors

            if queue_blocking is not None:
                self._queue_blocking = queue_blocking

            if resources_metrics_interval and disable_resources_metrics:
                self._error(
                    "Setting of resource metric interval and disabling resource metrics is ambiguous"
                )
                return False

            if disable_resources_metrics:
                self._pid = None
                self._resources_metrics_interval = None

            if emission_metrics_interval:
                if not enable_emission_metrics:
                    self._error(
                        "Cannot set rate of emission metrics, these metrics have been disabled"
                    )
                    return False
                self._emission_metrics_interval = emission_metrics_interval

            if enable_emission_metrics:
                self._emissions_tracker = SimvueEmissionsTracker(
                    "simvue", self, self._emission_metrics_interval
                )

                # If the main Run API object is initialised the run is active
                # hence the tracker should start too
                if self._sv_obj:
                    self._emissions_tracker.start()
            elif enable_emission_metrics is False and self._emissions_tracker:
                self._error("Cannot disable emissions tracker once it has been started")

            if resources_metrics_interval:
                self._resources_metrics_interval = resources_metrics_interval

            if abort_on_alert is not None:
                if isinstance(abort_on_alert, bool):
                    warnings.warn(
                        "Use of type bool for argument 'abort_on_alert' will be deprecated from v1.2, "
                        "please use either 'run', 'all' or 'ignore'"
                    )
                    abort_on_alert = "run" if self._abort_on_alert else "ignore"
                self._abort_on_alert = abort_on_alert

            if storage_id:
                self._storage_id = storage_id

        return True

    @skip_if_failed("_aborted", "_suppress_errors", False)
    @check_run_initialised
    @pydantic.validate_call
    def update_metadata(self, metadata: dict[str, typing.Any]) -> bool:
        """Update metadata for this run

        Parameters
        ----------
        metadata : dict[str, typing.Any]
            set run metadata

        Returns
        -------
        bool
            if the update was successful
        """
        if not self._sv_obj:
            self._error("Cannot update metadata, run not initialised")
            return False

        if not isinstance(metadata, dict):
            self._error("metadata must be a dict")
            return False

        if self._sv_obj:
            self._sv_obj.metadata = metadata
            self._sv_obj.commit()
            return True

        return True

    @skip_if_failed("_aborted", "_suppress_errors", False)
    @check_run_initialised
    @pydantic.validate_call
    def set_tags(self, tags: list[str]) -> bool:
        """Set tags for this run

        Parameters
        ----------
        tags : list[str]
            new set of tags to assign

        Returns
        -------
        bool
            whether the update was successful
        """
        if not self._sv_obj:
            self._error("Cannot update tags, run not initialised")
            return False

        self._sv_obj.tags = tags
        self._sv_obj.commit()

        return True

    @skip_if_failed("_aborted", "_suppress_errors", False)
    @check_run_initialised
    @pydantic.validate_call
    def update_tags(self, tags: list[str]) -> bool:
        """Add additional tags to this run without duplication

        Parameters
        ----------
        tags : list[str]
            new set of tags to attach

        Returns
        -------
        bool
            whether the update was successful
        """
        if not self._sv_obj:
            return False

        try:
            current_tags: list[str] = self._sv_obj.tags
        except RuntimeError as e:
            self._error(f"{e.args[0]}")
            return False

        try:
            self.set_tags(list(set(current_tags + tags)))
        except Exception as err:
            self._error(f"Failed to update tags: {err}")
            return False

        return True

    @skip_if_failed("_aborted", "_suppress_errors", False)
    @check_run_initialised
    @pydantic.validate_call
    def log_event(self, message: str, timestamp: str | None = None) -> bool:
        """Log event to the server

        Parameters
        ----------
        message : str
            event message to log
        timestamp : str, optional
            manually specify the time stamp for this log, by default None

        Returns
        -------
        bool
            whether event log was successful
        """
        if self._aborted:
            return False

        if not self._sv_obj or not self._dispatcher:
            self._error("Cannot log events, run not initialised")
            return False

        if not self._active:
            self._error("Run is not active")
            return False

        if self._status != "running":
            self._error("Cannot log events when not in the running state")
            return False

        if timestamp and not validate_timestamp(timestamp):
            self._error("Invalid timestamp format")
            return False

        _data = {"message": message, "timestamp": timestamp or self.time_stamp}
        self._dispatcher.add_item(_data, "events", self._queue_blocking)

        return True

    def _add_metrics_to_dispatch(
        self,
        metrics: dict[str, typing.Union[int, float]],
        step: typing.Optional[int] = None,
        time: typing.Optional[float] = None,
        timestamp: typing.Optional[str] = None,
        join_on_fail: bool = True,
    ) -> bool:
        if self._user_config.run.mode == "disabled":
            return True

        # If there are no metrics to log just ignore
        if not metrics:
            return True

        if not self._sv_obj or not self._dispatcher:
            self._error("Cannot log metrics, run not initialised", join_on_fail)
            return False

        if not self._active:
            self._error("Run is not active", join_on_fail)
            return False

        if self._status != "running":
            self._error(
                "Cannot log metrics when not in the running state", join_on_fail
            )
            return False

        if timestamp and not validate_timestamp(timestamp):
            self._error("Invalid timestamp format", join_on_fail)
            return False

        _data: dict[str, typing.Any] = {
            "values": metrics,
            "time": time if time is not None else self.duration,
            "timestamp": timestamp if timestamp is not None else self.time_stamp,
            "step": step if step is not None else self._step,
        }
        self._dispatcher.add_item(_data, "metrics", self._queue_blocking)

        return True

    @skip_if_failed("_aborted", "_suppress_errors", False)
    @check_run_initialised
    @pydantic.validate_call
    def log_metrics(
        self,
        metrics: dict[MetricKeyString, typing.Union[int, float]],
        step: typing.Optional[int] = None,
        time: typing.Optional[float] = None,
        timestamp: typing.Optional[str] = None,
    ) -> bool:
        """Log metrics to Simvue server

        Parameters
        ----------
        metrics : dict[str, typing.Union[int, float]]
            set of metrics to upload to server for this run
        step : int, optional
            manually specify the step index for this log, by default None
        time : int, optional
            manually specify the time for this log, by default None
        timestamp : str, optional
            manually specify the timestamp for this log, by default None

        Returns
        -------
        bool
            if the metric log was succcessful
        """
        add_dispatch = self._add_metrics_to_dispatch(
            metrics, step=step, time=time, timestamp=timestamp
        )
        self._step += 1
        return add_dispatch

    @skip_if_failed("_aborted", "_suppress_errors", False)
    @check_run_initialised
    @pydantic.validate_call
    def save_object(
        self,
        obj: typing.Any,
        category: typing.Literal["input", "output", "code"],
        name: typing.Optional[
            typing.Annotated[str, pydantic.Field(pattern=NAME_REGEX)]
        ] = None,
        allow_pickle: bool = False,
        metadata: dict[str, typing.Any] = None,
    ) -> bool:
        """Save an object to the Simvue server

        Parameters
        ----------
        obj : typing.Any
            object to serialize and send to the server
        category : Literal['input', 'output', 'code']
            category of file with respect to this run
        name : str, optional
            name to associate with this object, by default None
        allow_pickle : bool, optional
            whether to allow pickling if all other serialization types fail, by default False
        metadata : str | None, optional
            any metadata to attach to the artifact

        Returns
        -------
        bool
            whether object upload was successful
        """
        if not self._sv_obj or not self.id:
            self._error("Cannot save files, run not initialised")
            return False

        _name: str = name or f"{obj.__class__.__name__.lower()}_{id(obj)}"

        try:
            _artifact = Artifact.new_object(
                name=_name,
                obj=obj,
                allow_pickling=allow_pickle,
                storage_id=self._storage_id,
                metadata=metadata,
            )
            _artifact.attach_to_run(self.id, category)
        except (ValueError, RuntimeError) as e:
            self._error(f"Failed to save object '{_name}' to run '{self.id}': {e}")
            return False

        return True

    @skip_if_failed("_aborted", "_suppress_errors", False)
    @check_run_initialised
    @pydantic.validate_call
    def save_file(
        self,
        file_path: pydantic.FilePath,
        category: typing.Literal["input", "output", "code"],
        filetype: typing.Optional[str] = None,
        preserve_path: bool = False,
        name: typing.Optional[
            typing.Annotated[str, pydantic.Field(pattern=NAME_REGEX)]
        ] = None,
        metadata: dict[str, typing.Any] = None,
    ) -> bool:
        """Upload file to the server

        Parameters
        ----------
        file_path : pydantic.FilePath
            path to the file to upload
        category : Literal['input', 'output', 'code']
            category of file with respect to this run
        filetype : str, optional
            the MIME file type else this is deduced, by default None
        preserve_path : bool, optional
            whether to preserve the path during storage, by default False
        name : str, optional
            name to associate with this file, by default None
        metadata : str | None, optional
            any metadata to attach to the artifact

        Returns
        -------
        bool
            whether the upload was successful
        """
        if not self._sv_obj or not self.id:
            self._error("Cannot save files, run not initialised")
            return False

        if self._status == "created" and category == "output":
            self._error("Cannot upload output files for runs in the created state")
            return False

        stored_file_name: str = f"{file_path}"

        if preserve_path and stored_file_name.startswith("./"):
            stored_file_name = stored_file_name[2:]
        elif not preserve_path:
            stored_file_name = os.path.basename(file_path)

        try:
            # Register file
            _artifact = Artifact.new_file(
                name=name or stored_file_name,
                storage_id=self._storage_id,
                file_path=file_path,
                offline=self._user_config.run.mode == "offline",
                file_type=filetype,
                metadata=metadata,
            )
            _artifact.attach_to_run(self.id, category)
        except (ValueError, RuntimeError) as e:
            self._error(f"Failed to save file: {e}")
            return False

        return True

    @skip_if_failed("_aborted", "_suppress_errors", False)
    @check_run_initialised
    @pydantic.validate_call
    def save_directory(
        self,
        directory: pydantic.DirectoryPath,
        category: typing.Literal["output", "input", "code"],
        filetype: typing.Optional[str] = None,
        preserve_path: bool = False,
    ) -> bool:
        """Upload files from a whole directory

        Parameters
        ----------
        directory : pydantic.DirectoryPath
            the directory to save to the run
        category : Literal[['output', 'input', 'code']
            the category to assign to the saved objects within this directory
        filetype : str, optional
            manually specify the MIME type for items in the directory, by default None
        preserve_path : bool, optional
            preserve the full path, by default False

        Returns
        -------
        bool
            if the directory save was successful
        """
        if not self._sv_obj:
            self._error("Cannot save directory, run not inirialised")
            return False

        if filetype:
            mimetypes.init()
            mimetypes_valid = [value for _, value in mimetypes.types_map.items()]
            if filetype not in mimetypes_valid:
                self._error("Invalid MIME type specified")
                return False

        for dirpath, _, filenames in os.walk(directory):
            for filename in filenames:
                if (full_path := pathlib.Path(dirpath).joinpath(filename)).is_file():
                    self.save_file(full_path, category, filetype, preserve_path)

        return True

    @skip_if_failed("_aborted", "_suppress_errors", False)
    @check_run_initialised
    @pydantic.validate_call
    def save_all(
        self,
        items: list[typing.Union[pydantic.FilePath, pydantic.DirectoryPath]],
        category: typing.Literal["input", "output", "code"],
        filetype: typing.Optional[str] = None,
        preserve_path: bool = False,
    ) -> bool:
        """Save a set of files and directories

        Parameters
        ----------
        items : list[pydantic.FilePath | pydantic.DirectoryPath]
            list of file paths and directories to save
        category : Literal['input', 'output', 'code']
            the category to assign to the saved objects
        filetype : str, optional
            manually specify the MIME type for all items, by default None
        preserve_path : bool, optional
            _preserve the full path, by default False

        Returns
        -------
        bool
            whether the save was successful
        """
        for item in items:
            if item.is_file():
                save_file = self.save_file(item, category, filetype, preserve_path)
            elif item.is_dir():
                save_file = self.save_directory(item, category, filetype, preserve_path)
            else:
                self._error(f"{item}: No such file or directory")
                save_file = False
            if not save_file:
                return False

        return True

    @skip_if_failed("_aborted", "_suppress_errors", False)
    @check_run_initialised
    @pydantic.validate_call
    def set_status(
        self, status: typing.Literal["completed", "failed", "terminated"]
    ) -> bool:
        """Set run status

        status to assign to this run

        Parameters
        ----------
        status : Literal['completed', 'failed', 'terminated']
            status to set the run to

        Returns
        -------
        bool
            if status update was successful
        """
        if not self._active:
            self._error("Run is not active")
            return False

        self._status = status

        if self._sv_obj:
            self._sv_obj.status = status
            self._sv_obj.commit()
            return True

        return False

    def _tidy_run(self) -> None:
        self._executor.wait_for_completion()

        if self._emissions_tracker:
            with contextlib.suppress(Exception):
                self._emissions_tracker.stop()

        if self._heartbeat_thread and self._heartbeat_termination_trigger:
            self._heartbeat_termination_trigger.set()
            self._heartbeat_thread.join()

        if self._shutdown_event:
            self._shutdown_event.set()

        if self._status == "running":
            if self._dispatcher:
                self._dispatcher.join()
            if self._active:
                self.set_status("completed")
        elif self._dispatcher:
            self._dispatcher.purge()
            self._dispatcher.join()

        if _non_zero := self.executor.exit_status:
            _error_msgs: dict[str, typing.Optional[str]] = (
                self.executor.get_error_summary()
            )
            _error_msg = "\n".join(
                f"{identifier}:\n{msg}" for identifier, msg in _error_msgs.items()
            )
            if _error_msg:
                _error_msg = f":\n{_error_msg}"
            click.secho(
                "[simvue] Process executor terminated with non-zero exit status "
                f"{_non_zero}{_error_msg}",
                fg="red" if self._term_color else None,
                bold=self._term_color,
            )
            sys.exit(_non_zero)

    @skip_if_failed("_aborted", "_suppress_errors", False)
    def close(self) -> bool:
        """Close the run

        Returns
        -------
        bool
            whether close was successful
        """
        self._executor.wait_for_completion()

        if not self._sv_obj:
            self._error("Cannot close run, not initialised")
            return False

        if not self._active:
            self._error("Run is not active")
            return False

        self._tidy_run()

        return True

    @skip_if_failed("_aborted", "_suppress_errors", False)
    @check_run_initialised
    @pydantic.validate_call
    def set_folder_details(
        self,
        metadata: typing.Optional[dict[str, typing.Union[int, str, float]]] = None,
        tags: typing.Optional[list[str]] = None,
        description: typing.Optional[str] = None,
    ) -> bool:
        """Add metadata to the specified folder

        Parameters
        ----------
        metadata : dict[str, int | str | float], optional
            additional metadata to attach to this folder, by default None
        tags : list[str], optional
            list of tags to assign to the folder, by default None
        description : str, optional
            description to assign to this folder, by default None

        Returns
        -------
        bool
            returns True if update was successful
        """
        if not self._folder:
            self._error("Cannot update folder details, run was not initialised")
            return False

        if not self._active:
            self._error("Run is not active")
            return False

        try:
            self._folder.read_only(False)
            if metadata:
                self._folder.metadata = metadata
            if tags:
                self._folder.tags = tags
            if description:
                self._folder.description = description
            self._folder.commit()
            self._folder.read_only(True)
        except (RuntimeError, ValueError, pydantic.ValidationError) as e:
            self._error(f"Failed to update folder '{self._folder.name}' details: {e}")
            return False

        return True

    @skip_if_failed("_aborted", "_suppress_errors", False)
    @check_run_initialised
    @pydantic.validate_call
    def add_alerts(
        self,
        ids: typing.Optional[list[str]] = None,
        names: typing.Optional[list[str]] = None,
    ) -> bool:
        """Add a set of existing alerts to this run by name or id

        Parameters
        ----------
        ids : typing.list[str], optional
            unique identifiers of the alerts to attach, by default None
        names : typing.list[str], optional
            names of alerts to attach, by default None

        Returns
        -------
        bool
            returns True if successful
        """
        if not self._sv_obj:
            self._error("Cannot add alerts, run not initialised")
            return False

        ids = ids or []
        names = names or []

        if names and not ids:
            try:
                if alerts := Alert.get():
                    for alert in alerts:
                        if alert.name in names:
                            ids.append(alert.id)
            except RuntimeError as e:
                self._error(f"{e.args[0]}")
                return False
            else:
                self._error("No existing alerts")
                return False
        elif not names and not ids:
            self._error("Need to provide alert ids or alert names")
            return False

        # Avoid duplication
        self._sv_obj.alerts = list(set(self._sv_obj.alerts + [ids]))
        self._sv_obj.commit()

        return False

    @skip_if_failed("_aborted", "_suppress_errors", None)
    @check_run_initialised
    @pydantic.validate_call
    def create_alert(
        self,
        name: typing.Annotated[str, pydantic.Field(pattern=NAME_REGEX)],
        source: typing.Literal["events", "metrics", "user"] = "metrics",
        description: typing.Optional[str] = None,
        frequency: typing.Optional[pydantic.PositiveInt] = None,
        window: pydantic.PositiveInt = 5,
        rule: typing.Optional[
            typing.Literal[
                "is above", "is below", "is inside range", "is outside range"
            ]
        ] = None,
        metric: typing.Optional[str] = None,
        threshold: typing.Optional[float] = None,
        range_low: typing.Optional[float] = None,
        range_high: typing.Optional[float] = None,
        aggregation: typing.Optional[
            typing.Literal["average", "sum", "at least one", "all"]
        ] = "average",
        notification: typing.Literal["email", "none"] = "none",
        pattern: typing.Optional[str] = None,
        trigger_abort: bool = False,
    ) -> typing.Optional[str]:
        """Creates an alert with the specified name (if it doesn't exist)
        and applies it to the current run. If alert already exists it will
        not be duplicated.

        Note available arguments depend on the alert source:

        Event
        =====

        Alerts triggered based on the contents of an event message, arguments are:
            - frequency
            - pattern

        Metrics
        =======

        Alerts triggered based on metric value condictions, arguments are:
            - frequency
            - rule
            - window
            - aggregation
            - metric
            - threshold / (range_low, range_high)

        User
        ====

        User defined alerts, manually triggered.

        Parameters
        ----------
        name : str
            name of alert
        source : Literal['events', 'metrics', 'user'], optional
            the source which triggers this alert based on status, either
            event based, metric values or manual user defined trigger. By default "metrics".
        description : str, optional
            description for this alert
        frequency : PositiveInt, optional
            frequency at which to check alert condition in seconds, by default None
        window : PositiveInt, optional
            time period in seconds over which metrics are averaged, by default 5
        rule : Literal['is above', 'is below', 'is inside', 'is outside range'], optional
            rule defining metric based alert conditions, by default None
        metric : str, optional
            metric to monitor, by default None
        threshold : float, optional
            the threshold value if 'rule' is 'is below' or 'is above', by default None
        range_low : float, optional
            the lower bound value if 'rule' is 'is inside range' or 'is outside range', by default None
        range_high : float, optional
            the upper bound value if 'rule' is 'is inside range' or 'is outside range', by default None
        aggregation : Literal['average', 'sum', 'at least one', 'all'], optional
            method to use when aggregating metrics within time window, default 'average'.
        notification : Literal['email', 'none'], optional
            whether to notify on trigger, by default "none"
        pattern : str, optional
            for event based alerts pattern to look for, by default None
        trigger_abort : bool, optional
            whether this alert can trigger a run abort

        Returns
        -------
        str | None
            returns the created alert ID if successful
        """
        if not self._sv_obj:
            self._error("Cannot add alert, run not initialised")
            return None

        if rule in ("is below", "is above") and threshold is None:
            self._error("threshold must be defined for the specified alert type")
            return None

        if rule in ("is outside range", "is inside range") and (
            range_low is None or range_high is None
        ):
            self._error(
                "range_low and range_high must be defined for the specified alert type"
            )
            return None

        _alert: EventsAlert | MetricsRangeAlert | MetricsThresholdAlert | UserAlert

        if source == "metrics" and threshold:
            if not metric or not aggregation or not rule:
                self._error("Missing arguments for alert of type 'metric threshold'")
                return None

            _alert = MetricsThresholdAlert.new(
                name=name,
                metric=metric,
                window=window,
                aggregation=aggregation,
                rule=rule,
                notification=notification,
                threshold=threshold,
                frequency=frequency or 60,
                offline=self._user_config.run.mode == "offline",
            )
        elif source == "metrics":
            if (
                not metric
                or not aggregation
                or not rule
                or not range_low
                or not range_high
            ):
                self._error("Missing arguments for alert of type 'metric range'")
                return None

            _alert = MetricsRangeAlert.new(
                name=name,
                metric=metric,
                window=window,
                aggregation=aggregation,
                notification=notification,
                rule=rule,
                range_low=range_low,
                range_high=range_high,
                frequency=frequency or 60,
                offline=self._user_config.run.mode == "offline",
            )
        elif source == "events":
            if not pattern:
                self._error("Missing arguments for alert of type 'events'")
                return None

            _alert = EventsAlert.new(
                name=name,
                pattern=pattern,
                notification=notification,
                frequency=frequency or 60,
                offline=self._user_config.run.mode == "offline",
            )
        else:
            _alert = UserAlert.new(
                name=name,
                notification=notification,
                offline=self._user_config.run.mode == "offline",
            )

        _alert.abort = trigger_abort

        # Check if the alert already exists
        _alert_id: typing.Optional[str] = None

        for _, _existing_alert in Alert.get():
            if _existing_alert.compare(_alert):
                _alert_id = _existing_alert.id
                logger.info("Existing alert found with id: %s", _existing_alert.id)
                break

        if not _alert_id:
            _alert.commit()
            _alert_id = _alert.id

        self._sv_obj.alerts = [_alert_id]

        self._sv_obj.commit()

        return _alert_id

    @skip_if_failed("_aborted", "_suppress_errors", False)
    @check_run_initialised
    @pydantic.validate_call
    def log_alert(
        self, identifier: str, state: typing.Literal["ok", "critical"]
    ) -> bool:
        """Set the state of an alert

        Parameters
        ----------
        identifier : str
            identifier of alert to update
        state : Literal['ok', 'critical']
            state to set alert to

        Returns
        -------
        bool
            whether alert state update was successful
        """
        if state not in ("ok", "critical"):
            self._error('state must be either "ok" or "critical"')
            return False

        _alert = Alert(identifier=identifier)
        if not isinstance(_alert, UserAlert):
            self._error(
                f"Cannot update state for alert '{identifier}' "
                f"of type '{_alert.__class__.__name__.lower()}'"
            )
            return False
        _alert.read_only(False)
        _alert.set_state(run_id=self._id, state=state)
        _alert.commit()

        return True
