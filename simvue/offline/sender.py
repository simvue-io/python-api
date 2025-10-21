"""Classes and methods for sending local objects to server.

These are designed to be run with a cron task in cases where server connection
is either not possible on the simulation machine, or connection is limited.
"""

from collections.abc import Iterable
import logging
import threading
import typing
import pydantic
import pathlib
import psutil

from simvue.offline.actions import UPLOAD_ORDER
from simvue.config.user import SimvueConfiguration

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


class Sender(pydantic.BaseModel):
    cache_directory: pydantic.DirectoryPath
    server_url: str
    server_token: pydantic.SecretStr
    max_workers: pydantic.PositiveInt = 5
    threading_threshold: pydantic.PositiveInt = 10
    throw_exceptions: bool = False
    retry_failed_uploads: bool = False
    _lock_path: pathlib.Path
    _id_mapping: dict[str, str]
    _thread_lock: threading.Lock = pydantic.PrivateAttr(threading.Lock())
    _logger: logging.Logger
    _run_failed: bool = pydantic.PrivateAttr(False)

    model_config: typing.ClassVar[pydantic.ConfigDict] = pydantic.ConfigDict(
        frozen=True, extra="forbid"
    )

    @pydantic.model_validator(mode="before")
    @classmethod
    def set_credentials(cls, values: dict[str, object]) -> dict[str, object]:
        """Set URL and token if unspecified."""
        _local_config: SimvueConfiguration = SimvueConfiguration.fetch(
            server_url=values.get("server_url"),
            server_token=values.get("server_token"),
        )
        values["server_url"] = _local_config.server.url
        values["server_token"] = _local_config.server.token
        values["cache_directory"] = values.get(
            "cache_directory", _local_config.offline.cache
        )

        return values

    def __post_init__(self) -> None:
        """Creates required local directories."""
        self.cache_directory.joinpath("server_ids").mkdir(parents=True, exist_ok=True)
        self._lock_path = self.cache_directory.joinpath("sender.lock")
        self._id_mapping = {
            file_path.name.split(".")[0]: file_path.read_text()
            for file_path in self.cache_directory.glob("server_ids/*.txt")
        }
        self._logger = logging.getLogger(__name__)

    @property
    def locked(self) -> bool:
        """Check if dispatch locked by another sender."""
        if not self._lock_path:
            raise RuntimeError("Expected lock file path, but none initialised.")
        return self._lock_path.exists() and psutil.pid_exists(
            int(self._lock_path.read_text())
        )

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
        self._logger.error(message)

        self._run_failed = True

    def _lock(self) -> None:
        """Lock to this sender."""
        if self.locked:
            raise RuntimeError("A sender is already running for this cache!")
        _ = self._lock_path.write_text(f"{psutil.Process().pid}")

    def _release(self) -> None:
        """Release lock to this sender."""
        self._lock_path.unlink()

    @pydantic.validate_call(config={"validate_default": True})
    def upload(self, objects_to_upload: Iterable[UploadItem] | None = None) -> None:
        """Upload objects to server."""
        for action in UPLOAD_ORDER:
            if objects_to_upload and action.object_type not in list(objects_to_upload):
                continue

            _n_objects: int = action.count(self.cache_directory)

            action.upload(
                cache_directory=self.cache_directory,
                id_mapping=self._id_mapping,
                thread_lock=self._thread_lock,
                throw_exceptions=self.throw_exceptions,
                retry_failed=self.retry_failed_uploads,
                single_thread_limit=self.threading_threshold,
                max_thread_workers=self.max_workers,
            )
