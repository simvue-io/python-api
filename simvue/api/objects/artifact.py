"""
Simvue Artifact
===============

Class for defining and interacting with artifact objects.

"""

import typing
import os.path
import pydantic

from simvue.models import NAME_REGEX
from simvue.utilities import get_mimetype_for_file, get_mimetypes, calculate_sha256
from .base import SimvueObject

Category = typing.Literal["code", "input", "output"]

__all__ = ["Artifact"]


class Artifact(SimvueObject):
    """Connect to/create an artifact locally or on the server"""

    @classmethod
    @pydantic.validate_call
    def new(
        cls,
        *,
        name: typing.Annotated[str, pydantic.Field(pattern=NAME_REGEX)],
        run: str,
        storage: str | None,
        category: Category,
        file_path: pydantic.FilePath,
        file_type: str | None,
        offline: bool = False,
    ) -> typing.Self:
        """Create a new artifact either locally or on the server

        Note all arguments are keyword arguments

        Parameters
        ----------
        name : str
            the name for this artifact
        run : str
            the identifier with which this artifact is associated
        storage : str | None
            the identifier for the storage location for this object
        category : "code" | "input" | "output"
            the category of this artifact
        file_path : pathlib.Path | str
            path to the file this artifact represents
        file_type : str | None
            the mime type for this file, else this is determined
        offline : bool, optional
            whether to define this artifact locally, default is False

        """
        _file_type = file_type or get_mimetype_for_file(file_path)

        if _file_type not in get_mimetypes():
            raise ValueError(f"Invalid MIME type '{file_type}' specified")

        _file_size = file_path.stat().st_size
        _file_orig_path = file_path.expanduser().absolute()
        _file_checksum = calculate_sha256(f"{file_path}", is_file=True)

        _artifact = Artifact(
            name=name,
            run=run,
            storage=storage,
            category=category,
            originalPath=os.path.expandvars(_file_orig_path),
            size=_file_size,
            type=_file_type,
            checksum=_file_checksum,
        )
        _artifact.offline_mode(offline)
        return _artifact

    @property
    def name(self) -> str:
        """Retrieve the name for this artifact"""
        return self._get_attribute("name")

    @property
    def checksum(self) -> str:
        """Retrieve the checksum for this artifact"""
        return self._get_attribute("checksum")

    @property
    def category(self) -> Category:
        """Retrieve the category for this artifact"""
        return self._get_attribute("category")

    @property
    def original_path(self) -> str:
        """Retrieve the original path of the file associated with this artifact"""
        return self._get_attribute("originalPath")

    @property
    def storage(self) -> str:
        """Retrieve the storage identifier for this artifact"""
        return self._get_attribute("storage")

    @property
    def type(self) -> str:
        """Retrieve the MIME type for this artifact"""
        return self._get_attribute("type")
