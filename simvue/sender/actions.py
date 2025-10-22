import abc
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
import http
import json
import logging
import pathlib
import threading
import typing

import requests

from simvue.api.objects import (
    Alert,
    Artifact,
    Events,
    EventsAlert,
    FileArtifact,
    FileStorage,
    Folder,
    Grid,
    GridMetrics,
    Metrics,
    MetricsRangeAlert,
    MetricsThresholdAlert,
    ObjectArtifact,
    Run,
    S3Storage,
    Storage,
    Tag,
    Tenant,
    User,
    UserAlert,
)
from simvue.api.objects.alert.fetch import AlertType
from simvue.api.objects.artifact.base import ArtifactBase
from simvue.api.objects.base import SimvueObject
from simvue.api.request import put as sv_put, get_json_from_response
from simvue.models import ObjectID
from simvue.config.user import SimvueConfiguration
from simvue.eco import CO2Monitor

try:
    from typing import override
except ImportError:
    from typing_extensions import override  # noqa: UP035


class UploadAction:
    """Defines the tasks to execute during upload."""

    object_type: str = ""
    logger: logging.Logger = logging.getLogger(__name__)
    singular_object: bool = True

    @classmethod
    def json_file(cls, cache_directory: pathlib.Path, offline_id: str) -> pathlib.Path:
        return cache_directory.joinpath(f"{cls.object_type}", f"{offline_id}.json")

    @classmethod
    def log_upload_failed(
        cls, cache_directory: pathlib.Path, offline_id: str, data: dict[str, typing.Any]
    ) -> None:
        data["upload_failed"] = True
        with cls.json_file(cache_directory, offline_id).open("w") as out_f:
            json.dump(data, out_f, indent=2)

    @classmethod
    def count(cls, cache_directory: pathlib.Path) -> int:
        """Return number of objects to upload of this type."""
        return len(list(cls.uploadable_objects(cache_directory)))

    @classmethod
    def pre_tasks(
        cls, offline_id: str, data: dict[str, typing.Any], cache_directory: pathlib.Path
    ) -> None:
        """Pre-upload actions."""
        _ = offline_id
        _ = data
        _ = cache_directory
        pass

    @classmethod
    def post_tasks(
        cls,
        offline_id: str,
        online_id: ObjectID | None,
        data: dict[str, typing.Any],
        cache_directory: pathlib.Path,
    ) -> None:
        """Post-upload actions."""
        _ = data
        _ = online_id
        cls.json_file(cache_directory, offline_id).unlink(missing_ok=True)

    @classmethod
    @abc.abstractmethod
    def initialise_object(
        cls, online_id: ObjectID | None, **data
    ) -> SimvueObject | None:
        """Initialise an instance."""
        _ = online_id
        _ = data

    @classmethod
    def uploadable_objects(cls, cache_directory: pathlib.Path) -> Generator[str]:
        """Iterate through uploadables."""
        for file in cache_directory.glob(f"{cls.object_type}/*.json"):
            yield file.stem

    @classmethod
    def _single_item_upload(
        cls,
        identifier: str,
        id_mapping: dict[str, str],
        cache_directory: pathlib.Path,
        thread_lock: threading.Lock,
        *,
        throw_exceptions: bool = False,
        retry_failed: bool = False,
    ) -> None:
        _json_file = cache_directory.joinpath(f"{cls.object_type}/{identifier}.json")

        with _json_file.open() as in_f:
            _data = json.load(in_f)

        if _data.pop("upload_failed", False) and not retry_failed:
            return

        try:
            cls.pre_tasks(
                offline_id=identifier, data=_data, cache_directory=cache_directory
            )

            _object = cls.initialise_object(
                online_id=id_mapping.get(identifier), **_data
            )

            if not _object:
                _out_msg: str = f"No initialiser defined for type '{cls.__name__}'"
                raise RuntimeError(_out_msg)

            with thread_lock:
                _object.on_reconnect(id_mapping)

            if not isinstance(_object, ArtifactBase):
                _object.commit()

            _object.read_only(True)

        except Exception as err:
            if throw_exceptions:
                raise err
            cls.logger.exception(
                "Failed to upload %s '%s'", cls.object_type, identifier
            )
            cls.log_upload_failed(cache_directory, identifier, _data)
            return

        if cls.singular_object:
            if not _object.id:
                cls.logger.error(
                    "No identifier retrieved for %s '%s'",
                    cls.object_type,
                    identifier,
                )
                cls.log_upload_failed(cache_directory, identifier, _data)
                return

            cls.logger.info(
                "%s %s '%s'",
                "Updated" if id_mapping.get(identifier) else "Created",
                cls.object_type[:-1]
                if cls.object_type.endswith("s")
                else cls.object_type,
                _object.id,
            )

            with thread_lock:
                id_mapping[identifier] = _object.id
        else:
            cls.logger.info(
                "%s %s",
                "Updated" if id_mapping.get(identifier) else "Created",
                cls.object_type[:-1]
                if cls.object_type.endswith("s")
                else cls.object_type,
            )

        cls.post_tasks(
            offline_id=identifier,
            online_id=_object.id if cls.singular_object else None,
            data=_data,
            cache_directory=cache_directory,
        )

    @classmethod
    def upload(
        cls,
        id_mapping: dict[str, str],
        cache_directory: pathlib.Path,
        thread_lock: threading.Lock,
        single_thread_limit: int,
        max_thread_workers: int,
        *,
        throw_exceptions: bool = False,
        retry_failed: bool = False,
    ) -> None:
        """Run upload of file category."""
        _iterable = cls.uploadable_objects(cache_directory)
        if cls.count(cache_directory) < single_thread_limit:
            for identifier in _iterable:
                cls._single_item_upload(
                    identifier=identifier,
                    cache_directory=cache_directory,
                    thread_lock=thread_lock,
                    throw_exceptions=throw_exceptions,
                    retry_failed=retry_failed,
                    id_mapping=id_mapping,
                )
        else:
            with ThreadPoolExecutor(
                max_workers=max_thread_workers,
                thread_name_prefix="sender_session_upload",
            ) as executor:
                _results = executor.map(
                    lambda identifier: cls._single_item_upload(
                        identifier=identifier,
                        cache_directory=cache_directory,
                        thread_lock=thread_lock,
                        throw_exceptions=throw_exceptions,
                        retry_failed=retry_failed,
                        id_mapping=id_mapping,
                    ),
                    _iterable,
                )
                # This will raise any exceptions encountered during sending
                for result in _results:
                    pass


