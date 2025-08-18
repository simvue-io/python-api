"""Defines filters specific to Run retrieval."""

import sys
import pydantic

if sys.version_info < (3, 11):
    from typing_extensions import Self
else:
    from typing import Self

from .base import (
    AggregateFilter,
    ObjectListProperty,
    RestAPIFilter,
    ObjectStrProperty,
    PropertyComposite,
    MetadataFilter,
    TemporalFilter,
)


class MetricsFilter(PropertyComposite):
    """Class defining a filter for metrics."""

    def __init__(self, filter: "RestAPIFilter") -> None:
        """Initialise a new metrics filter.

        Parameters
        ----------
        filter: RestAPIFilter
            the parent filter object.

        """
        super().__init__("metrics", filter)

    def __getattr__(self, name: str) -> object:
        return AggregateFilter(f"{self._name}.{name}", self._parent_filter)

    def __call__(self, name: str) -> object:
        return AggregateFilter(f"{self._name}.{name}", self._parent_filter)


class RunFolderFilter(PropertyComposite):
    """Class defining a filter for run folders."""

    def __init__(self, filter: "RestAPIFilter") -> None:
        """Initialise a new run folder filter.

        Parameters
        ----------
        filter: RestAPIFilter
            the parent filter object.

        """
        super().__init__("folder", filter)

    @property
    def path(self) -> ObjectStrProperty:
        """Append filter based on run folder path."""
        return ObjectStrProperty(f"{self._name}.path", self._parent_filter)


class CPUFilter(PropertyComposite):
    """Class defining filter based on CPU properties."""

    def __init__(
        self, filter: "RestAPIFilter", parent: PropertyComposite | None = None
    ) -> None:
        """Initialise a new run system CPU metric filter.

        Parameters
        ----------
        filter: RestAPIFilter
            the parent filter object.
        parent: PropertyComposite | None, optional
            the parent composite if applicable. Default None.

        """
        super().__init__("cpu", filter, parent=parent)

    @property
    def architecture(self) -> ObjectStrProperty:
        """Append filter based on CPU architecture."""
        return ObjectStrProperty(f"{self._name}.arch", self._parent_filter)

    @property
    def processor(self) -> ObjectStrProperty:
        """Append filter based on CPU processor."""
        return ObjectStrProperty(f"{self._name}.processor", self._parent_filter)


class GPUFilter(PropertyComposite):
    """Class defining filter based on GPU properties."""

    def __init__(
        self, filter: "RestAPIFilter", parent: PropertyComposite | None = None
    ) -> None:
        """Initialise a new run system GPU metric filter.

        Parameters
        ----------
        filter: RestAPIFilter
            the parent filter object.
        parent: PropertyComposite | None, optional
            the parent composite if applicable. Default None.

        """
        super().__init__("gpu", filter, parent=parent)

    @property
    def driver(self) -> ObjectStrProperty:
        """Append filter based on GPU driver."""
        return ObjectStrProperty(f"{self._name}.driver", self._parent_filter)

    @property
    def name(self) -> ObjectStrProperty:
        """Append filter based on GPU name."""
        return ObjectStrProperty(f"{self._name}.name", self._parent_filter)


class SystemFilter(PropertyComposite):
    """Class defining filter based on System properties."""

    def __init__(
        self, filter: "RestAPIFilter", parent: PropertyComposite | None = None
    ) -> None:
        """Initialise a new run system GPU metric filter.

        Parameters
        ----------
        filter: RestAPIFilter
            the parent filter object.
        parent: PropertyComposite | None, optional
            the parent composite if applicable. Default None.

        """
        super().__init__("system", filter, parent=parent)

    @property
    def current_working_directory(self) -> ObjectStrProperty:
        """Append filter based on project working directory."""
        return ObjectStrProperty(f"{self._name}.cwd", self._parent_filter)

    @property
    def hostname(self) -> ObjectStrProperty:
        """Append filter based on host name of system."""
        return ObjectStrProperty(f"{self._name}.hostname", self._parent_filter)

    @property
    def python_version(self) -> ObjectStrProperty:
        """Append filter based on Python version."""
        return ObjectStrProperty(f"{self._name}.pythonversion", self._parent_filter)

    @property
    def platform(self) -> ObjectStrProperty:
        """Append filter based on system platform."""
        return ObjectStrProperty(f"{self._name}.platform", self._parent_filter)

    @property
    def cpu(self) -> CPUFilter:
        """Append filter based on CPU properties."""
        return CPUFilter(self._parent_filter, parent=self)

    @property
    def gpu(self) -> ObjectStrProperty:
        """Append filter based on GPU properties."""
        return GPUFilter(self._parent_filter, parent=self)


class ObjectURLProperty(ObjectStrProperty):
    """Class for filtering URL properties."""

    @pydantic.validate_call
    def equals(self, value: pydantic.HttpUrl) -> "RestAPIFilter":
        """Append filter based on URL equivalence."""
        return super().equals(value)

    @pydantic.validate_call
    def not_equals(self, value: pydantic.HttpUrl) -> "RestAPIFilter":
        """Append filter based on URL non-equivalence."""
        return super().not_equals(value)


class RunsFilter(TemporalFilter):
    """Filter for browsing Run objects."""

    @property
    def name(self) -> ObjectStrProperty:
        """Return comparator for run name."""
        return ObjectStrProperty(name="name", filter=self)

    @property
    def author(self) -> ObjectStrProperty:
        """Return comparator for run author."""
        return ObjectStrProperty(name="author", filter=self)

    @property
    def description(self) -> ObjectStrProperty:
        """Return comparator for run description."""
        return ObjectStrProperty(name="description", filter=self)

    @property
    def folder(self) -> PropertyComposite:
        """Return comparator for run folder."""
        return RunFolderFilter(self)

    @property
    def tags(self) -> ObjectListProperty:
        """Return comparator for run tags."""
        return ObjectListProperty(name="tags", filter=self, member_property_type=str)

    @property
    def metadata(self) -> MetadataFilter:
        """Return comparator for run metadata."""
        return MetadataFilter(self)

    @property
    def metrics(self) -> MetricsFilter:
        """Return comparator for run metrics."""
        return MetricsFilter(self)

    @property
    def starred(self) -> Self:
        return self._boolean_flag("starred")

    @property
    def system(self) -> SystemFilter:
        """Return comparator for run system properties."""
        return SystemFilter(self)

    @property
    def status(self) -> ObjectStrProperty:
        """Return comparator for run status."""
        return ObjectStrProperty(
            "status",
            self,
            choices=["running", "created", "terminated", "lost", "failed", "completed"],
        )

    @property
    def owned_by_user(self) -> "ObjectStrProperty":
        """Return comparator for if run owned by user."""
        return ObjectStrProperty(name="user", filter=self).equals("self")

    @property
    def owned_by_others(self) -> "ObjectStrProperty":
        """Return comparator for if run owned by others."""
        return ObjectStrProperty(name="user", filter=self).not_equals("self")

    @property
    def shared_with_user(self) -> Self:
        """Return comparator for if run shared with user."""
        return self._boolean_flag("shared")
