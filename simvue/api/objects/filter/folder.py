"""Simvue RestAPI Folders Filter."""

import typing
import pydantic as pyd

try:
    from typing import Self
except ImportError:
    from typing_extensions import Self  # noqa: UP035

from simvue.models import FOLDER_REGEX
from simvue.utilities import prettify_pydantic
from .base import RestAPIFilter


class FoldersFilter(RestAPIFilter):
    """Filter for Folders."""

    @prettify_pydantic
    @pyd.validate_call
    def has_path(
        self, name: typing.Annotated[str, pyd.Field(pattern=FOLDER_REGEX)]
    ) -> Self:
        """Check if a folder has the given path."""
        self._filters.append(f"path == {name}")
        return self

    @prettify_pydantic
    @pyd.validate_call
    def has_path_containing(self, name: str) -> Self:
        """Check if the folder path contains a search term."""
        self._filters.append(f"path contains {name}")
        return self