class ArtifactUploadAction(UploadAction):
    object_type: str = "artifacts"

    @override
    @classmethod
    def pre_tasks(
        cls,
        offline_id: str,
        data: dict[str, typing.Any],
        cache_directory: pathlib.Path,
    ) -> None:
        if data["obj_type"] != "ObjectArtifact":
            return
        with cache_directory.joinpath(cls.object_type, f"{offline_id}.object").open(
            "rb"
        ) as in_f:
            data["serialized"] = in_f.read()

    @override
    @classmethod
    def post_tasks(
        cls,
        offline_id: str,
        online_id: ObjectID | None,
        data: dict[str, typing.Any],
        cache_directory: pathlib.Path,
    ) -> None:
        _ = online_id
        super().post_tasks(
            offline_id=offline_id,
            online_id=online_id,
            data=data,
            cache_directory=cache_directory,
        )
        if data["obj_type"] != "ObjectArtifact":
            return
        cache_directory.joinpath(cls.object_type, f"{offline_id}.object").unlink()

    @override
    @classmethod
    def initialise_object(
        cls, online_id: ObjectID | None, **data
    ) -> FileArtifact | ObjectArtifact:
        if not online_id:
            if data.get("file_path"):
                return FileArtifact.new(**data)

            return ObjectArtifact.new(**data)

        _sv_obj = Artifact(identifier=online_id, _read_only=False, **data)
        return _sv_obj


class RunUploadAction(UploadAction):
    object_type: str = "runs"

    @override
    @classmethod
    def initialise_object(cls, online_id: ObjectID | None, **data) -> Run:
        if not online_id:
            return Run.new(**data)

        return Run(identifier=online_id, _read_only=False, **data)

    @override
    @classmethod
    def post_tasks(
        cls,
        offline_id: str,
        online_id: str,
        data: dict[str, typing.Any],
        cache_directory: pathlib.Path,
    ) -> None:
        super().post_tasks(
            offline_id=offline_id,
            online_id=online_id,
            data=data,
            cache_directory=cache_directory,
        )

        _ = cache_directory.joinpath("server_ids", f"{offline_id}.txt").write_text(
            online_id
        )

        if not cache_directory.joinpath(
            cls.object_type, f"{offline_id}.closed"
        ).exists():
            return

        _alerts_list: list[str] = typing.cast("list[str]", data.get("alerts", []))

        for _id in _alerts_list:
            cache_directory.joinpath("server_ids", f"{_id}.txt").unlink()

        if _folder_id := data.get("folder_id"):
            cache_directory.joinpath("server_ids", f"{_folder_id}.txt").unlink()

        cache_directory.joinpath("server_ids", f"{offline_id}.txt").unlink()
        cache_directory.joinpath(cls.object_type, f"{offline_id}.closed").unlink()
        cls.logger.info("Run '%s' closed - deleting cached copies...", offline_id)


