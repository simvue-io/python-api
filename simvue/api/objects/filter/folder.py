"""Simvue RestAPI Folders Filter."""

from .base import RestAPIFilter


class FoldersFilter(RestAPIFilter):
    """Filter for Folders."""

    def has_path(self, name: str) -> "FoldersFilter":
        """Check if a folder has the given path."""
        self._filters.append(f"path == {name}")
        return self

    def has_path_containing(self, name: str) -> "FoldersFilter":
        """Check if the folder path contains a search term."""
        self._filters.append(f"path contains {name}")
        return self

    def _generate_members(self) -> None:
        return super()._generate_members()
