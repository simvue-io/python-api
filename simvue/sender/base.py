"""Classes and methods for sending local objects to server.

These are designed to be run with a cron task in cases where server connection
is either not possible on the simulation machine, or connection is limited.
"""

import datetime
import logging
import threading
import typing
import pydantic
import psutil

from simvue.sender.actions import UPLOAD_ACTION_ORDER
from simvue.config.user import SimvueConfiguration
from simvue.run import Run

logger = logging.getLogger(__name__)

UploadItem = typing.Literal[
    "tenants",
    "users",
    "storage",
    "folders",
    "tags",
    "alerts",
    "runs",
    "grids",
    "artifacts",
    "metrics",
    "grid_metrics",
    "events",
    "heartbeat",
    "co2_intensity",
]

UPLOAD_ORDER: list[str] = [action.object_type for action in UPLOAD_ACTION_ORDER]


class Sender:
    @pydantic.validate_call
    def __init__(
        self,
        cache_directory: pydantic.DirectoryPath | None = None,
        max_workers: pydantic.PositiveInt = 5,
        threading_threshold: pydantic.PositiveInt = 10,
        throw_exceptions: bool = False,
        retry_failed_uploads: bool = False,
        run_notification: typing.Literal["none", "all", "email"] = "none",
        run_retention_period: str | None = None,
        monitor_uploads: bool = False,
    ) -> None:
        """Initialise a local data sender.

        Parameters
        ----------
        cache_directory : pydantic.DirectoryPath | None, optional
            The directory where cached files are stored, else use default.
        max_workers : int, optional
            The maximum number of threads to use, default 5.
        threading_threshold : int, optional
            The number of cached files above which threading will be used, default 10.
        throw_exceptions : bool, optional
            Whether to throw exceptions as they are encountered in the sender,
            default is False (exceptions will be logged)
        retry_failed_uploads : bool, optional
            Whether to retry sending objects which previously failed, by default False
        monitor_uploads : bool, optional
            Whether to track uploads as a Simvue run, by default False
        """
        _local_config: SimvueConfiguration = SimvueConfiguration.fetch(mode="online")
        self._cache_directory = cache_directory or _local_config.offline.cache
        self._cache_directory.joinpath("server_ids").mkdir(parents=True, exist_ok=True)
        self._throw_exceptions = throw_exceptions
        self._threading_threshold = threading_threshold
        self._retry_failed_uploads = retry_failed_uploads
        self._max_workers = max_workers
        self._lock_path = self._cache_directory.joinpath("sender.lock")
        self._thread_lock = threading.Lock()
        self._run_notification: typing.Literal["none", "email"] = run_notification
        self._run_retention_period: str | None = run_retention_period
        self._upload_status: dict[str, str | float] = {}
        self._monitor_uploads: bool = monitor_uploads
        self._id_mapping = {
            file_path.name.split(".")[0]: file_path.read_text()
            for file_path in self._cache_directory.glob("server_ids/*.txt")
        }

    @property
    def locked(self) -> bool:
        """Check if dispatch locked by another sender."""
        if not self._lock_path:
            raise RuntimeError("Expected lock file path, but none initialised.")
        return self._lock_path.exists() and psutil.pid_exists(
            int(self._lock_path.read_text())
        )

    @property
    def id_mapping(self) -> dict[str, str]:
        """Get the ID mapping from offline to online ID."""
        return self._id_mapping

    def _lock(self) -> None:
        """Lock to this sender."""
        if self.locked:
            raise RuntimeError("A sender is already running for this cache!")
        _ = self._lock_path.write_text(f"{psutil.Process().pid}")

    def _release(self) -> None:
        """Release lock to this sender."""
        self._lock_path.unlink()

    def _initialise_monitor_run(self) -> Run:
        """Create a Simvue run for monitoring upload."""
        _time_stamp: str = datetime.datetime.now(tz=datetime.UTC).strftime(
            "%Y_%m_%d_%H_%M_%S"
        )
        _run = Run(mode="online")
        _ = _run.init(
            name=f"sender_upload_{_time_stamp}",
            folder="/sender",
            notification=self._run_notification,
            description="Simvue sender upload session.",
            retention_period=self._run_retention_period,
            timeout=None,
            metadata={
                f"sender.item_count.{upload_object.object_type}": _obj_count
                for upload_object in UPLOAD_ACTION_ORDER
                if (_obj_count := upload_object.count(self._cache_directory)) > 0
            },
            no_color=True,
        )
        _ = _run.config(suppress_errors=True, enable_emission_metrics=False)
        _run.create_user_alert(
            name="sender_object_upload_failure",
            description="Triggers when an object fails to send to the server.",
            notification=self._run_notification,
            trigger_abort=False,
        )

        _run.upload_count = 0

        return _run

    @pydantic.validate_call
    def upload(self, objects_to_upload: list[UploadItem] | None = None) -> None:
        """Upload objects to server.

        Parameters
        ----------
        objects_to_upload : list[str]
            Types of objects to upload, by default uploads all types of objects present in cache
        """
        self._lock()

        _monitor_run = self._initialise_monitor_run() if self._monitor_uploads else None

        self._upload_status = {}

        for action in UPLOAD_ACTION_ORDER:
            if objects_to_upload and action.object_type not in objects_to_upload:
                continue

            logger.info("Uploading %s", action.object_type)

            _n_objects: int = action.count(self._cache_directory)

            action.upload(
                cache_directory=self._cache_directory,
                id_mapping=self._id_mapping,
                thread_lock=self._thread_lock,
                throw_exceptions=self._throw_exceptions,
                retry_failed=self._retry_failed_uploads,
                threading_threshold=self._threading_threshold,
                max_thread_workers=self._max_workers,
                simvue_monitor_run=_monitor_run,
                upload_status=self._upload_status,
            )
        if _monitor_run:
            _monitor_run.close()
        self._release()