class FolderUploadAction(UploadAction):
    object_type: str = "folders"

    @classmethod
    @override
    def initialise_object(cls, online_id: ObjectID | None, **data) -> Folder:
        if not online_id:
            return Folder.new(**data)

        return Folder(identifier=online_id, _read_only=False, **data)

    @classmethod
    @override
    def post_tasks(
        cls,
        offline_id: str,
        online_id: str,
        data: dict[str, typing.Any],
        cache_directory: pathlib.Path,
    ) -> None:
        super().post_tasks(
            offline_id=offline_id,
            online_id=online_id,
            data=data,
            cache_directory=cache_directory,
        )

        _ = cache_directory.joinpath("server_ids", f"{offline_id}.txt").write_text(
            online_id
        )


class TenantUploadAction(UploadAction):
    object_type: str = "tenants"

    @classmethod
    @override
    def initialise_object(cls, online_id: ObjectID | None, **data) -> Tenant:
        if not online_id:
            return Tenant.new(**data)

        return Tenant(identifier=online_id, _read_only=False, **data)


class UserUploadAction(UploadAction):
    object_type: str = "users"

    @classmethod
    @override
    def initialise_object(cls, online_id: ObjectID | None, **data) -> User:
        if not online_id:
            return User.new(**data)

        return User(identifier=online_id, _read_only=False, **data)


class TagUploadAction(UploadAction):
    object_type: str = "tags"

    @classmethod
    @override
    def initialise_object(cls, online_id: ObjectID | None, **data) -> Tag:
        if not online_id:
            return Tag.new(**data)

        return Tag(identifier=online_id, _read_only=False, **data)

    @classmethod
    @override
    def post_tasks(
        cls,
        offline_id: str,
        online_id: str,
        data: dict[str, typing.Any],
        cache_directory: pathlib.Path,
    ) -> None:
        super().post_tasks(offline_id, online_id, data, cache_directory)
        _ = cache_directory.joinpath("server_ids", f"{offline_id}.txt").write_text(
            online_id
        )


class AlertUploadAction(UploadAction):
    object_type: str = "alerts"

    @classmethod
    @override
    def initialise_object(cls, online_id: ObjectID | None, **data) -> AlertType:
        if not online_id:
            _source: str = data["source"]

            if _source == "events":
                return EventsAlert.new(**data)
            elif _source == "metrics" and data.get("threshold"):
                return MetricsThresholdAlert.new(**data)
            elif _source == "metrics":
                return MetricsRangeAlert.new(**data)
            else:
                return UserAlert.new(**data)

        return Alert(identifier=online_id, _read_only=False, **data)

    @classmethod
    @override
    def post_tasks(
        cls,
        offline_id: str,
        online_id: str,
        data: dict[str, typing.Any],
        cache_directory: pathlib.Path,
    ) -> None:
        super().post_tasks(offline_id, online_id, data, cache_directory)
        _ = cache_directory.joinpath("server_ids", f"{offline_id}.txt").write_text(
            online_id
        )


class StorageUploadAction(UploadAction):
    object_type: str = "storage"

    @classmethod
    @override
    def initialise_object(
        cls, online_id: ObjectID | None, **data
    ) -> S3Storage | FileStorage:
        if not online_id:
            if data.get("config", {}).get("endpoint_url"):
                return S3Storage.new(**data)

            return FileStorage.new(**data)

        return Storage(identifier=online_id, _read_only=False, **data)


class GridUploadAction(UploadAction):
    object_type: str = "grids"

    @classmethod
    @override
    def initialise_object(cls, online_id: ObjectID | None, **data) -> Grid:
        if not online_id:
            return Grid.new(**data)

        return Grid(identifier=online_id, _read_only=False, **data)


class MetricsUploadAction(UploadAction):
    object_type: str = "metrics"
    singular_object: bool = False

    @classmethod
    @override
    def initialise_object(cls, online_id: ObjectID | None, **data) -> Metrics:
        _ = online_id
        return Metrics.new(**data)


class GridMetricsUploadAction(UploadAction):
    object_type: str = "grid_metrics"
    singular_object: bool = False

    @classmethod
    @override
    def initialise_object(cls, online_id: ObjectID | None, **data) -> GridMetrics:
        _ = online_id
        return GridMetrics.new(**data)


class EventsUploadAction(UploadAction):
    object_type: str = "events"
    singular_object: bool = False

    @classmethod
    @override
    def initialise_object(cls, online_id: ObjectID | None, **data) -> Events:
        _ = online_id
        return Events.new(**data)


