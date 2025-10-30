"""Simvue RestAPI Objects.

Contains base class for interacting with objects on the Simvue server
"""

from __future__ import annotations

import abc
import http
import inspect
import json
import logging
import types
import typing
import uuid
from collections.abc import Generator  # noqa: TC003

import msgpack
import pydantic

from simvue.api.request import delete as sv_delete
from simvue.api.request import (
    get as sv_get,
)
from simvue.api.request import (
    get_json_from_response,
    get_paginated,
)
from simvue.api.request import (
    post as sv_post,
)
from simvue.api.request import (
    put as sv_put,
)
from simvue.api.url import URL
from simvue.config.user import SimvueConfiguration
from simvue.exception import ObjectNotFoundError
from simvue.utilities import staging_merger
from simvue.version import __version__

try:
    from typing import Self
except ImportError:
    from typing_extensions import Self  # noqa: UP035

try:
    from typing import override
except ImportError:
    from typing_extensions import override  # noqa: UP035

if typing.TYPE_CHECKING:
    import pathlib

T = typing.TypeVar("T", bound="SimvueObject")
C = typing.TypeVar("C")
U = typing.TypeVar("U")


def staging_check(
    member_func: typing.Callable[[T], C],
) -> typing.Callable[[T], C]:
    """Check if requested attribute has uncommitted changes via decorator."""

    def _wrapper(self: T) -> C:
        _sv_obj = typing.cast("SimvueObject", getattr(self, "_sv_obj", self))
        if not hasattr(_sv_obj, "_offline"):
            _out_msg: str = (
                f"Cannot use 'staging_check' decorator on type '{type(self).__name__}'"
            )
            raise RuntimeError(_out_msg)
        if _sv_obj._offline:  # noqa: SLF001
            return member_func(self)
        if not _sv_obj._read_only and member_func.__name__ in _sv_obj._staging:  # noqa: SLF001
            _sv_obj._logger.warning(  # noqa: SLF001
                "Uncommitted change found for attribute '%s'", member_func.__name__
            )
        return member_func(self)

    _wrapper.__doc__ = member_func.__doc__
    _wrapper.__name__ = member_func.__name__
    _wrapper.__annotations__ = member_func.__annotations__
    _wrapper.__module__ = member_func.__module__
    _wrapper.__qualname__ = member_func.__qualname__
    _wrapper.__dict__ = member_func.__dict__
    return _wrapper


def write_only(
    attribute_func: typing.Callable[[T, U], None],
) -> typing.Callable[[T, U], None]:
    """Check if function only available in write mode."""

    def _wrapper(self: T, *args: U, **kwargs: U) -> object | None:
        _sv_obj: SimvueObject = typing.cast(
            "SimvueObject", getattr(self, "_sv_obj", self)
        )
        if _sv_obj._read_only:  # noqa: SLF001
            _out_msg: str = (
                f"Cannot set property '{attribute_func.__name__}' "
                f"on read-only object of type '{_sv_obj._label}'"  # noqa: SLF001
            )
            raise AssertionError(_out_msg)
        return attribute_func(self, *args, **kwargs)

    _wrapper.__name__ = attribute_func.__name__
    _wrapper.__name__ = attribute_func.__name__
    _wrapper.__annotations__ = attribute_func.__annotations__
    _wrapper.__module__ = attribute_func.__module__
    _wrapper.__qualname__ = attribute_func.__qualname__
    _wrapper.__dict__ = attribute_func.__dict__
    return _wrapper


class SimvueObjectAttribute(typing.Generic[T]):
    """Interface for attributes to Simvue objects with sub-attributes."""

    def __init__(self, sv_obj: T) -> None:
        """Initialise visibility with target object."""
        self._sv_obj: T = sv_obj


