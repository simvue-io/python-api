"""
Simvue RestAPI Objects
======================

Contains base class for interacting with objects on the Simvue server
"""

import abc
import pathlib
import typing
import uuid
import boltons.urlutils as bo_url
import http

from codecarbon.external.logger import logging
from codecarbon.output_methods.emissions_data import json

from simvue.config.user import SimvueConfiguration
from simvue.version import __version__
from simvue.api.request import (
    get as sv_get,
    post as sv_post,
    put as sv_put,
    delete as sv_delete,
    get_json_from_response,
)


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
        if member_func.__name__ in _sv_obj._staging:
            _sv_obj._logger.warning(
                f"Uncommitted change found for attribute '{member_func.__name__}'"
            )
        return member_func(self)

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
        """Retrieve the list of users able to see this object"""
        return self._sv_obj._get_visibility().get("users", [])

    @users.setter
    def users(self, users: list[str]) -> None:
        """Set the list of users able to see this object"""
        self._update_visibility("users", users)

    @property
    @staging_check
    def public(self) -> bool:
        """Retrieve if this object is publically visible"""
        return self._sv_obj._get_visibility().get("public", False)

    @public.setter
    def public(self, public: bool) -> None:
        """Set if this object is publically visible"""
        self._update_visibility("public", public)

    @property
    @staging_check
    def tenant(self) -> bool:
        """Retrieve the tenant group this object is visible to"""
        return self._sv_obj._get_visibility().get("tenant", False)

    @tenant.setter
    def tenant(self, tenant: bool) -> None:
        """Set the tenant group this object is visible to"""
        self._update_visibility("tenant", tenant)


