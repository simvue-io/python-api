"""Classes and methods for sending local objects to server.

These are designed to be run with a cron task in cases where server connection
is either not possible on the simulation machine, or connection is limited.
"""

import logging
import threading
import typing
import pydantic
import psutil

from simvue.sender.actions import UPLOAD_ACTION_ORDER
from simvue.config.user import SimvueConfiguration

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
    ) -> None:
        """Creates required local directories."""
        _local_config: SimvueConfiguration = SimvueConfiguration.fetch()
        self._cache_directory = cache_directory or _local_config.offline.cache
        self._cache_directory.joinpath("server_ids").mkdir(parents=True, exist_ok=True)
        self._throw_exceptions = throw_exceptions
        self._threading_threshold = threading_threshold
        self._retry_failed_uploads = retry_failed_uploads
        self._max_workers = max_workers
        self._lock_path = self._cache_directory.joinpath("sender.lock")
        self._thread_lock = threading.Lock()
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

    @pydantic.validate_call
    def upload(self, objects_to_upload: list[UploadItem] | None = None) -> None:
        """Upload objects to server."""
        self._lock()

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
                single_thread_limit=self._threading_threshold,
                max_thread_workers=self._max_workers,
            )
        self._release()
