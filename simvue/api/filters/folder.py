"""Defines filters for Folder retrieval."""

import sys

from .base import MetadataFilter, ObjectListProperty, RestAPIFilter, ObjectStrProperty

if sys.version_info < (3, 11):
    from typing_extensions import Self
else:
    from typing import Self


class FoldersFilter(RestAPIFilter):
    """Filter for browsing Folder objects."""

    @property
    def path(self) -> ObjectStrProperty:
        """Return comparator for Folder path."""
        return ObjectStrProperty("path", self)

    @property
    def description(self) -> ObjectStrProperty:
        """Return comparator for Folder description."""
        return ObjectStrProperty("description", self)

    @property
    def tags(self) -> ObjectListProperty:
        """Return comparator for Folder tags."""
        return ObjectListProperty("tags", self, str)

    @property
    def starred(self) -> Self:
        """Return filter for if Folder starred."""
        return self._boolean_flag("starred")

    @property
    def metadata(self) -> MetadataFilter:
        """Return comparator for metadata filtering."""
        return MetadataFilter(self)
