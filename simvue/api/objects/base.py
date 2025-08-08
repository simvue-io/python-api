"""
Simvue RestAPI Objects
======================

Contains base class for interacting with objects on the Simvue server
"""

import abc
import pathlib
import typing
import inspect
import uuid
import http
import json
import logging

import msgpack
import pydantic

from simvue.utilities import staging_merger
from simvue.config.user import SimvueConfiguration
from simvue.exception import ObjectNotFoundError
from simvue.version import __version__
from simvue.api.request import (
    get as sv_get,
    get_paginated,
    post as sv_post,
    put as sv_put,
    delete as sv_delete,
    get_json_from_response,
)
from simvue.api.url import URL

logging.basicConfig(level=logging.INFO)

try:
    from typing import Self
except ImportError:
    from typing_extensions import Self

# Need to use this inside of Generator typing to fix bug present in Python 3.10 - see issue #745
T = typing.TypeVar("T", bound="SimvueObject")


def staging_check(member_func: typing.Callable) -> typing.Callable:
    """Decorator for checking if requested attribute has uncommitted changes"""

    def _wrapper(self) -> typing.Any:
        if isinstance(self, SimvueObject):
            _sv_obj = self
        elif hasattr(self, "_sv_obj"):
            _sv_obj = self._sv_obj
        else:
            raise RuntimeError(
                f"Cannot use 'staging_check' decorator on type '{type(self).__name__}'"
            )
        if _sv_obj._offline:
            return member_func(self)
        if not _sv_obj._read_only and member_func.__name__ in _sv_obj._staging:
            _sv_obj._logger.warning(
                f"Uncommitted change found for attribute '{member_func.__name__}'"
            )
        return member_func(self)

    _wrapper.__doc__ = member_func.__doc__
    _wrapper.__name__ = member_func.__name__
    _wrapper.__annotations__ = member_func.__annotations__
    _wrapper.__module__ = member_func.__module__
    _wrapper.__qualname__ = member_func.__qualname__
    _wrapper.__dict__ = member_func.__dict__
    return _wrapper


def write_only(attribute_func: typing.Callable) -> typing.Callable:
    def _wrapper(self: "SimvueObject", *args, **kwargs) -> typing.Any:
        _sv_obj = getattr(self, "_sv_obj", self)
        if _sv_obj._read_only:
            raise AssertionError(
                f"Cannot set property '{attribute_func.__name__}' "
                f"on read-only object of type '{self._label}'"
            )
        return attribute_func(self, *args, **kwargs)

    _wrapper.__name__ = attribute_func.__name__
    _wrapper.__name__ = attribute_func.__name__
    _wrapper.__annotations__ = attribute_func.__annotations__
    _wrapper.__module__ = attribute_func.__module__
    _wrapper.__qualname__ = attribute_func.__qualname__
    _wrapper.__dict__ = attribute_func.__dict__
    return _wrapper


class Visibility:
    """Interface for object visibility definition"""

    def __init__(self, sv_obj: "SimvueObject") -> None:
        """Initialise visibility with target object"""
        self._sv_obj = sv_obj

    def _update_visibility(self, key: str, value: typing.Any) -> None:
        """Update the visibility configuration for this object"""
        _visibility = self._sv_obj._get_visibility() | {key: value}
        self._sv_obj._staging["visibility"] = _visibility

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
        return self._sv_obj._get_visibility().get("users", [])

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
        return self._sv_obj._get_visibility().get("public", False)  # type: ignore

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
        return self._sv_obj._get_visibility().get("tenant", False)  # type: ignore

    @tenant.setter
    @write_only
    def tenant(self, tenant: bool) -> None:
        self._update_visibility("tenant", tenant)


class Sort(pydantic.BaseModel):
    column: str
    descending: bool = True

    def to_params(self) -> dict[str, str]:
        return {"id": self.column, "desc": self.descending}


