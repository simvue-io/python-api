"""Base filter classes for constructing filter based queries.

Allows more advanced querying of the Simvue server based on conditionals.
"""

import json
import sys
import typing
import pydantic

if sys.version_info < (3, 11):
    from typing_extensions import Self
else:
    from typing import Self

if typing.TYPE_CHECKING:
    from simvue.api.objects.base import SimvueObject

T = typing.TypeVar("T")


class RestAPIFilter:
    """Base class for attaching filters to server object queries."""

    def __init__(self, sv_obj: typing.Type["SimvueObject"]) -> None:
        """Initialise a new filter object, attaching it to a simvue object class."""
        self.query: list[str] = []
        self._sv_obj: typing.Type["SimvueObject"] = sv_obj

    def clear(self) -> None:
        """Clear the query set."""
        self.query = []

    def get(self, *args, **kwargs) -> None:
        """Perform a server search using the parent Simvue object class."""
        return self._sv_obj.get(filters=json.dumps(self.query), *args, **kwargs)

    def _boolean_flag(self, name: str) -> Self:
        """Construct a flag based filter query."""
        self.query.append(name)
        return self


class ObjectProperty:
    """Base class for filtering by object property."""

    @pydantic.validate_call(config={"arbitrary_types_allowed": True})
    def __init__(
        self,
        *,
        name: str,
        filter: "RestAPIFilter",
        property_type: typing.Type[T],
        choices: list[T] | None = None,
    ) -> None:
        """Initialise an ObjectProperty.

        Parameters
        ----------
        *
        name: str
            name of the filterable attribute.
        filter: RestAPIFilter
            the parent filter object.
        property_type: Type[T]
            the Python type of the attribute.
        choices: list[T] | None, optional
            if specified, the allowed values.

        """
        self._choices: list[T] = choices
        self._name: str = name
        self._parent_filter = filter
        self._property_type: property_type

    @pydantic.validate_call
    def equals(self, value: T) -> "RestAPIFilter":
        """Append filter checking equivalence."""
        if self._choices and value not in self._choices:
            raise ValueError(f"Value '{value}' not valid for filter '{self._name}'")
        self._parent_filter.query.append(f"{self._name} == {value}")
        return self._parent_filter

    @pydantic.validate_call
    def not_equals(self, value: T) -> "RestAPIFilter":
        """Append filter checking non-equivalence."""
        if self._choices and value not in self._choices:
            raise ValueError(f"Value '{value}' not valid for filter '{self._name}'")
        self._parent_filter.query.append(f"{self._name} == {value}")
        return self._parent_filter


class ObjectStrProperty(ObjectProperty):
    """Class for filtering string based properties."""

    def __init__(
        self,
        *,
        name: str,
        filter: "RestAPIFilter",
        choices: list[str] | None = None,
        **_,
    ) -> None:
        """Initialise an ObjectStrProperty.

        Parameters
        ----------
        *
        name: str
            name of the filterable attribute.
        filter: RestAPIFilter
            the parent filter object.
        choices: list[str] | None, optional
            if specified, the allowed values.

        """
        super().__init__(name=name, filter=filter, property_type=str, choices=choices)

    def contains(self, value: str) -> "RestAPIFilter":
        """Append filter checking for substring."""
        self._parent_filter.query.append(f"{self._name} contains {value}")
        return self._parent_filter


class ObjectNumericProperty(ObjectProperty):
    """Class for filtering numeric properties."""

    def __init__(
        self,
        *,
        name: str,
        filter: "RestAPIFilter",
        choices: list[float] | None = None,
        **_,
    ) -> None:
        """Initialise an ObjectNumericProperty.

        Parameters
        ----------
        *
        name: str
            name of the filterable attribute.
        filter: RestAPIFilter
            the parent filter object.
        choices: list[float] | None, optional
            if specified, the allowed values.

        """
        super().__init__(name=name, filter=filter, property_type=float, choices=choices)

    def less_than(self, value: str) -> "RestAPIFilter":
        """Append filter checking attribute below value."""
        self._parent_filter.query.append(f"{self._name} < {value}")
        return self._parent_filter

    def greater_than(self, value: str) -> "RestAPIFilter":
        """Append filter checking attribute above value."""
        self._parent_filter.query.append(f"{self._name} > {value}")
        return self._parent_filter

    def less_than_or_equal_to(self, value: str) -> "RestAPIFilter":
        """Append filter checking attribute below or equal to value."""
        self._parent_filter.query.append(f"{self._name} <= {value}")
        return self._parent_filter

    def greater_than_or_equal_to(self, value: str) -> "RestAPIFilter":
        """Append filter checking attribute above or equal to value."""
        self._parent_filter.query.append(f"{self._name} >= {value}")
        return self._parent_filter