class SimvueObject(abc.ABC):
    def __init__(self, identifier: typing.Optional[str] = None, **kwargs) -> None:
        self._logger = logging.getLogger(f"simvue.{self.__class__.__name__}")
        self._label: str = getattr(self, "_label", self.__class__.__name__.lower())
        self._endpoint: str = f"{self._label}s"
        self._identifier: typing.Optional[str] = (
            identifier if identifier is not None else f"offline_{uuid.uuid1()}"
        )
        self._offline: bool = identifier is not None and identifier.startswith(
            "offline_"
        )

        _config_args = {
            "server_url": kwargs.pop("server_url", None),
            "server_token": kwargs.pop("server_token", None),
        }

        self._user_config = SimvueConfiguration.fetch(**_config_args)
        self._local_staging_file: pathlib.Path = (
            self._user_config.offline.cache.joinpath("staging.json")
        )

        # Recover any locally staged changes
        self._staging: dict[str, typing.Any] = self._get_local_staged() | kwargs

        self._headers: dict[str, str] = {
            "Authorization": f"Bearer {self._user_config.server.token}",
            "User-Agent": f"Simvue Python client {__version__}",
        }

    def _get_local_staged(self) -> dict[str, typing.Any]:
        """Retrieve any locally staged data for this identifier"""
        if not self._local_staging_file.exists() or not self._identifier:
            return {}

        with self._local_staging_file.open() as in_f:
            _staged_data = json.load(in_f)

        return _staged_data.get(self._label, {}).get(self._identifier, {})

    def _get_attribute(self, attribute: str) -> typing.Any:
        try:
            return self._get()[attribute]
        except KeyError as e:
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

    def offline_mode(self, is_true: bool) -> None:
        self._offline = is_true

    def _get_visibility(self) -> dict[str, bool | list[str]]:
        try:
            return self._get_attribute("visibility")
        except AttributeError:
            return {}

    @abc.abstractclassmethod
    def new(cls, offline: bool = False, **kwargs):
        pass

    def commit(self) -> None:
        if not self._staging:
            return

        if self._offline:
            _offline_dir: pathlib.Path = self._user_config.offline.cache
            _offline_file = _offline_dir.joinpath("staging.json")
            self._cache()
            return

        # Initial commit is creation of object
        if not self._identifier or self._identifier.startswith("offline_"):
            self._post(**self._staging)
        else:
            self._put(**self._staging)

        # Clear staged changes
        self._clear_staging()

    @property
    def id(self) -> typing.Optional[str]:
        return self._identifier

    @property
    def _url_path(self) -> pathlib.Path:
        return pathlib.Path(f"api/{self._endpoint}")

    @property
    def _base_url(self) -> str:
        _url = bo_url.URL(self._user_config.server.url)
        _url.path = self._url_path
        return f"{_url}"

    @property
    def url(self) -> typing.Optional[str]:
        if self._identifier is None:
            return None
        _url = bo_url.URL(self._user_config.server.url)
        _url.path = f"{self._url_path / self._identifier}"
        return f"{_url}"

    def _post(self, **kwargs) -> dict[str, typing.Any]:
        _response = sv_post(
            url=self._base_url, headers=self._headers, data=kwargs, is_json=True
        )

        if _response.status_code == http.HTTPStatus.FORBIDDEN:
            raise RuntimeError(
                f"Forbidden: You do not have permission to create object of type '{self._label}'"
            )

        _json_response = get_json_from_response(
            response=_response,
            expected_status=[http.HTTPStatus.OK],
            scenario=f"Creation of {self.__class__.__name__.lower()} '{kwargs}'",
        )

        if not isinstance(_json_response, dict):
            raise RuntimeError(
                f"Expected dictionary from JSON response during {self._label} creation "
                f"but got '{type(_json_response)}'"
            )
        self._logger.debug("'%s' created successfully", _json_response["id"])
        self._identifier = _json_response["id"]

        return _json_response

    def _put(self, **kwargs) -> dict[str, typing.Any]:
        if not self.url:
            raise RuntimeError(
                f"Identifier for instance of {self.__class__.__name__} Unknown"
            )
        _response = sv_put(
            url=self.url, headers=self._headers, data=kwargs, is_json=True
        )

        if _response.status_code == http.HTTPStatus.FORBIDDEN:
            raise RuntimeError(
                f"Forbidden: You do not have permission to create object of type '{self._label}'"
            )

        _json_response = get_json_from_response(
            response=_response,
            expected_status=[http.HTTPStatus.OK],
            scenario=f"Creation of {self.__class__.__name__.lower()} '{self._identifier}",
        )

        if not isinstance(_json_response, dict):
            raise RuntimeError(
                f"Expected dictionary from JSON response during {self._label} modification "
                f"but got '{type(_json_response)}'"
            )
        self._logger.debug("'%s' modified successfully", self._identifier)

        return _json_response

    def delete(self) -> dict[str, typing.Any]:
        if self._get_local_staged():
            with self._local_staging_file.open() as in_f:
                _local_data = json.load(in_f)

            _local_data[self._label].pop(self._identifier, None)

            with self._local_staging_file.open("w") as out_f:
                json.dump(_local_data, out_f, indent=2)

        if self._offline:
            return {"id": self._identifier}

        if not self.url:
            raise RuntimeError(
                f"Identifier for instance of {self.__class__.__name__} Unknown"
            )
        _response = sv_delete(url=self.url, headers=self._headers)
        _json_response = get_json_from_response(
            response=_response,
            expected_status=[http.HTTPStatus.OK, http.HTTPStatus.NO_CONTENT],
            scenario=f"Deletion of {self.__class__.__name__.lower()} '{self._identifier}'",
        )
        self._logger.debug("'%s' deleted successfully", self._identifier)

        if not isinstance(_json_response, dict):
            raise RuntimeError(
                f"Expected dictionary from JSON response during {self._label} deletion "
                f"but got '{type(_json_response)}'"
            )
        return _json_response

    def _get(self) -> dict[str, typing.Any]:
        if self._offline:
            return self._get_local_staged()

        if not self.url:
            raise RuntimeError(
                f"Identifier for instance of {self.__class__.__name__} Unknown"
            )
        _response = sv_get(url=self.url, headers=self._headers)
        _json_response = get_json_from_response(
            response=_response,
            expected_status=[http.HTTPStatus.OK],
            scenario=f"Retrieval of {self.__class__.__name__.lower()} '{self._identifier}'",
        )
        self._logger.debug("'%s' retrieved successfully", self._identifier)

        if not isinstance(_json_response, dict):
            raise RuntimeError(
                f"Expected dictionary from JSON response during {self._label} retrieval "
                f"but got '{type(_json_response)}'"
            )
        return _json_response

    def _cache(self) -> None:
        if not (_dir := self._local_staging_file.parent).exists():
            _dir.mkdir()

        _local_data: dict[str, typing.Any] = {}

        if self._local_staging_file.exists():
            with self._local_staging_file.open() as in_f:
                _local_data = json.load(in_f)

        if not _local_data.get(self._label):
            _local_data[self._label] = {}

        _local_data[self._label][self._identifier] = self._staging

        with self._local_staging_file.open("w", encoding="utf-8") as out_f:
            json.dump(_local_data, out_f, indent=2)