class Visibility(SimvueObjectAttribute["SimvueObject"]):
    """Interface for object visibility definition."""

    def _update_visibility(self, key: str, value: object) -> None:
        """Tpdate the visibility configuration for this object."""
        _visibility = self._sv_obj._get_visibility() | {key: value}  # noqa: SLF001
        self._sv_obj._staging["visibility"] = _visibility  # noqa: SLF001

    @property
    @staging_check
    def users(self) -> list[str]:
        """Set/retrieve the list of users able to see this object.

        Parameters
        ----------
        users : list[str]

        Returns
        -------
        list[str]
        """
        _users: list[str] = typing.cast(
            "list[str]",
            self._sv_obj._get_visibility().get("users", []),  # noqa: SLF001
        )
        return _users

    @users.setter
    @write_only
    def users(self, users: list[str]) -> None:
        self._update_visibility("users", users)

    @property
    @staging_check
    def public(self) -> bool:
        """Set/retrieve if this object is publicly visible.

        Parameters
        ----------
        public : bool

        Returns
        -------
        bool
        """
        _public: bool = typing.cast(
            "bool",
            self._sv_obj._get_visibility().get("public", False),  # noqa: SLF001
        )
        return _public

    @public.setter
    @write_only
    def public(self, public: bool) -> None:
        self._update_visibility("public", public)

    @property
    @staging_check
    def tenant(self) -> bool:
        """Set/retrieve whether this object is visible to the current tenant.

        Parameters
        ----------
        tenant : bool

        Returns
        -------
        bool
        """
        _tenant: bool = typing.cast(
            "bool",
            self._sv_obj._get_visibility().get("tenant", False),  # noqa: SLF001
        )
        return _tenant

    @tenant.setter
    @write_only
    def tenant(self, tenant: bool) -> None:
        self._update_visibility("tenant", tenant)


class Sort(pydantic.BaseModel):
    """Base class for performing sort during retrieval."""

    column: str
    descending: bool = True

    def to_params(self) -> dict[str, str | bool]:
        """Convert to RestAPI parameters."""
        return {"id": self.column, "desc": self.descending}


class VisibilityBatchArgs(pydantic.BaseModel):
    """Class defining visibility arguments for batch upload."""

    tenant: bool | None = None
    user: list[str] | None = None
    public: bool | None = None


class ObjectBatchArgs(pydantic.BaseModel):
    """Base class for object batch upload arguments."""