class HeartbeatUploadAction(UploadAction):
    object_type: str = "heartbeat"
    singular_object: bool = True

    @override
    @classmethod
    def initialise_object(cls, online_id: ObjectID | None, **data) -> None:
        _ = online_id
        _ = data

    @override
    @classmethod
    def pre_tasks(
        cls, offline_id: str, data: dict[str, typing.Any], cache_directory: pathlib.Path
    ) -> None:
        _ = offline_id
        _ = data
        _ = cache_directory
        pass

    @override
    @classmethod
    def uploadable_objects(cls, cache_directory: pathlib.Path) -> Generator[str]:
        """Iterate through uploadables."""
        for file in cache_directory.glob("runs/*.heartbeat"):
            yield file.stem

    @override
    @classmethod
    def _single_item_upload(
        cls,
        identifier: str,
        id_mapping: dict[str, str],
        cache_directory: pathlib.Path,
        thread_lock: threading.Lock,
        *,
        throw_exceptions: bool = False,
        retry_failed: bool = False,
    ) -> None:
        if not (_online_id := id_mapping.get(identifier)):
            # Run has been closed - can just remove heartbeat and continue
            cache_directory.joinpath(f"runs/{identifier}.heartbeat").unlink()
            return

        _local_config: SimvueConfiguration = SimvueConfiguration.fetch()

        cls.logger.info("Sending heartbeat to run '%s'", identifier)

        _response: requests.Response = sv_put(
            url=f"{_local_config.server.url}/runs/{_online_id}/heartbeat",
            headers=_local_config.headers,
        )

        try:
            _json_response = get_json_from_response(
                expected_status=[http.HTTPStatus.OK],
                scenario=f"Attempt to send heartbeat to run {_online_id}",
                response=_response,
            )
        except RuntimeError as e:
            if throw_exceptions:
                raise e
            cls.logger.exception(e)

    @override
    @classmethod
    def post_tasks(
        cls,
        offline_id: str,
        online_id: ObjectID | None,
        data: dict[str, typing.Any],
        cache_directory: pathlib.Path,
    ) -> None:
        pass


class CO2IntensityUploadAction(UploadAction):
    object_type: str = "co2_intensity"

    @override
    @classmethod
    def initialise_object(cls, online_id: ObjectID | None, **data) -> None:
        _ = online_id
        _ = data

    @override
    @classmethod
    def pre_tasks(
        cls, offline_id: str, data: dict[str, typing.Any], cache_directory: pathlib.Path
    ) -> None:
        _ = offline_id
        _ = data
        _ = cache_directory

    @override
    @classmethod
    def post_tasks(
        cls,
        offline_id: str,
        online_id: ObjectID | None,
        data: dict[str, typing.Any],
        cache_directory: pathlib.Path,
    ) -> None:
        _ = offline_id
        _ = data
        _ = cache_directory

    @override
    @classmethod
    def uploadable_objects(cls, cache_directory: pathlib.Path) -> Generator[str]:
        yield from ()

    @override
    @classmethod
    def _single_item_upload(
        cls,
        identifier: str,
        id_mapping: dict[str, str],
        cache_directory: pathlib.Path,
        thread_lock: threading.Lock,
        *,
        throw_exceptions: bool = False,
        retry_failed: bool = False,
    ) -> None:
        _ = identifier
        _ = id_mapping
        _ = cache_directory
        _ = thread_lock

    @override
    @classmethod
    def upload(
        cls,
        id_mapping: dict[str, str],
        cache_directory: pathlib.Path,
        thread_lock: threading.Lock,
        single_thread_limit: int,
        max_thread_workers: int,
        *,
        throw_exceptions: bool = False,
        retry_failed: bool = False,
    ) -> None:
        _ = id_mapping
        _ = thread_lock
        _ = single_thread_limit
        _ = max_thread_workers

        _local_config: SimvueConfiguration = SimvueConfiguration.fetch()

        if not _local_config.metrics.enable_emission_metrics:
            return

        try:
            CO2Monitor(
                thermal_design_power_per_gpu=None,
                thermal_design_power_per_cpu=None,
                local_data_directory=cache_directory,
                intensity_refresh_interval=_local_config.eco.intensity_refresh_interval,
                co2_intensity=_local_config.eco.co2_intensity,
                co2_signal_api_token=_local_config.eco.co2_signal_api_token,
            ).check_refresh()
        except (ValueError, RuntimeError) as e:
            if throw_exceptions:
                raise e
            cls.logger.exception(e)


UPLOAD_ACTION_ORDER: tuple[type[UploadAction], ...] = (
    TenantUploadAction,
    UserUploadAction,
    StorageUploadAction,
    FolderUploadAction,
    TagUploadAction,
    AlertUploadAction,
    RunUploadAction,
    GridUploadAction,
    ArtifactUploadAction,
    MetricsUploadAction,
    GridMetricsUploadAction,
    EventsUploadAction,
    HeartbeatUploadAction,
    CO2IntensityUploadAction,
)
