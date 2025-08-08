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
import randomname
import click
import psutil

from simvue.api.objects.alert.fetch import Alert
from simvue.api.objects.folder import Folder
from simvue.exception import SimvueRunError
from simvue.utilities import prettify_pydantic


from .config.user import SimvueConfiguration

from .factory.dispatch import Dispatcher
from .executor import Executor
from .metrics import SystemResourceMeasurement
from .models import FOLDER_REGEX, NAME_REGEX, MetricKeyString
from .system import get_system
from .metadata import git_info, environment
from .eco import CO2Monitor
from .utilities import (
    skip_if_failed,
    validate_timestamp,
    simvue_timestamp,
)
from .api.objects import (
    Run as RunObject,
    FileArtifact,
    ObjectArtifact,
    MetricsThresholdAlert,
    MetricsRangeAlert,
    UserAlert,
    EventsAlert,
    Events,
    Metrics,
)

try:
    from typing import Self
except ImportError:
    from typing_extensions import Self  # noqa: F401


if typing.TYPE_CHECKING:
    from .factory.dispatch import DispatcherBaseClass

HEARTBEAT_INTERVAL: int = 60
RESOURCES_METRIC_PREFIX: str = "resources"

logger = logging.getLogger(__name__)


def check_run_initialised(
    function: typing.Callable[..., typing.Any],
) -> typing.Callable[..., typing.Any]:
    @functools.wraps(function)
    def _wrapper(self: Self, *args: typing.Any, **kwargs: typing.Any) -> typing.Any:
        # Tidy pydantic errors
        _function = prettify_pydantic(function)

        if self._user_config.run.mode == "disabled":
            return True

        if self._retention and time.time() - self._timer > self._retention:
            self._active = False
            raise RuntimeError("Cannot update expired Simvue Run")

        if not self._sv_obj:
            raise RuntimeError(
                f"Simvue Run must be initialised before calling '{function.__name__}'"
            )
        return _function(self, *args, **kwargs)

    return _wrapper