class AggregateFilter:
    """Class for filtering numeric sets based on aggregations."""

    def __init__(self, *, name: str, filter: "RestAPIFilter") -> None:
        """Initialise an aggregatable attribute filter.

        Parameters
        ----------
        *
        name: str
            name of the filterable attribute.
        filter: RestAPIFilter
            the parent filter object.

        """
        self._name = name
        self._parent_filter = filter

    @property
    def average(self) -> "RestAPIFilter":
        """Append filter checking average comparison."""
        return ObjectNumericProperty(f"{self._name}.average", self._parent_filter)

    @property
    def last(self) -> "RestAPIFilter":
        """Append filter checking last value comparison."""
        return ObjectNumericProperty(f"{self._name}.last", self._parent_filter)

    @property
    def min(self) -> "RestAPIFilter":
        """Append filter checking minimum value comparison."""
        return ObjectNumericProperty(f"{self._name}.min", self._parent_filter)

    @property
    def max(self) -> "RestAPIFilter":
        """Append filter checking maximum value comparison."""
        return ObjectNumericProperty(f"{self._name}.max", self._parent_filter)


class ObjectPolytypeProperty(ObjectStrProperty, ObjectNumericProperty):
    """Class for filtering attributes which can be either numeric or string."""

    def __init__(
        self,
        *,
        name: str,
        filter: "RestAPIFilter",
    ) -> None:
        """Initialise an ObjectPolytypeProperty.

        Parameters
        ----------
        *
        name: str
            name of the filterable attribute.
        filter: RestAPIFilter
            the parent filter object.

        """
        super().__init__(name=name, filter=filter, choices=None)

    @property
    def exists(self) -> "RestAPIFilter":
        """Append filter checking if attribute exists."""
        self._parent_filter.query.append(f"{self._name} exists")
        return self._parent_filter

    @property
    def does_not_exist(self) -> "RestAPIFilter":
        """Append filter checking if attribute does not exist."""
        self._parent_filter.query.append(f"{self._name} not exists")
        return self._parent_filter


class ObjectListProperty(ObjectProperty):
    """Class for filtering list based properties."""

    def __init__(
        self,
        name: str,
        filter: "RestAPIFilter",
        member_property_type: typing.Type[T],
        member_choices: list[T] | None = None,
    ) -> None:
        """Initialise an ObjectListProperty.

        Parameters
        ----------
        *
        name: str
            name of the filterable attribute.
        filter: RestAPIFilter
            the parent filter object.
        member_property_type: Type[T]
            the Python type of the attribute list members.
        member_choices: list[float] | None, optional
            if specified, the allowed values for members.

        """
        self._member_type = member_property_type
        self._member_choices = member_choices
        super().__init__(name, filter, list)

    def includes(self, values: T | list[T]) -> "RestAPIFilter":
        """Append filter checking if value is a member of attribute."""
        return self._list_check(values, True)

    def excludes(self, values: T | list[T]) -> "RestAPIFilter":
        """Append filter checking if value is not a member of attribute."""
        return self._list_check(values, False)

    def _list_check(self, values: T | list[T], contains: bool) -> "RestAPIFilter":
        """Assemble the list based filters."""
        _query_name: str = self._name
        if isinstance(values, str):
            values = [values]
        if _query_name.endswith("s"):
            _query_name = _query_name[:-1]
        for value in values:
            if self._member_choices and value not in self._member_choices:
                raise ValueError(
                    f"Value '{value}' not allowed for filter '{self._name}'"
                )
            self._parent_filter.query.append(
                f"has{' not' if not contains else ''} {_query_name}.{value}"
            )
        return self._parent_filter


