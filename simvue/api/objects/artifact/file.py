from .base import ArtifactBase

import typing
import pydantic
import os
import pathlib
from simvue.models import NAME_REGEX
from simvue.utilities import get_mimetype_for_file, get_mimetypes, calculate_sha256

try:
    from typing import Self
except ImportError:
    from typing_extensions import Self


class FileArtifact(ArtifactBase):
    """File based artifact modification and creation class."""

    def __init__(
        self, identifier: str | None = None, _read_only: bool = True, **kwargs
    ) -> None:
        """Initialise a new file artifact connection.

        Parameters
        ----------
        identifier : str, optional
            the identifier of this object on the server.
        """
        super().__init__(identifier=identifier, _read_only=_read_only, **kwargs)

    @classmethod
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
        **kwargs,
    ) -> Self:
        """Create a new artifact either locally or on the server

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

        """
        _mime_type = mime_type or get_mimetype_for_file(file_path)

        if _mime_type not in get_mimetypes():
            raise ValueError(f"Invalid MIME type '{mime_type}' specified")

        if _file_orig_path := kwargs.pop("original_path", None):
            _file_size = kwargs.pop("size")
            _file_checksum = kwargs.pop("checksum")
        else:
            file_path = pathlib.Path(file_path)
            _file_size = file_path.stat().st_size
            _file_orig_path = file_path.expanduser().absolute()
            _file_checksum = calculate_sha256(f"{file_path}", is_file=True)

        _artifact = FileArtifact(
            name=name,
            storage=storage,
            original_path=os.path.expandvars(_file_orig_path),
            size=_file_size,
            mime_type=_mime_type,
            checksum=_file_checksum,
            _offline=offline,
            _read_only=False,
            metadata=metadata,
            **kwargs,
        )
        _artifact._staging["file_path"] = str(file_path)
        if offline:
            _artifact._init_data = {}

        else:
            _artifact._init_data = _artifact._post(**_artifact._staging)
            _artifact._staging["url"] = _artifact._init_data["url"]

        _artifact._init_data["runs"] = kwargs.get("runs") or {}

        if offline:
            return _artifact

        with open(_file_orig_path, "rb") as out_f:
            _artifact._upload(file=out_f, timeout=upload_timeout, file_size=_file_size)

        return _artifact