class SimvueObject(abc.ABC):
    def __init__(
        self,
        identifier: str | None = None,
        _read_only: bool = True,
        _local: bool = False,
        _user_agent: str | None = None,
        _offline: bool = False,
        **kwargs,
    ) -> None:
        self._logger = logging.getLogger(f"simvue.{self.__class__.__name__}")
        self._label: str = getattr(self, "_label", self.__class__.__name__.lower())
        self._read_only: bool = _read_only
        self._endpoint: str = getattr(self, "_endpoint", f"{self._label}s")
        self._identifier: str | None = (
            identifier if identifier is not None else f"offline_{uuid.uuid1()}"
        )
        self._properties = [
            name
            for name, member in inspect.getmembers(self.__class__)
            if isinstance(member, property)
        ]
        self._offline: bool = _offline or (
            identifier is not None and identifier.startswith("offline_")
        )

        _config_args = {
            "server_url": kwargs.pop("server_url", None),
            "server_token": kwargs.pop("server_token", None),
            "mode": "offline" if self._offline else "online",
        }

        self._user_config = SimvueConfiguration.fetch(**_config_args)

        # Use a single file for each object so we can have parallelism
        # e.g. multiple runs writing at the same time
        self._local_staging_file: pathlib.Path = (
            self._user_config.offline.cache.joinpath(
                self._endpoint, f"{self._identifier}.json"
            )
        )

        self._headers: dict[str, str] = (
            {
                "Authorization": f"Bearer {self._user_config.server.token.get_secret_value()}",
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
            and not _local
        ):
            self._staging = self._get()

        # Recover any locally staged changes if not read-only
        self._staging |= (
            {} if (_read_only and not self._offline) else self._get_local_staged()
        )

        self._staging |= kwargs

    def _get_local_staged(self, obj_label: str | None = None) -> dict[str, typing.Any]:
        """Retrieve any locally staged data for this identifier"""
        if not self._local_staging_file.exists() or not self._identifier:
            return {}

        with self._local_staging_file.open() as in_f:
            _staged_data = json.load(in_f)

        return _staged_data

    def _stage_to_other(self, obj_label: str, key: str, value: typing.Any) -> None:
        """Stage a change to another object type"""
        with self._local_staging_file.open() as in_f:
            _staged_data = json.load(in_f)

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
        self, attribute: str, *default, url: str | None = None
    ) -> typing.Any:
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
                # If the key is not in staging, but the object is not in offline mode
                # retrieve from the server and update cache instead
                if not _offline_state and (
                    _attribute := self._get(url=url).get(attribute)
                ):
                    self._staging[attribute] = _attribute
                    return _attribute
                raise AttributeError(
                    f"Could not retrieve attribute '{attribute}' "
                    f"for {self._label} '{self._identifier}' from cached data"
                ) from e

        try:
            self._logger.debug(
                f"Retrieving attribute '{attribute}' from {self._label} '{self._identifier}'"
            )
            return self._get(url=url)[attribute]
        except KeyError as e:
            if default:
                return default[0]

            if self._offline:
                raise AttributeError(
                    f"A value for attribute '{attribute}' has "
                    f"not yet been committed for offline {self._label} '{self._identifier}'"
                ) from e
            raise RuntimeError(
                f"Expected key '{attribute}' for {self._label} '{self._identifier}'"
            ) from e

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
            return self._get_attribute("visibility")
        except AttributeError:
            return {}

    @classmethod
    def new(cls, **_) -> Self:
        pass

    @classmethod
    def ids(
        cls, count: int | None = None, offset: int | None = None, **kwargs
    ) -> typing.Generator[str, None, None]:
        """Retrieve a list of all object identifiers.

        Parameters
        ----------
        count: int | None, optional
            limit number of objects
        offset : int | None, optional
            set start index for objects list

        Yields
        -------
        str
            identifiers for all objects of this type.
        """
        _class_instance = cls(_read_only=True, _local=True)
        _count: int = 0
        for response in cls._get_all_objects(offset, count=count, **kwargs):
            if (_data := response.get("data")) is None:
                raise RuntimeError(
                    f"Expected key 'data' for retrieval of {_class_instance.__class__.__name__.lower()}s"
                )
            for entry in _data:
                yield entry["id"]
                _count += 1
                if count and _count > count:
                    return

    @classmethod
    @pydantic.validate_call
    def get(
        cls,
        count: pydantic.PositiveInt | None = None,
        offset: pydantic.NonNegativeInt | None = None,
        **kwargs,
    ) -> typing.Generator[tuple[str, T | None], None, None]:
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
        Generator[tuple[str, SimvueObject | None], None, None]
        """
        _class_instance = cls(_read_only=True, _local=True)
        _count: int = 0
        for _response in cls._get_all_objects(offset, count=count, **kwargs):
            if count and _count > count:
                return
            if (_data := _response.get("data")) is None:
                raise RuntimeError(
                    f"Expected key 'data' for retrieval of {_class_instance.__class__.__name__.lower()}s"
                )

            # If data is an empty list
            if not _data:
                return

            for entry in _data:
                _id = entry["id"]
                yield _id, cls(_read_only=True, identifier=_id, _local=True, **entry)
                _count += 1

    @classmethod
    def count(cls, **kwargs) -> int:
        """Return the total number of entries for this object type from the server.

        Returns
        -------
        int
            total from server database for current user.
        """
        _class_instance = cls(_read_only=True)
        _count_total: int = 0
        for _data in cls._get_all_objects(**kwargs):
            if not (_count := _data.get("count")):
                raise RuntimeError(
                    f"Expected key 'count' for retrieval of {_class_instance.__class__.__name__.lower()}s"
                )
            _count_total += _count
        return _count_total

    @classmethod
    def _get_all_objects(
        cls, offset: int | None, count: int | None, **kwargs
    ) -> typing.Generator[dict, None, None]:
        _class_instance = cls(_read_only=True)
        _url = f"{_class_instance._base_url}"

        _label = _class_instance.__class__.__name__.lower()
        if _label.endswith("s"):
            _label = _label[:-1]

        for response in get_paginated(
            _url, headers=_class_instance._headers, offset=offset, count=count, **kwargs
        ):
            yield get_json_from_response(
                response=response,
                expected_status=[http.HTTPStatus.OK],
                scenario=f"Retrieval of {_label}s",
            )  # type: ignore

    def read_only(self, is_read_only: bool) -> None:
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

    def commit(self) -> dict | None:
        """Send updates to the server, or if offline, store locally."""
        if self._read_only:
            raise AttributeError("Cannot commit object in 'read-only' mode")

        if self._offline:
            self._logger.debug(
                f"Writing updates to staging file for {self._label} '{self.id}': {self._staging}"
            )
            self._cache()
            return

        _response: dict | None = None

        # Initial commit is creation of object
        # if staging is empty then we do not need to use PUT
        if not self._identifier or self._identifier.startswith("offline_"):
            self._logger.debug(
                f"Posting from staged data for {self._label} '{self.id}': {self._staging}"
            )
            _response = self._post(**self._staging)
        elif self._staging:
            self._logger.debug(
                f"Pushing updates from staged data for {self._label} '{self.id}': {self._staging}"
            )
            _response = self._put(**self._staging)

        # Clear staged changes
        self._clear_staging()

        return _response

    @property
    def id(self) -> str | None:
        """The identifier for this object if applicable.

        Returns
        -------
        str | None
        """
        return self._identifier

    @property
    def _base_url(self) -> URL:
        return URL(self._user_config.server.url) / self._endpoint

    @property
    def url(self) -> URL | None:
        """The URL for accessing this object on the server.

        Returns
        -------
        simvue.api.url.URL | None
        """
        return None if self._identifier is None else self._base_url / self._identifier

    def _post(self, is_json: bool = True, **kwargs) -> dict[str, typing.Any]:
        if not is_json:
            kwargs = msgpack.packb(kwargs, use_bin_type=True)
        _response = sv_post(
            url=f"{self._base_url}",
            headers=self._headers | {"Content-Type": "application/msgpack"},
            params=self._params,
            data=kwargs,
            is_json=is_json,
        )

        if _response.status_code == http.HTTPStatus.FORBIDDEN:
            raise RuntimeError(
                f"Forbidden: You do not have permission to create object of type '{self._label}'"
            )

        _json_response = get_json_from_response(
            response=_response,
            expected_status=[http.HTTPStatus.OK, http.HTTPStatus.CONFLICT],
            scenario=f"Creation of {self._label}",
        )

        if isinstance(_json_response, list):
            raise RuntimeError(
                "Expected dictionary from JSON response but got type list"
            )

        if _id := _json_response.get("id"):
            self._logger.debug("'%s' created successfully", _id)
            self._identifier = _id

        return _json_response

    def _put(self, **kwargs) -> dict[str, typing.Any]:
        if not self.url:
            raise RuntimeError(f"Identifier for instance of {self._label} Unknown")
        _response = sv_put(
            url=f"{self.url}", headers=self._headers, data=kwargs, is_json=True
        )

        if _response.status_code == http.HTTPStatus.FORBIDDEN:
            raise RuntimeError(
                f"Forbidden: You do not have permission to create object of type '{self._label}'"
            )

        return get_json_from_response(
            response=_response,
            expected_status=[http.HTTPStatus.OK, http.HTTPStatus.CONFLICT],
            scenario=f"Creation of {self._label} '{self._identifier}",
        )

    def delete(self, **kwargs) -> dict[str, typing.Any]:
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
            raise RuntimeError(f"Object of type '{self._label}' has no identifier.")

        if not self.url:
            raise RuntimeError(f"Identifier for instance of {self._label} Unknown")
        _response = sv_delete(url=f"{self.url}", headers=self._headers, params=kwargs)
        _json_response = get_json_from_response(
            response=_response,
            expected_status=[http.HTTPStatus.OK, http.HTTPStatus.NO_CONTENT],
            scenario=f"Deletion of {self._label} '{self._identifier}'",
        )
        self._logger.debug("'%s' deleted successfully", self._identifier)

        return _json_response

    def _get(
        self, url: str | None = None, allow_parse_failure: bool = False, **kwargs
    ) -> dict[str, typing.Any]:
        if self._identifier.startswith("offline_"):
            return self._get_local_staged()

        if not self.url:
            raise RuntimeError(f"Identifier for instance of {self._label} Unknown")

        _response = sv_get(
            url=f"{url or self.url}", headers=self._headers, params=kwargs
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
            raise RuntimeError(
                f"Expected dictionary from JSON response during {self._label} retrieval "
                f"but got '{type(_json_response)}'"
            )
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

        staging_merger.merge(_local_data, self._staging)

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
        """Executed when a run switches from offline to online mode.

        In this case no action is taken.
        """
        pass

    @property
    def staged(self) -> dict[str, typing.Any] | None:
        """Return currently staged changes to this object.

        Returns
        -------
        dict[str, Any] | None
            the locally staged data if available.
        """
        return self._staging or None

    def __str__(self) -> str:
        """String representation of Simvue object."""
        return f"{self.__class__.__name__}({self.id=})"

    def __repr__(self) -> str:
        _out_str = f"{self.__class__.__module__}.{self.__class__.__qualname__}("
        _out_str += ", ".join(
            f"{property}={getattr(self, property)!r}" for property in self._properties
        )
        _out_str += ")"
        return _out_str