class TemporalFilter(RestAPIFilter):
    """Class for filtering temporal properties."""

    def _time_within(
        self, time_type: str, *, hours: int = 0, days: int = 0, years: int = 0
    ) -> "RestAPIFilter":
        """Construct filter based on upper time threshold."""
        if len(_non_zero := list(i for i in (hours, days, years) if i != 0)) > 1:
            raise AssertionError(
                "Only one duration type may be provided: hours, days or years"
            )
        if len(_non_zero) < 1:
            raise AssertionError(
                f"No duration provided for filter '{time_type.value}_within'"
            )

        if hours:
            self.query.append(f"{time_type} < {hours}h")
        elif days:
            self.query.append(f"{time_type} < {days}d")
        else:
            self.query.append(f"{time_type} < {years}y")
        return self

    @pydantic.validate_call
    def created_within(
        self,
        *,
        hours: pydantic.PositiveInt = 0,
        days: pydantic.PositiveInt = 0,
        years: pydantic.PositiveInt = 0,
    ) -> "RestAPIFilter":
        """Append filter checking that created status is within a time period.

        Note only one parameter should be specified.

        Parameters
        ----------
        *
        hours: int, optional
            number of hours
        days: int, optional
            number of days
        years: int, optional
            number of years

        Returns
        -------
        RestAPIFilter
            parent filter object

        Raises
        ------
        AssertionError
            if no arguments or more than one argument is provided.
        """
        return self._time_within("created", hours=hours, days=days, years=years)

    @pydantic.validate_call
    def started_within(
        self,
        *,
        hours: pydantic.PositiveInt = 0,
        days: pydantic.PositiveInt = 0,
        years: pydantic.PositiveInt = 0,
    ) -> "RestAPIFilter":
        """Append filter checking that started status is within a time period.

        Note only one parameter should be specified.

        Parameters
        ----------
        *
        hours: int, optional
            number of hours
        days: int, optional
            number of days
        years: int, optional
            number of years

        Returns
        -------
        RestAPIFilter
            parent filter object

        Raises
        ------
        AssertionError
            if no arguments or more than one argument is provided.
        """
        return self._time_within("started", hours=hours, days=days, years=years)

    @pydantic.validate_call
    def modified_within(
        self,
        *,
        hours: pydantic.PositiveInt = 0,
        days: pydantic.PositiveInt = 0,
        years: pydantic.PositiveInt = 0,
    ) -> "RestAPIFilter":
        """Append filter checking that modified status is within a time period.

        Note only one parameter should be specified.

        Parameters
        ----------
        *
        hours: int, optional
            number of hours
        days: int, optional
            number of days
        years: int, optional
            number of years

        Returns
        -------
        RestAPIFilter
            parent filter object

        Raises
        ------
        AssertionError
            if no arguments or more than one argument is provided.
        """
        return self._time_within("modified", hours=hours, days=days, years=years)

    @pydantic.validate_call
    def ended_within(
        self,
        *,
        hours: pydantic.PositiveInt = 0,
        days: pydantic.PositiveInt = 0,
        years: pydantic.PositiveInt = 0,
    ) -> "RestAPIFilter":
        """Append filter checking that ended status is within a time period.

        Note only one parameter should be specified.

        Parameters
        ----------
        *
        hours: int, optional
            number of hours
        days: int, optional
            number of days
        years: int, optional
            number of years

        Returns
        -------
        RestAPIFilter
            parent filter object

        Raises
        ------
        AssertionError
            if no arguments or more than one argument is provided.
        """
        return self._time_within("ended", hours=hours, days=days, years=years)


class PropertyComposite:
    """Class acting as a struct for properties with sub-attributes."""

    def __init__(
        self,
        *,
        name: str,
        filter: "RestAPIFilter",
        parent: typing.Optional["PropertyComposite"] | None = None,
    ) -> None:
        """Initialise a PropertyComposite.

        Parameters
        ----------
        name: str
            name of the filterable attribute.
        filter: RestAPIFilter
            the parent filter object.
        parent: PropertyComposite, optional
            if this composite is the child of another, the parent, default None.

        """
        self._name: str = name if not parent else f"{parent._name}.{name}"
        self._parent_filter = filter


class MetadataFilter(PropertyComposite):
    """Class defining a filter for metadata."""

    def __init__(self, *, filter: "RestAPIFilter") -> None:
        """Initialise a new metadata filter.

        Parameters
        ----------
        filter: RestAPIFilter
            the parent filter object.

        """
        super().__init__("metadata", filter)

    @property
    def __getattr__(self, name: str) -> object:
        return ObjectPolytypeProperty(
            name=f"{self._name}.{name}", filter=self._parent_filter
        )

    def __call__(self, name: str) -> object:
        return ObjectPolytypeProperty(
            name=f"{self._name}.{name}", filter=self._parent_filter
        )
