import abc
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
import json
import logging
import pathlib
import threading
import typing

from simvue.api.objects import (
    Alert,
    Artifact,
    EventsAlert,
    FileArtifact,
    FileStorage,
    Grid,
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

try:
    from typing import override
except ImportError:
    from typing_extensions import override  # noqa: UP035


class UploadAction:
    """Defines the tasks to execute during upload."""

    object_type: str = ""
    logger: logging.Logger = logging.getLogger(__name__)

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
        online_id: str,
        data: dict[str, typing.Any],
        cache_directory: pathlib.Path,
    ) -> None:
        """Post-upload actions."""
        _ = data
        _ = online_id
        cls.json_file(cache_directory, offline_id).unlink(missing_ok=True)

    @abc.abstractmethod
    @classmethod
    def initialise_object(cls, identifier: str, **data) -> SimvueObject:
        """Initialise an instance."""
        pass

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

            _object = cls.initialise_object(identifier=identifier, **_data)

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
            cls.object_type[:-1] if cls.object_type.endswith("s") else cls.object_type,
            _object.id,
        )

        with thread_lock:
            id_mapping[identifier] = _object.id

        cls.post_tasks(
            offline_id=identifier,
            online_id=_object.id,
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
    def post_tasks(
        cls,
        offline_id: str,
        online_id: str,
        data: dict[str, typing.Any],
        cache_directory: pathlib.Path,
    ) -> None:
        _ = online_id
        if not data.get("obj"):
            return
        cache_directory.joinpath(cls.object_type, f"{offline_id}.object").unlink()

    @override
    @classmethod
    def initialise_object(
        cls, identifier: str | None, **data
    ) -> FileArtifact | ObjectArtifact:
        if not identifier:
            if data.get("file_path"):
                return FileArtifact.new(**data)

            return ObjectArtifact.new(**data)

        _sv_obj = Artifact(identifier=identifier)
        _sv_obj.read_only(False)
        return _sv_obj


class RunUploadAction(UploadAction):
    object_type: str = "runs"

    @override
    @classmethod
    def initialise_object(cls, identifier: str | None, **data) -> Run:
        if not identifier:
            return Run.new(**data)

        _sv_obj = Run(identifier=identifier)
        _sv_obj.read_only(False)
        return _sv_obj

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
    def initialise_object(cls, identifier: str, **data) -> Tenant:
        if not identifier:
            return Tenant.new(**data)

        _sv_obj = Tenant(identifier=identifier)
        _sv_obj.read_only(False)
        return _sv_obj


class UserUploadAction(UploadAction):
    object_type: str = "users"

    @classmethod
    @override
    def initialise_object(cls, identifier: str, **data) -> User:
        if not identifier:
            return User.new(**data)

        _sv_obj = User(identifier=identifier)
        _sv_obj.read_only(False)
        return _sv_obj


class TagUploadAction(UploadAction):
    object_type: str = "tags"

    @classmethod
    @override
    def initialise_object(cls, identifier: str, **data) -> Tag:
        if not identifier:
            return Tag.new(**data)

        _sv_obj = Tag(identifier=identifier)
        _sv_obj.read_only(False)
        return _sv_obj

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
    def initialise_object(cls, identifier: str, **data) -> AlertType:
        if not identifier:
            _source: str = data["source"]

            if _source == "events":
                return EventsAlert.new(**data)
            elif _source == "metrics" and data.get("threshold"):
                return MetricsThresholdAlert.new(**data)
            elif _source == "metrics":
                return MetricsRangeAlert.new(**data)
            else:
                return UserAlert.new(**data)

        _sv_obj = Alert(identifier=identifier)
        _sv_obj.read_only(False)
        return _sv_obj

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
    def initialise_object(cls, identifier: str, **data) -> S3Storage | FileStorage:
        if not identifier:
            if data.get("config", {}).get("endpoint_url"):
                return S3Storage.new(**data)

            return FileStorage.new(**data)

        _sv_obj = Storage(identifier=identifier)
        _sv_obj.read_only(False)
        return _sv_obj


class GridUploadAction(UploadAction):
    object_type: str = "grids"

    @classmethod
    @override
    def initialise_object(cls, identifier: str, **data) -> Grid:
        if not identifier:
            return Grid.new(**data)

        _sv_obj = Grid(identifier=identifier)
        _sv_obj.read_only(False)
        return _sv_obj


UPLOAD_ORDER: tuple[type[UploadAction], ...] = (
    TenantUploadAction,
    UserUploadAction,
    StorageUploadAction,
    FolderUploadAction,
    TagUploadAction,
    AlertUploadAction,
    RunUploadAction,
    GridUploadAction,
    ArtifactUploadAction,
)