class SimvueObject(abc.ABC):
    """Base class for all RestAPI objects."""

    def __init__(
        self,
        identifier: str | None = None,
        *,
        _read_only: bool = True,
        _local: bool = False,
        _user_agent: str | None = None,
        _offline: bool = False,
        **kwargs: object,
    ) -> None:
        self._logger: logging.Logger = logging.getLogger(
            f"simvue.{self.__class__.__name__}"
        )
        self._label: str = getattr(self, "_label", self.__class__.__name__.lower())

        # Local blocks any remote connection completely, this prevents multiple server
        # calls when information cannot be found locally which is important
        # especially if the user opted to veto information
        self._local: bool = _local

        self._read_only: bool = _read_only
        self._is_set: bool = False
        self._endpoint: str = getattr(self, "_endpoint", f"{self._label}s")

        # For simvue object initialisation, unlike the server there is no nested
        # arguments, however this means that there are extra keys during post which
        # need removing, this attribute handles that and should be set in subclasses.
        self._local_only_args: list[str] = []

        self._identifier: str | None = (
            identifier if identifier is not None else f"offline_{uuid.uuid1()}"
        )
        self._properties: list[str] = [
            name
            for name, member in inspect.getmembers(self.__class__)
            if isinstance(member, property) and name not in ("label", "base_url")
        ]
        self._offline: bool = _offline or (
            identifier is not None and identifier.startswith("offline_")
        )

        _config_args = {
            "server_url": kwargs.pop("server_url", None),
            "server_token": kwargs.pop("server_token", None),
            "mode": "offline" if self._offline else "online",
        }

        self._user_config: SimvueConfiguration = SimvueConfiguration.fetch(
            **_config_args
        )

        # Use a single file for each object so we can have parallelism
        # e.g. multiple runs writing at the same time
        self._local_staging_file: pathlib.Path = (
            self._user_config.offline.cache.joinpath(
                self._endpoint, f"{self._identifier}.json"
            )
        )

        self._headers: dict[str, str] = (
            {
                "Authorization": (
                    f"Bearer {self._user_config.server.token.get_secret_value()}"
                ),
                "User-Agent": _user_agent or f"Simvue Python client {__version__}",
                "Accept-Encoding": "gzip",
            }
            if not self._offline
            else {}
        )

        self._params: dict[str, str] = {}

        self._staging: dict[str, typing.Any] = {}

        # If this object is read-only, but not a local construction, make an API call
        if (
            not self._identifier.startswith("offline_")
            and self._read_only
            and not self._local
        ):
            self._staging = self._get()

        # Recover any locally staged changes if not read-only
        self._staging |= (
            {} if (_read_only and not self._offline) else self._get_local_staged()
        )

        self._staging |= kwargs

    def _get_local_staged(self) -> dict[str, object]:
        """Retrieve any locally staged data for this identifier."""
        if not self._local_staging_file.exists() or not self._identifier:
            return {}

        with self._local_staging_file.open() as in_f:
            return typing.cast("dict[str, object]", json.load(in_f))

    def _stage_to_other(
        self,
        obj_label: str,
        key: str,
        value: typing.Any,  # noqa: ANN401
    ) -> None:
        """Stage a change to another object type."""
        with self._local_staging_file.open() as in_f:
            _staged_data = typing.cast("dict[str, typing.Any]", json.load(in_f))

        if key not in _staged_data[obj_label]:
            _staged_data[key] = value
            return

        if isinstance(_staged_data[key], list):
            if not _staged_data.get(key):
                _staged_data[key] = []
            _staged_data[key] += value
        elif isinstance(_staged_data[key], dict):
            if not _staged_data.get(key):
                _staged_data[key] = {}
            _staged_data[key] |= value
        else:
            _staged_data[key] = value

        with self._local_staging_file.open("w") as out_f:
            json.dump(_staged_data, out_f, indent=2)

    def _get_attribute(
        self,
        attribute: str,
        *,
        url: str | None = None,
    ) -> object:
        """Retrieve an attribute for the given object.

        Parameters
        ----------
        attribute : str
            name of attribute to retrieve
        url : str | None, optional
            alternative URL to use for retrieval.

        Returns
        -------
        object
            the attribute value
        """
        # In the case where the object is read-only, staging is the data
        # already retrieved from the server
        _attribute_is_property: bool = attribute in self._properties
        _state_is_read_only: bool = getattr(self, "_read_only", True)
        _offline_state: bool = (
            self._identifier is not None and self._identifier.startswith("offline_")
        )

        if (_attribute_is_property and _state_is_read_only) or _offline_state:
            try:
                return self._staging[attribute]
            except KeyError as e:
                if self._local:
                    raise
                # If the key is not in staging, but the object is not in offline mode
                # retrieve from the server and update cache instead
                if not _offline_state and (
                    _attribute := self._get(url=url).get(attribute)
                ):
                    self._staging[attribute] = _attribute
                    return _attribute
                _out_msg: str = (
                    f"Could not retrieve attribute '{attribute}' "
                    f"for {self._label} '{self._identifier}' from cached data"
                )
                raise AttributeError(_out_msg) from e

        try:
            self._logger.debug(
                "Retrieving attribute '%s' from %s '%s'",
                attribute,
                self._label,
                self._identifier,
            )
            return self._get(url=url)[attribute]
        except KeyError as e:
            if self._offline:
                _out_msg = (
                    f"A value for attribute '{attribute}' has "
                    f"not yet been committed for offline {self._label}"
                    f" {self._identifier}'"
                )
                raise AttributeError(_out_msg) from e
            _out_msg = (
                f"Expected key '{attribute}' for {self._label} '{self._identifier}'"
            )
            raise RuntimeError(_out_msg) from e

    def _clear_staging(self) -> None:
        self._staging = {}

        if not self._local_staging_file.exists():
            return

        with self._local_staging_file.open() as in_f:
            _staged_data = json.load(in_f)

        if _staged_data.get(self._label):
            _staged_data[self._label].pop(self._identifier, None)

        with self._local_staging_file.open("w") as out_f:
            json.dump(_staged_data, out_f, indent=2)

    def _get_visibility(self) -> dict[str, bool | list[str]]:
        try:
            return typing.cast(
                "dict[str, bool | list[str]]", self._get_attribute("visibility")
            )
        except AttributeError:
            return {}

    @classmethod
    @abc.abstractmethod
    def new(cls, **_: typing.Any) -> Self:  # noqa: ANN401
        """Define new instance of this object."""

    @classmethod
    def batch_create(
        cls, obj_args: ObjectBatchArgs, visibility: VisibilityBatchArgs
    ) -> Generator[str]:
        """Upload a set of objects."""
        _, __ = obj_args, visibility
        raise NotImplementedError

    @classmethod
    def ids(
        cls, count: int | None = None, offset: int | None = None, **kwargs: object
    ) -> Generator[str]:
        """Retrieve a list of all object identifiers.

        Parameters
        ----------
        count: int | None, optional
            limit number of objects
        offset : int | None, optional
            set start index for objects list

        Yields
        ------
        str
            identifiers for all objects of this type.
        """
        _class_instance = cls(_read_only=True, _local=True)
        _count: int = 0
        for response in cls._get_all_objects(offset, count=count, **kwargs):  # pyright: ignore[reportArgumentType]
            _data = typing.cast("list[dict[str, object]] | None", response.get("data"))
            if _data is None:
                _out_msg: str = (
                    f"Expected key 'data' for retrieval of "
                    f"{_class_instance.__class__.__name__.lower()}s"
                )
                raise RuntimeError(_out_msg)
            for entry in _data:
                _id = typing.cast("str", entry["id"])
                yield _id
                _count += 1
                if count and _count > count:
                    return

    @classmethod
    @pydantic.validate_call
    def get(
        cls,
        *,
        count: pydantic.PositiveInt | None = None,
        offset: pydantic.NonNegativeInt | None = None,
        **kwargs: object,
    ) -> Generator[tuple[str, Self]]:
        """Retrieve items of this object type from the server.

        Parameters
        ----------
        count: int | None, optional
            limit number of objects
        offset : int | None, optional
            set start index for objects list

        Yields
        ------
        tuple[str, SimvueObject | None]
            object corresponding to an entry on the server.

        Returns
        -------
        Generator[tuple[str, SimvueObject]]
        """
        _class_instance = cls(_read_only=True, _local=True)
        _count: int = 0

        for _response in cls._get_all_objects(offset, count=count, **kwargs):  # pyright: ignore[reportArgumentType]
            if count and _count > count:
                return

            _data = typing.cast("list[dict[str, object]] | None", _response.get("data"))
            if _data is None:
                _out_msg: str = (
                    f"Expected key 'data' for retrieval of "
                    f"{_class_instance.__class__.__name__.lower()}s"
                )
                raise RuntimeError(_out_msg)

            # If data is an empty list
            if not _data:
                return

            for entry in _data:
                _id = typing.cast("str", entry["id"])
                yield _id, cls(_read_only=True, identifier=_id, _local=True, **entry)  # pyright: ignore[reportArgumentType]
                _count += 1

    @classmethod
    def count(cls, **kwargs: object) -> int:
        """Return the total number of entries for this object type from the server.

        Returns
        -------
        int
            total from server database for current user.
        """
        _class_instance = cls(_read_only=True)
        _count_total: int = 0
        for _data in cls._get_all_objects(count=None, offset=None, **kwargs):  # pyright: ignore[reportArgumentType]
            _count = typing.cast("int | None", _data.get("count"))
            if not _count:
                _out_msg: str = (
                    "Expected key 'count' for retrieval of"
                    f" {_class_instance.__class__.__name__.lower()}s"
                )
                raise RuntimeError(_out_msg)
            _count_total += _count
        return _count_total

    @classmethod
    def _get_all_objects(
        cls,
        offset: int | None,
        count: int | None,
        endpoint: str | None = None,
        expected_type: type = dict,
        **kwargs: object,
    ) -> Generator[dict[str, object]]:
        _class_instance = cls(_read_only=True)

        # Allow the possibility of paginating a URL that is not the
        # main class endpoint
        _url = (
            f"{_class_instance._user_config.server.url}/{endpoint}"
            if endpoint
            else f"{_class_instance.base_url}"
        )

        _label = _class_instance.__class__.__name__.lower()
        _label = _label.removesuffix("s")

        for response in get_paginated(
            _url,
            headers=_class_instance._headers,
            offset=offset,
            count=count,
            **kwargs,  # pyright: ignore[reportArgumentType]
        ):
            _generator = get_json_from_response(
                response=response,
                expected_status=[http.HTTPStatus.OK],
                scenario=f"Retrieval of {_label}s",
                expected_type=expected_type,
            )

            if expected_type is dict:
                yield typing.cast("dict[str, object]", _generator)
            else:
                yield from typing.cast("list[dict[str, object]]", _generator)

    def read_only(self, is_read_only: bool) -> None:  # noqa: FBT001
        """Set whether this object is in read only state.

        Parameters
        ----------
        is_read_only : bool
            whether object is read only.
        """
        self._read_only = is_read_only

        # If using writable mode, clear the staging dictionary as
        # in this context it contains existing data retrieved
        # from the server/local entry which we dont want to
        # re-push unnecessarily, then read any locally staged changes
        if not self._read_only:
            self._staging = self._get_local_staged()

    def commit(self) -> list[dict[str, str]] | dict[str, str] | None:
        """Send updates to the server, or if offline, store locally."""
        if self._read_only:
            raise AttributeError("Cannot commit object in 'read-only' mode")

        if self._offline:
            self._logger.debug(
                "Writing updates to staging file for %s '%s': %s",
                self._label,
                self.id,
                self._staging,
            )
            self._cache()
            return None

        _response: dict[str, str] | list[dict[str, str]] | None = None

        # Initial commit is creation of object
        # if staging is empty then we do not need to use PUT
        if not self._identifier or self._identifier.startswith("offline_"):
            # If batch upload send as list, else send as dictionary of params
            _batch_commit = typing.cast(
                "list[ObjectBatchArgs] | None", self._staging.get("batch")
            )
            if _batch_commit is not None:
                self._logger.debug(
                    "Posting batched data to server: %s %ss",
                    len(_batch_commit),
                    self._label,
                )
                _response = self._post_batch(batch_data=_batch_commit)
            else:
                self._logger.debug(
                    "Posting from staged data for %s '%s': %s",
                    self._label,
                    self.id,
                    self._staging,
                )
                _response = typing.cast(
                    "dict[str, str]", self._post_single(**self._staging)
                )
        elif self._staging:
            self._logger.debug(
                "Pushing updates from staged data for %s '%s': %s",
                self._label,
                self.id,
                self._staging,
            )
            _response = typing.cast("dict[str, str]", self._put(**self._staging))

        # Clear staged changes
        self._clear_staging()

        return _response

    @property
    def offline(self) -> bool:
        """Return of object in offline mode."""
        return self._offline

    @property
    def staging(self) -> dict[str, typing.Any]:
        """Return staging mapping."""
        return self._staging

    @property
    def headers(self) -> dict[str, str]:
        """Return request headers."""
        return self._headers

    @property
    def id(self) -> str | None:
        """The identifier for this object if applicable.

        Returns
        -------
        str | None
        """
        return self._identifier

    @property
    def base_url(self) -> URL:
        """Retrieve the base URL for this object."""
        return URL(f"{self._user_config.server.url}") / self._endpoint

    @property
    def url(self) -> URL | None:
        """The URL for accessing this object on the server.

        Returns
        -------
        simvue.api.url.URL | None
        """
        return None if self._identifier is None else self.base_url / self._identifier

    def _post_batch(
        self,
        batch_data: list[ObjectBatchArgs],
    ) -> list[dict[str, str]]:
        _response = sv_post(
            url=f"{self.base_url}",
            headers=self._headers | {"Content-Type": "application/msgpack"},
            params=self._params,
            data=batch_data,
            is_json=True,
        )

        if _response.status_code == http.HTTPStatus.FORBIDDEN:
            _out_msg: str = (
                "Forbidden: You do not have permission to create object "
                f"of type '{self._label}'"
            )
            raise RuntimeError(_out_msg)

        _json_response = get_json_from_response(
            response=_response,
            expected_status=[http.HTTPStatus.OK, http.HTTPStatus.CONFLICT],
            scenario=f"Creation of multiple {self._label}s",
            expected_type=list,
        )

        if len(batch_data) != (_n_created := len(_json_response)):
            _out_msg = (
                f"Expected {len(batch_data)} to be created, "
                f"but only {_n_created} found."
            )
            raise RuntimeError(_out_msg)

        self._logger.debug("Successfully created %s %ss", _n_created, self._label)

        return typing.cast("list[dict[str, str]]", _json_response)

    def _post_single(
        self,
        *,
        is_json: bool = True,
        data: list[dict[str, object]] | dict[str, object] | None = None,
        **kwargs: object,
    ) -> dict[str, typing.Any] | list[dict[str, typing.Any]]:
        _data = kwargs if is_json else msgpack.packb(data or kwargs, use_bin_type=True)

        # Remove any extra keys
        for key in self._local_only_args:
            _ = (data or kwargs).pop(key, None)

        _response = sv_post(
            url=f"{self.base_url}",
            headers=self._headers | {"Content-Type": "application/msgpack"},
            params=self._params,
            data=_data or kwargs,
            is_json=is_json,
        )

        if _response.status_code == http.HTTPStatus.FORBIDDEN:
            _out_msg: str = (
                "Forbidden: You do not have permission to create "
                f"object of type '{self._label}'"
            )
            raise RuntimeError(_out_msg)

        _json_response = get_json_from_response(
            response=_response,
            expected_status=[http.HTTPStatus.OK, http.HTTPStatus.CONFLICT],
            scenario=f"Creation of {self._label}",
        )

        if isinstance(_json_response, list):
            raise TypeError("Expected dictionary from JSON response but got type list")

        _id = typing.cast("str | None", _json_response.get("id"))
        if _id:
            self._logger.debug("'%s' created successfully", _id)
            self._identifier = _id
        elif not self._is_set:
            _detail = _json_response.get("detail", _json_response)

            if not _detail:
                _detail = "No information in JSON response."

            _out_msg = f"Expected new ID for {self._label} but none found: {_detail}."
            raise RuntimeError(_out_msg)

        return _json_response

    def _put(self, **kwargs: object) -> dict[str, object]:
        if not self.url:
            _out_msg: str = f"Identifier for instance of {self._label} Unknown"
            raise RuntimeError(_out_msg)

        # Remove any extra keys
        for key in self._local_only_args:
            _ = kwargs.pop(key, None)

        _response = sv_put(
            url=f"{self.url}", headers=self._headers, data=kwargs, is_json=True
        )

        if _response.status_code == http.HTTPStatus.FORBIDDEN:
            _out_msg = (
                "Forbidden: You do not have permission to "
                f"create object of type '{self._label}'"
            )
            raise RuntimeError(_out_msg)

        return typing.cast(
            "dict[str, object]",
            get_json_from_response(
                response=_response,
                expected_status=[http.HTTPStatus.OK, http.HTTPStatus.CONFLICT],
                scenario=f"Creation of {self._label} '{self._identifier}",
            ),
        )

    def delete(self, **kwargs: object) -> dict[str, object]:
        """Delete the server entry for this object.

        Returns
        -------
        dict[str, Any]
            response from server on deletion.
        """
        if self._get_local_staged():
            self._local_staging_file.unlink(missing_ok=True)

        if self._offline:
            return {"id": self._identifier}

        if not self._identifier:
            _out_msg: str = f"Object of type '{self._label}' has no identifier."
            raise RuntimeError(_out_msg)

        if not self.url:
            _out_msg = f"Identifier for instance of {self._label} Unknown"
            raise RuntimeError(_out_msg)
        _response = sv_delete(url=f"{self.url}", headers=self._headers, params=kwargs)
        _json_response = get_json_from_response(
            response=_response,
            expected_status=[http.HTTPStatus.OK, http.HTTPStatus.NO_CONTENT],
            scenario=f"Deletion of {self._label} '{self._identifier}'",
        )
        self._logger.debug("'%s' deleted successfully", self._identifier)

        return typing.cast("dict[str, object]", _json_response)

    def _get(
        self,
        url: str | None = None,
        *,
        allow_parse_failure: bool = False,
        **kwargs: str | float | None,
    ) -> dict[str, typing.Any]:
        if (self._identifier or "").startswith("offline_"):
            return self._get_local_staged()

        if not self.url:
            _out_msg: str = f"Identifier for instance of {self._label} Unknown"
            raise RuntimeError(_out_msg)

        _response = sv_get(
            url=f"{url or self.url}",
            headers=self._headers,
            params=kwargs,  # pyright: ignore[reportArgumentType]
        )

        if _response.status_code == http.HTTPStatus.NOT_FOUND:
            raise ObjectNotFoundError(
                obj_type=self._label, name=self._identifier or "Unknown"
            )

        _json_response = get_json_from_response(
            response=_response,
            expected_status=[http.HTTPStatus.OK],
            allow_parse_failure=allow_parse_failure,
            scenario=f"Retrieval of {self._label} '{self._identifier}'",
        )
        self._logger.debug("'%s' retrieved successfully", self._identifier)

        if not isinstance(_json_response, dict):
            _out_msg = (
                f"Expected dictionary from JSON response during {self._label}"
                f"retrieval but got '{type(_json_response)}'"
            )
            raise TypeError(_out_msg)
        return _json_response

    def refresh(self) -> None:
        """Refresh staging from local data if in read-only mode."""
        if self._read_only:
            self._staging = self._get()

    def _cache(self) -> None:
        if not (_dir := self._local_staging_file.parent).exists():
            _dir.mkdir(parents=True)

        _local_data: dict[str, typing.Any] = {"obj_type": self.__class__.__name__}

        if self._local_staging_file.exists():
            with self._local_staging_file.open() as in_f:
                _local_data = json.load(in_f)

        _ = staging_merger.merge(_local_data, self._staging)

        with self._local_staging_file.open("w", encoding="utf-8") as out_f:
            json.dump(_local_data, out_f, indent=2)

    def to_dict(self) -> dict[str, typing.Any]:
        """Convert object to serializable dictionary.

        Returns
        -------
        dict[str, Any]
            dictionary representation of this object
        """
        return self._get() | self._staging

    def on_reconnect(self, id_mapping: dict[str, str]) -> None:
        """Perform action when switching from offline to online mode."""
        _ = id_mapping

    @property
    def staged(self) -> dict[str, typing.Any] | None:
        """Return currently staged changes to this object.

        Returns
        -------
        dict[str, Any] | None
            the locally staged data if available.
        """
        return self._staging or None

    @override
    def __str__(self) -> str:
        """Represent Simvue object as string."""
        return f"{self.__class__.__name__}({self.id=})"

    @property
    def label(self) -> str:
        """Return label for this object type."""
        return self._label

    @override
    def __repr__(self) -> str:
        """Represent Simvue object as Python repr format."""
        _out_str = f"{self.__class__.__module__}.{self.__class__.__qualname__}("
        _property_values: list[str] = []

        for _property in self._properties:
            try:
                _value = getattr(self, _property)
            except KeyError:
                continue

            if isinstance(_value, types.GeneratorType):
                continue

            _property_values.append(f"{_property}={_value!r}")

        _out_str += ", ".join(_property_values)
        _out_str += ")"
        return _out_str
