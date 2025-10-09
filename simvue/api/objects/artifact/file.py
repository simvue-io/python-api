"""File type artifact handling."""

import datetime
import os
import pathlib
import shutil
import typing

import pydantic

from simvue.config.user import SimvueConfiguration
from simvue.models import NAME_REGEX
from simvue.utilities import calculate_sha256, get_mimetype_for_file, get_mimetypes

from .base import ArtifactBase

try:
    from typing import Self
except ImportError:
    from typing_extensions import Self  # noqa: UP035

try:
    from typing import override
except ImportError:
    from typing_extensions import override  # noqa: UP035


try:
    tz_utc = datetime.UTC
except AttributeError:
    tz_utc = datetime.timezone.utc  # noqa: UP017


class FileArtifact(ArtifactBase):
    """File based artifact modification and creation class."""

    def __init__(
        self,
        identifier: str | None = None,
        *,
        _read_only: bool = True,
        **kwargs: object,
    ) -> None:
        """Initialise a new file artifact connection.

        Parameters
        ----------
        identifier : str, optional
            the identifier of this object on the server.
        """
        super().__init__(identifier=identifier, _read_only=_read_only, **kwargs)

    @classmethod
    @override
    def new(
        cls,
        *,
        name: typing.Annotated[str, pydantic.Field(pattern=NAME_REGEX)],
        storage: str | None,
        file_path: pydantic.FilePath,
        mime_type: str | None,
        metadata: dict[str, typing.Any] | None,
        upload_timeout: int | None = None,
        offline: bool = False,
        snapshot: bool = False,
        **kwargs: object,
    ) -> Self:
        """Create a new artifact either locally or on the server.

        Note all arguments are keyword arguments

        Parameters
        ----------
        name : str
            the name for this artifact
        storage : str | None
            the identifier for the storage location for this object
        file_path : pathlib.Path | str
            path to the file this artifact represents
        mime_type : str | None
            the mime type for this file, else this is determined
        metadata : dict[str, Any] | None
            supply metadata information for this artifact
        upload_timeout : int | None, optional
            specify the timeout in seconds for upload
        offline : bool, optional
            whether to define this artifact locally, default is False
        snapshot : bool, optional
            whether to create a snapshot of this file before uploading it,
            default is False

        """
        _mime_type = mime_type or get_mimetype_for_file(file_path)

        if _mime_type not in get_mimetypes():
            _out_msg: str = f"Invalid MIME type '{mime_type}' specified"
            raise ValueError(_out_msg)

        _file_orig_path = typing.cast("str | None", kwargs.pop("original_path", None))
        if _file_orig_path:
            _file_size = typing.cast("int", kwargs.pop("size"))
            _file_checksum = typing.cast("str", kwargs.pop("checksum"))
        else:
            file_path = pathlib.Path(file_path)
            if snapshot:
                _user_config = SimvueConfiguration.fetch()

                _local_staging_dir: pathlib.Path = _user_config.offline.cache.joinpath(
                    "artifacts"
                )
                _local_staging_dir.mkdir(parents=True, exist_ok=True)  # pyright: ignore[reportUnusedCallResult]
                _time_stamp: str = datetime.datetime.now(tz=datetime.UTC).strftime(
                    "%Y-%m-%d_%H-%M-%S_%f"
                )
                _local_staging_file = _local_staging_dir.joinpath(
                    f"{file_path.stem}_{_time_stamp[:-3]}.file"
                )
                _local_staging_file = typing.cast("pathlib.Path", _local_staging_file)
                _ = shutil.copy(file_path, _local_staging_file)
                file_path = _local_staging_file

            _file_size = file_path.stat().st_size
            _file_orig_path = file_path.expanduser().absolute()
            _file_checksum = calculate_sha256(f"{file_path}", is_file=True)

        _artifact = cls(
            name=name,
            storage=storage,
            original_path=os.path.expandvars(_file_orig_path),
            size=_file_size,
            mime_type=_mime_type,
            checksum=_file_checksum,
            _offline=offline,
            _read_only=False,
            metadata=metadata,
            **kwargs,  # pyright: ignore[reportArgumentType]
        )
        _artifact._staging["file_path"] = str(file_path)
        if offline:
            _artifact._init_data = {}

        else:
            _artifact._init_data = typing.cast(
                "dict[str, dict[str, object]]",
                _artifact._post_single(**_artifact._staging),
            )
            _artifact._staging["url"] = _artifact._init_data["url"]

        _artifact._init_data["runs"] = typing.cast(
            "dict[str, object]", kwargs.get("runs", {})
        )

        if offline:
            return _artifact

        with pathlib.Path(_file_orig_path).open("rb") as out_f:
            _artifact._upload(file=out_f, timeout=upload_timeout, file_size=_file_size)

        # If snapshot created, delete it after uploading
        if pathlib.Path(_file_orig_path).parent == _artifact._local_staging_file.parent:
            pathlib.Path(_file_orig_path).unlink()

        return _artifact