class Run:
    """Track simulation details based on token and URL.

    The Run class provides a way of monitoring simulation runs by logging metrics
    and creating alerts based on such metrics. The recommended usage is as a
    context manager to ensure the run is closed upon completion.
    """

    @pydantic.validate_call
    def __init__(
        self,
        mode: typing.Literal["online", "offline", "disabled"] = "online",
        abort_callback: typing.Callable[[Self], None] | None = None,
        server_token: pydantic.SecretStr | None = None,
        server_url: str | None = None,
        debug: bool = False,
    ) -> None:
        """Initialise a new Simvue run

        If `abort_callback` is provided the first argument must be this Run instance

        Parameters
        ----------
        mode : Literal['online', 'offline', 'disabled'], optional
            mode of running
                * online - objects sent directly to Simvue server
                * offline - everything is written to disk for later dispatch
                * disabled - disable monitoring completely
        abort_callback : Callable | None, optional
            callback executed when the run is aborted
        server_token : str, optional
            overwrite value for server token, default is None
        server_url : str, optional
            overwrite value for server URL, default is None
        debug : bool, optional
            run in debug mode, default is False

        Examples
        --------

        ```python
        with simvue.Run() as run:
            ...
        ```
        """
        self._uuid: str = f"{uuid.uuid4()}"

        # monitor duration with respect to retention period
        self._timer: float = 0
        self._retention: float | None = None

        # Keep track of if the Run class has been intialised
        # through a context manager
        self._context_manager_called: bool = False

        self._testing: bool = False
        self._abort_on_alert: typing.Literal["run", "terminate", "ignore"] = "terminate"
        self._abort_callback: typing.Callable[[Self], None] | None = abort_callback
        self._dispatch_mode: typing.Literal["direct", "queued"] = "queued"

        self._executor = Executor(self)
        self._dispatcher: DispatcherBaseClass | None = None

        self._folder: Folder | None = None
        self._term_color: bool = True
        self._suppress_errors: bool = False
        self._queue_blocking: bool = False
        self._status: (
            typing.Literal[
                "created", "running", "completed", "failed", "terminated", "lost"
            ]
            | None
        ) = None
        self._data: dict[str, typing.Any] = {}
        self._step: int = 0
        self._active: bool = False
        self._user_config: SimvueConfiguration = SimvueConfiguration.fetch(
            server_url=server_url, server_token=server_token, mode=mode
        )

        logging.getLogger(self.__class__.__module__).setLevel(
            logging.DEBUG
            if (debug is not None and debug)
            or (debug is None and self._user_config.client.debug)
            else logging.INFO
        )

        self._aborted: bool = False
        self._system_metrics_interval: int | None = (
            HEARTBEAT_INTERVAL
            if self._user_config.metrics.system_metrics_interval < 1
            else self._user_config.metrics.system_metrics_interval
        )
        self._headers: dict[str, str] = (
            {
                "Authorization": f"Bearer {self._user_config.server.token.get_secret_value()}",
                "Accept-Encoding": "gzip",
            }
            if mode != "offline"
            else {}
        )
        self._sv_obj: RunObject | None = None
        self._pid: int | None = 0
        self._shutdown_event: threading.Event | None = None
        self._configuration_lock = threading.Lock()
        self._heartbeat_termination_trigger: threading.Event | None = None
        self._storage_id: str | None = None
        self._heartbeat_thread: threading.Thread | None = None

        self._heartbeat_interval: int = HEARTBEAT_INTERVAL
        self._emissions_monitor: CO2Monitor | None = None

    def __enter__(self) -> Self:
        self._context_manager_called = True
        return self

    def _handle_exception_throw(
        self,
        exc_type: typing.Type[BaseException] | None,
        value: BaseException,
        traceback: typing.Type[BaseException] | BaseException | None,
    ) -> None:
        _exception_thrown: str | None = exc_type.__name__ if exc_type else None
        _is_running: bool = self._status == "running"
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

        # If the dispatcher has already been aborted then this will
        # fail so just continue without the event
        with contextlib.suppress(RuntimeError):
            self.log_event(_event_msg)

        self.set_status("terminated" if _is_terminated else "failed")

    def __exit__(
        self,
        exc_type: typing.Type[BaseException] | None,
        value: BaseException,
        traceback: typing.Type[BaseException] | BaseException | None,
    ) -> None:
        logger.debug(
            "Automatically closing run '%s' in status %s",
            self.id
            if self._user_config.run.mode == "online" and self._sv_obj
            else "unregistered",
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
        process_list += self._child_processes

        return list(set(process_list))

    def _terminate_run(
        self,
        abort_callback: typing.Callable[[Self], None] | None,
        force_exit: bool = True,
    ) -> None:
        """Close the current simvue Run and its subprocesses.

        Closes the run and all subprocesses with the default to being also.
        To abort the actual Python execution as well.

        Parameters
        ----------
        abort_callback: Callable, optional
            the callback to execute on the termination else None
        force_exit: bool, optional
            whether to close Python itself, the default is True
        """
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
            os._exit(1) if force_exit else sys.exit(1)

    def _get_internal_metrics(
        self,
        system_metrics_step: int,
    ) -> None:
        """Refresh resource and emissions metrics.

        Checks if the refresh interval has been satisfied for emissions
        and resource metrics, if so adds latest values to dispatch.

        Parameters
        ----------
        system_metrics_step: int
            The current step for this system metric record

        Return
        ------
        tuple[float, float]
            new resource metric measure time
            new emissions metric measure time
        """

        # In order to get a resource metric reading at t=0
        # because there is no previous CPU reading yet we cannot
        # use the default of None for the interval here, so we measure
        # at an interval of 1s.
        _current_system_measure = SystemResourceMeasurement(
            self.processes,
            interval=1 if system_metrics_step == 0 else None,
        )

        # Set join on fail to false as if an error is thrown
        # join would be called on this thread and a thread cannot
        # join itself!
        if self.status == "running":
            self._add_metrics_to_dispatch(
                _current_system_measure.to_dict(),
                join_on_fail=False,
                step=system_metrics_step,
            )

        # For the first emissions metrics reading, the time interval to use
        # Is the time since the run started, otherwise just use the time between readings
        if self._emissions_monitor:
            _estimated = self._emissions_monitor.estimate_co2_emissions(
                process_id=f"{self._sv_obj.name}",
                cpu_percent=_current_system_measure.cpu_percent,
                measure_interval=(time.time() - self._start_time)
                if system_metrics_step == 0
                else self._system_metrics_interval,
                gpu_percent=_current_system_measure.gpu_percent,
            )
            if _estimated and self.status == "running":
                self._add_metrics_to_dispatch(
                    self._emissions_monitor.simvue_metrics(),
                    join_on_fail=False,
                    step=system_metrics_step,
                )

    def _create_heartbeat_callback(
        self,
    ) -> typing.Callable[[threading.Event], None]:
        """Defines the callback executed at the heartbeat interval for the Run."""
        if (
            self._user_config.run.mode == "online"
            and (not self._user_config.server.url or not self.id)
        ) or not self._heartbeat_termination_trigger:
            raise RuntimeError("Could not commence heartbeat, run not initialised")

        def _heartbeat(
            heartbeat_trigger: threading.Event
            | None = self._heartbeat_termination_trigger,
            abort_callback: typing.Callable[[Self], None] | None = self._abort_callback,
        ) -> None:
            if not heartbeat_trigger:
                raise RuntimeError("Expected initialisation of heartbeat")

            last_heartbeat: float = 0
            last_sys_metric_call: float = 0

            sys_step: int = 0

            while not heartbeat_trigger.is_set():
                with self._configuration_lock:
                    _current_time: float = time.time()

                    _update_system_metrics: bool = (
                        self._system_metrics_interval is not None
                        and _current_time - last_sys_metric_call
                        > self._system_metrics_interval
                        and self._status == "running"
                    )

                    if _update_system_metrics:
                        self._get_internal_metrics(system_metrics_step=sys_step)
                        sys_step += 1

                    last_sys_metric_call = (
                        _current_time
                        if _update_system_metrics
                        else last_sys_metric_call
                    )

                if time.time() - last_heartbeat < self._heartbeat_interval:
                    time.sleep(1)
                    continue

                last_heartbeat = time.time()

                # Check if the user has aborted the run
                with self._configuration_lock:
                    if self._sv_obj and self._sv_obj.abort_trigger:
                        self._terminate_run(abort_callback=abort_callback)

                if self._sv_obj:
                    self._sv_obj.send_heartbeat()

                time.sleep(1)

        return _heartbeat

    def _create_dispatch_callback(
        self,
    ) -> typing.Callable:
        """Generates the relevant callback for posting of metrics and events

        The generated callback is assigned to the dispatcher instance and is
        executed on metrics and events objects held in a buffer.
        """

        if self._user_config.run.mode == "online" and not self.id:
            raise RuntimeError("Expected identifier for run")

        if (
            self._user_config.run.mode != "offline" and not self._user_config.server.url
        ) or not self._sv_obj:
            raise RuntimeError("Cannot commence dispatch, run not initialised")

        def _dispatch_callback(
            buffer: list[typing.Any],
            category: typing.Literal["events", "metrics"],
        ) -> None:
            if category == "events":
                _events = Events.new(
                    run=self.id,
                    offline=self._user_config.run.mode == "offline",
                    events=buffer,
                )
                return _events.commit()
            else:
                _metrics = Metrics.new(
                    run=self.id,
                    offline=self._user_config.run.mode == "offline",
                    metrics=buffer,
                )
                return _metrics.commit()

        return _dispatch_callback

    def _start(self) -> bool:
        """Start a run

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

        self._start_time = time.time()

        if self._sv_obj:
            _changed = False
            if self._sv_obj.status != "running":
                self._sv_obj.status = self._status
                _changed = True
            if self._user_config.run.mode == "offline":
                self._sv_obj.started = self._start_time
                _changed = True
            if _changed:
                self._sv_obj.commit()

        if self._pid == 0:
            self._pid = os.getpid()

        self._parent_process = psutil.Process(self._pid) if self._pid else None
        self._child_processes = (
            self._get_child_processes() if self._parent_process else None
        )

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
                target=self._create_heartbeat_callback(),
                daemon=True,
                name=f"{self.id}_heartbeat",
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
        tags: list[str] | None = None,
        description: str | None = None,
        folder: typing.Annotated[
            str, pydantic.Field(None, pattern=FOLDER_REGEX)
        ] = None,
        notification: typing.Literal["none", "all", "error", "lost"] = "none",
        running: bool = True,
        retention_period: str | None = None,
        timeout: int | None = 180,
        visibility: typing.Literal["public", "tenant"] | list[str] | None = None,
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
        notification: typing.Literal["none", "all", "error", "lost"], optional
            email notification on completion settings
                * none - do not notify (default).
                * all - notify for all updates.
                * error - notify on errors.
                * lost - notify if run lost.
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

        if self._user_config.run.mode != "offline" and (
            not self._user_config.server.token or not self._user_config.server.url
        ):
            self._error(
                "Unable to get URL and token from environment variables or config file"
            )
            return False

        if name and not re.match(r"^[a-zA-Z0-9\-\_\s\/\.:]+$", name):
            self._error("specified name is invalid")
            return False
        elif not name and self._user_config.run.mode == "offline":
            name = randomname.get_name()

        self._status = "running" if running else "created"

        # Parse the time to live/retention time if specified
        try:
            if retention_period:
                self._retention: int | None = int(
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

        self._sv_obj.visibility.tenant = visibility == "tenant"
        self._sv_obj.visibility.public = visibility == "public"
        self._sv_obj.visibility.users = (
            visibility if isinstance(visibility, list) else []
        )
        self._sv_obj.ttl = self._retention
        self._sv_obj.status = self._status
        self._sv_obj.tags = tags
        self._sv_obj.metadata = (metadata or {}) | git_info(os.getcwd()) | environment()
        self._sv_obj.heartbeat_timeout = timeout
        self._sv_obj.alerts = []
        self._sv_obj.created = time.time()
        self._sv_obj.notifications = notification
        self._sv_obj._staging["folder_id"] = self._folder.id

        if self._status == "running":
            self._sv_obj.system = get_system()

        self._data = self._sv_obj._staging
        self._sv_obj.commit()

        if not self.name:
            return False

        if self._status == "running":
            self._start()

        if self._user_config.run.mode == "online":
            click.secho(
                f"[simvue] Run {self.name} created",
                bold=self._term_color,
                fg="green" if self._term_color else None,
            )
            click.secho(
                f"[simvue] Monitor in the UI at {self._user_config.server.url.rsplit('/api', 1)[0]}/dashboard/runs/run/{self.id}",
                bold=self._term_color,
                fg="green" if self._term_color else None,
            )

        return True

    @skip_if_failed("_aborted", "_suppress_errors", None)
    @pydantic.validate_call(config={"arbitrary_types_allowed": True})
    def add_process(
        self,
        identifier: str,
        *cmd_args,
        executable: str | pathlib.Path | None = None,
        script: pydantic.FilePath | None = None,
        input_file: pydantic.FilePath | None = None,
        completion_callback: typing.Optional[
            typing.Callable[[int, str, str], None]
        ] = None,
        completion_trigger: multiprocessing.synchronize.Event | None = None,
        env: dict[str, str] | None = None,
        cwd: pathlib.Path | None = None,
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
        env : dict[str, str], optional
            environment variables for process
        cwd: pathlib.Path | None, optional
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

        cmd_list: list[str] = []
        pos_args = list(cmd_args)
        executable_str: str | None = None

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

    def _get_child_processes(self) -> list[psutil.Process]:
        _process_list = []
        # Attach child processes relating to the process set by set_pid
        with contextlib.suppress(psutil.NoSuchProcess, psutil.ZombieProcess):
            for child in self._parent_process.children(recursive=True):
                if child not in _process_list:
                    _process_list.append(child)

        return list(set(_process_list))

    @property
    def executor(self) -> Executor:
        """Return the executor for this run"""
        return self._executor

    @property
    def name(self) -> str | None:
        """Return the name of the run"""
        if not self._sv_obj:
            logger.warning(
                "Attempted to get name on non initialized run - returning None"
            )
            return None
        return self._sv_obj.name

    @property
    def status(
        self,
    ) -> (
        typing.Literal[
            "created", "running", "completed", "failed", "terminated", "lost"
        ]
        | None
    ):
        """Return the status of the run"""
        if not self._sv_obj:
            logger.warning(
                "Attempted to get name on non initialized run - returning cached value"
            )
            return self._status
        return self._sv_obj.status

    @property
    def uid(self) -> str:
        """Return the local unique identifier of the run"""
        return self._uuid

    @property
    def id(self) -> str | None:
        """Return the unique id of the run"""
        if not self._sv_obj:
            logger.warning(
                "Attempted to get name on non initialized run - returning None"
            )
            return None
        return self._sv_obj.id

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

        self._sv_obj = RunObject(identifier=run_id, _read_only=False)

        self._sv_obj.status = self._status
        self._sv_obj.system = get_system()
        self._sv_obj.commit()
        self._start()

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
        self._parent_process = psutil.Process(self._pid)
        self._child_processes = self._get_child_processes()
        # Get CPU usage stats for each of those new processes, so that next time it's measured by the heartbeat the value is accurate
        [
            _process.cpu_percent()
            for _process in self._child_processes + [self._parent_process]
        ]

    @skip_if_failed("_aborted", "_suppress_errors", False)
    @pydantic.validate_call
    def config(
        self,
        *,
        suppress_errors: bool | None = None,
        queue_blocking: bool | None = None,
        system_metrics_interval: pydantic.PositiveInt | None = None,
        enable_emission_metrics: bool | None = None,
        disable_resources_metrics: bool | None = None,
        storage_id: str | None = None,
        abort_on_alert: typing.Literal["run", "all", "ignore"] | bool | None = None,
    ) -> bool:
        """Optional configuration

        Parameters
        ----------
        suppress_errors : bool, optional
            disable exception throwing instead putting Simvue into a
            dormant state if an error occurs
        queue_blocking : bool, optional
            block thread queues during metric/event recording
        system_metrics_interval : int, optional
            frequency at which to collect resource and emissions metrics, if enabled
        enable_emission_metrics : bool, optional
            enable monitoring of emission metrics
        disable_resources_metrics : bool, optional
            disable monitoring of resource metrics
        storage_id : str, optional
            identifier of storage to use, by default None
        abort_on_alert : Literal['ignore', run', 'terminate'], optional
            whether to abort when an alert is triggered.
                * run - current run is aborted.
                * terminate - script itself is terminated.
                * ignore - alerts do not affect this run.

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

            if system_metrics_interval and disable_resources_metrics:
                self._error(
                    "Setting of resource metric interval and disabling resource metrics is ambiguous"
                )
                return False

            if system_metrics_interval:
                self._system_metrics_interval = system_metrics_interval

            if disable_resources_metrics:
                if self._emissions_monitor:
                    self._error(
                        "Emissions metrics require resource metrics collection."
                    )
                    return False
                self._pid = None
                self._system_metrics_interval = None

            if enable_emission_metrics:
                if not self._system_metrics_interval:
                    self._error(
                        "Emissions metrics require resource metrics collection - make sure resource metrics are enabled!"
                    )
                    return False
                if self._user_config.run.mode == "offline":
                    # Create an emissions monitor with no API calls
                    self._emissions_monitor = CO2Monitor(
                        intensity_refresh_interval=None,
                        co2_intensity=self._user_config.eco.co2_intensity,
                        local_data_directory=self._user_config.offline.cache,
                        co2_signal_api_token=None,
                        thermal_design_power_per_cpu=self._user_config.eco.cpu_thermal_design_power,
                        thermal_design_power_per_gpu=self._user_config.eco.gpu_thermal_design_power,
                        offline=True,
                    )
                else:
                    self._emissions_monitor = CO2Monitor(
                        intensity_refresh_interval=self._user_config.eco.intensity_refresh_interval,
                        local_data_directory=self._user_config.offline.cache,
                        co2_signal_api_token=self._user_config.eco.co2_signal_api_token,
                        co2_intensity=self._user_config.eco.co2_intensity,
                        thermal_design_power_per_cpu=self._user_config.eco.cpu_thermal_design_power,
                        thermal_design_power_per_gpu=self._user_config.eco.gpu_thermal_design_power,
                    )

            elif enable_emission_metrics is False and self._emissions_monitor:
                self._error("Cannot disable emissions monitor once it has been started")

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
        metrics: dict[str, int | float],
        step: int | None = None,
        time: float | None = None,
        timestamp: str | None = None,
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
        metrics: dict[MetricKeyString, int | float],
        step: int | None = None,
        time: float | None = None,
        timestamp: str | None = None,
    ) -> bool:
        """Log metrics to Simvue server

        Parameters
        ----------
        metrics : dict[str, int | float]
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
                * input - this file is an input file.
                * output - this file is created by the run.
                * code - this file represents an executed script
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
            _artifact = ObjectArtifact.new(
                name=_name,
                obj=obj,
                allow_pickling=allow_pickle,
                storage=self._storage_id,
                metadata=metadata,
                offline=self._user_config.run.mode == "offline",
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
        file_type: str | None = None,
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
                * input - this file is an input file.
                * output - this file is created by the run.
                * code - this file represents an executed script
        file_type : str, optional
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
            _artifact = FileArtifact.new(
                name=name or stored_file_name,
                storage=self._storage_id,
                file_path=file_path,
                offline=self._user_config.run.mode == "offline",
                mime_type=file_type,
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
        file_type: str | None = None,
        preserve_path: bool = False,
    ) -> bool:
        """Upload files from a whole directory

        Parameters
        ----------
        directory : pydantic.DirectoryPath
            the directory to save to the run
        category : Literal['input', 'output', 'code']
            category of file with respect to this run
                * input - this file is an input file.
                * output - this file is created by the run.
                * code - this file represents an executed script
        file_type : str, optional
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

        if file_type:
            mimetypes.init()
            mimetypes_valid = [value for _, value in mimetypes.types_map.items()]
            if file_type not in mimetypes_valid:
                self._error("Invalid MIME type specified")
                return False

        for dirpath, _, filenames in os.walk(directory):
            for filename in filenames:
                if (full_path := pathlib.Path(dirpath).joinpath(filename)).is_file():
                    self.save_file(full_path, category, file_type, preserve_path)

        return True

    @skip_if_failed("_aborted", "_suppress_errors", False)
    @check_run_initialised
    @pydantic.validate_call
    def save_all(
        self,
        items: list[pydantic.FilePath | pydantic.DirectoryPath],
        category: typing.Literal["input", "output", "code"],
        file_type: str | None = None,
        preserve_path: bool = False,
    ) -> bool:
        """Save a set of files and directories

        Parameters
        ----------
        items : list[pydantic.FilePath | pydantic.DirectoryPath]
            list of file paths and directories to save
        category : Literal['input', 'output', 'code']
            category of file with respect to this run
                * input - this file is an input file.
                * output - this file is created by the run.
                * code - this file represents an executed script
        file_type : str, optional
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
                save_file = self.save_file(item, category, file_type, preserve_path)
            elif item.is_dir():
                save_file = self.save_directory(
                    item, category, file_type, preserve_path
                )
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

        status to assign to this run once finished

        Parameters
        ----------
        status : Literal['completed', 'failed', 'terminated']
            status to set the run to
                * completed - run finished with zero exit status.
                * failed - run failed to complete.
                * terminated - run was aborted.

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
            self._sv_obj.endtime = time.time()
            self._sv_obj.commit()
            return True

        return False

    def _tidy_run(self) -> None:
        self._executor.wait_for_completion()

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

        if (
            self._sv_obj
            and self._user_config.run.mode == "offline"
            and self._status != "created"
        ):
            self._user_config.offline.cache.joinpath(
                "runs", f"{self.id}.closed"
            ).touch()

        if _non_zero := self.executor.exit_status:
            _error_msgs: dict[str, str] | None = self.executor.get_error_summary()
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
        if self._context_manager_called:
            self._error("Cannot call close method in context manager.")
            return

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
        metadata: dict[str, int | str | float] | None = None,
        tags: list[str] | None = None,
        description: str | None = None,
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
            if metadata:
                self._folder.metadata = metadata
            if tags:
                self._folder.tags = tags
            if description:
                self._folder.description = description
            self._folder.commit()
        except (RuntimeError, ValueError, pydantic.ValidationError) as e:
            self._error(f"Failed to update folder '{self._folder.name}' details: {e}")
            return False

        return True

    @skip_if_failed("_aborted", "_suppress_errors", False)
    @check_run_initialised
    @pydantic.validate_call
    def add_alerts(
        self,
        ids: list[str] | None = None,
        names: list[str] | None = None,
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
            if self._user_config.run.mode == "offline":
                self._error(
                    "Cannot retrieve alerts based on names in offline mode - please use IDs instead."
                )
                return False
            try:
                if alerts := Alert.get(offline=self._user_config.run.mode == "offline"):
                    ids += [id for id, alert in alerts if alert.name in names]
                else:
                    self._error("No existing alerts")
                    return False
            except RuntimeError as e:
                self._error(f"{e.args[0]}")
                return False
        elif not names and not ids:
            self._error("Need to provide alert ids or alert names")
            return False

        # Avoid duplication
        _deduplicated = list(set(self._sv_obj.alerts + ids))
        self._sv_obj.alerts = _deduplicated
        self._sv_obj.commit()

        return True

    @skip_if_failed("_aborted", "_suppress_errors", None)
    @pydantic.validate_call
    def create_metric_range_alert(
        self,
        name: typing.Annotated[str, pydantic.Field(pattern=NAME_REGEX)],
        metric: str,
        range_low: float,
        range_high: float,
        rule: typing.Literal["is inside range", "is outside range"],
        *,
        description: str | None = None,
        window: pydantic.PositiveInt = 5,
        frequency: pydantic.PositiveInt = 1,
        aggregation: typing.Literal[
            "average", "sum", "at least one", "all"
        ] = "average",
        notification: typing.Literal["email", "none"] = "none",
        trigger_abort: bool = False,
        attach_to_run: bool = True,
    ) -> str | None:
        """Creates a metric range alert with the specified name (if it doesn't exist)
        and applies it to the current run. If alert already exists it will
        not be duplicated.

        Parameters
        ----------
        name : str
            name of alert
        metric : str
            metric to monitor
        range_low : float
            the lower bound value
        range_high : float, optional
            the upper bound value
        rule : Literal['is inside range', 'is outside range']
            * is inside range - metric value falls within value range.
            * is outside range - metric value falls outside of value range.
        description : str, optional
            description for this alert, default None
        window : PositiveInt, optional
            time period in seconds over which metrics are averaged, by default 5
        frequency : PositiveInt, optional
            frequency at which to check alert condition in seconds, by default 1
        aggregation : Literal['average', 'sum', 'at least one', 'all'], optional
            method to use when aggregating metrics within time window
                * average - average across all values in window (default).
                * sum - take the sum of all values within window.
                * at least one - returns if at least one value in window satisfy condition.
                * all - returns if all values in window satisfy condition.
        notification : Literal['email', 'none'], optional
            whether to notify on trigger
                * email - send email to user on notify.
                * none - send no notifications (default).
        trigger_abort : bool, optional
            whether this alert can trigger a run abort, default False
        attach_to_run : bool, optional
            whether to attach this alert to the current run, default True

        Returns
        -------
        str | None
            returns the created alert ID if successful

        """
        _alert = MetricsRangeAlert.new(
            name=name,
            description=description,
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
        _alert.abort = trigger_abort
        _alert.commit()
        if attach_to_run:
            self.add_alerts(ids=[_alert.id])
        return _alert.id

    @skip_if_failed("_aborted", "_suppress_errors", None)
    @pydantic.validate_call
    def create_metric_threshold_alert(
        self,
        name: typing.Annotated[str, pydantic.Field(pattern=NAME_REGEX)],
        metric: str,
        threshold: float,
        rule: typing.Literal["is above", "is below"],
        *,
        description: str | None = None,
        window: pydantic.PositiveInt = 5,
        frequency: pydantic.PositiveInt = 1,
        aggregation: typing.Literal[
            "average", "sum", "at least one", "all"
        ] = "average",
        notification: typing.Literal["email", "none"] = "none",
        trigger_abort: bool = False,
        attach_to_run: bool = True,
    ) -> str | None:
        """Creates a metric threshold alert with the specified name (if it doesn't exist)
        and applies it to the current run. If alert already exists it will
        not be duplicated.

        Parameters
        ----------
        name : str
            name of alert
        metric : str
            metric to monitor
        threshold : float
            the threshold value
        rule : Literal['is above', 'is below']
            rule defining threshold alert conditions
                * is above - value is above threshold.
                * is below - value is below threshold.
        description : str, optional
            description for this alert, default None
        window : PositiveInt, optional
            time period in seconds over which metrics are averaged, by default 5
        frequency : PositiveInt, optional
            frequency at which to check alert condition in seconds, by default 1
        aggregation : Literal['average', 'sum', 'at least one', 'all'], optional
            method to use when aggregating metrics within time window
                * average - average across all values in window (default).
                * sum - take the sum of all values within window.
                * at least one - returns if at least one value in window satisfy condition.
                * all - returns if all values in window satisfy condition.
        notification : Literal['email', 'none'], optional
            whether to notify on trigger
                * email - send email to user on alert.
                * none - send no notifications (default).
        trigger_abort : bool, optional
            whether this alert can trigger a run abort, default False
        attach_to_run : bool, optional
            whether to attach this alert to the current run, default True

        Returns
        -------
        str | None
            returns the created alert ID if successful

        """
        _alert = MetricsThresholdAlert.new(
            name=name,
            metric=metric,
            description=description,
            threshold=threshold,
            rule=rule,
            window=window,
            frequency=frequency,
            aggregation=aggregation,
            notification=notification,
            offline=self._user_config.run.mode == "offline",
        )

        _alert.abort = trigger_abort
        _alert.commit()
        if attach_to_run:
            self.add_alerts(ids=[_alert.id])
        return _alert.id

    @skip_if_failed("_aborted", "_suppress_errors", None)
    @pydantic.validate_call
    def create_event_alert(
        self,
        name: str,
        pattern: str,
        *,
        description: str | None = None,
        frequency: pydantic.PositiveInt = 1,
        notification: typing.Literal["email", "none"] = "none",
        trigger_abort: bool = False,
        attach_to_run: bool = True,
    ) -> str | None:
        """Creates an events alert with the specified name (if it doesn't exist)
        and applies it to the current run. If alert already exists it will
        not be duplicated.

        Parameters
        ----------
        name : str
            name of alert
        pattern : str, optional
            for event based alerts pattern to look for, by default None
        frequency : PositiveInt, optional
            frequency at which to check alert condition in seconds, by default None
        notification : Literal['email', 'none'], optional
            whether to notify on trigger
                * email - send email to user on alert.
                * none - send no notifications (default).
        trigger_abort : bool, optional
            whether this alert can trigger a run abort
        attach_to_run : bool, optional
            whether to attach this alert to the current run, default True

        Returns
        -------
        str | None
            returns the created alert ID if successful

        """
        _alert = EventsAlert.new(
            name=name,
            description=description,
            pattern=pattern,
            notification=notification,
            frequency=frequency,
            offline=self._user_config.run.mode == "offline",
        )
        _alert.abort = trigger_abort
        _alert.commit()
        if attach_to_run:
            self.add_alerts(ids=[_alert.id])
        return _alert.id

    @skip_if_failed("_aborted", "_suppress_errors", None)
    @pydantic.validate_call
    def create_user_alert(
        self,
        name: typing.Annotated[str, pydantic.Field(pattern=NAME_REGEX)],
        *,
        description: str | None = None,
        notification: typing.Literal["email", "none"] = "none",
        trigger_abort: bool = False,
        attach_to_run: bool = True,
    ) -> None:
        """Creates a user alert with the specified name (if it doesn't exist)
        and applies it to the current run. If alert already exists it will
        not be duplicated.

        Parameters
        ----------
        name : str
            name of alert
        description : str, optional
            description for this alert, default None
        notification : Literal['email', 'none'], optional
            whether to notify on trigger
                * email - send email to user on notify.
                * none - send no notifications (default).
        trigger_abort : bool, optional
            whether this alert can trigger a run abort, default False
        attach_to_run : bool, optional
            whether to attach this alert to the current run, default True

        Returns
        -------
        str | None
            returns the created alert ID if successful

        """
        _alert = UserAlert.new(
            name=name,
            notification=notification,
            description=description,
            offline=self._user_config.run.mode == "offline",
        )
        _alert.abort = trigger_abort
        _alert.commit()
        if attach_to_run:
            self.add_alerts(ids=[_alert.id])
        return _alert.id

    @skip_if_failed("_aborted", "_suppress_errors", False)
    @check_run_initialised
    @pydantic.validate_call
    def log_alert(
        self,
        identifier: str | None = None,
        name: str | None = None,
        state: typing.Literal["ok", "critical"] = "critical",
    ) -> bool:
        """Set the state of an alert - either specify the alert by ID or name.

        Parameters
        ----------
        identifier : str | None
            ID of alert to update, by default None
        name : str | None
            Name of the alert to update, by default None
        state : Literal['ok', 'critical']
            state to set alert to
                * ok - alert is set to ok state.
                * critical - alert is set to critical state (default).

        Returns
        -------
        bool
            whether alert state update was successful
        """
        if state not in ("ok", "critical"):
            self._error('state must be either "ok" or "critical"')
            return False

        if (identifier and name) or (not identifier and not name):
            self._error("Please specify alert to update either by ID or by name.")
            return False

        if name and self._user_config.run.mode == "offline":
            self._error(
                "Cannot retrieve alerts based on names in offline mode - please use IDs instead."
            )
            return False

        if name:
            try:
                if alerts := Alert.get(offline=self._user_config.run.mode == "offline"):
                    identifier = next(
                        (id for id, alert in alerts if alert.name == name), None
                    )
                else:
                    self._error("No existing alerts")
                    return False
            except RuntimeError as e:
                self._error(f"{e.args[0]}")
                return False

        if not identifier:
            self._error(f"Alert with name '{name}' could not be found.")

        _alert = UserAlert(identifier=identifier)
        if not isinstance(_alert, UserAlert):
            self._error(
                f"Cannot update state for alert '{identifier}' "
                f"of type '{_alert.__class__.__name__.lower()}'"
            )
            return False
        _alert.read_only(False)
        _alert.set_status(run_id=self.id, status=state)
        _alert.commit()

        return True
