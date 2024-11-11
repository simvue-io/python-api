"""
Simvue RestAPI Objects
======================

Contains base class for interacting with objects on the Simvue server
"""

import abc
import pathlib
import typing
import boltons.urlutils as bo_url
import http

from codecarbon.external.logger import logging

from simvue.config.user import SimvueConfiguration
from simvue.version import __version__
from simvue.api.request import (
    get as sv_get,
    post as sv_post,
    put as sv_put,
    delete as sv_delete,
    get_json_from_response,
)


class Visibility:
    def __init__(self, sv_obj: "SimvueObject") -> None:
        self._sv_obj = sv_obj

    def _update_visibility(self, key: str, value: typing.Any) -> None:
        _visibility = self._sv_obj._get_visibility() | {key: value}
        self._sv_obj._put(visibility=_visibility)

    @property
    def users(self) -> list[str]:
        return self._sv_obj._get_visibility().get("users", [])

    @users.setter
    def users(self, users: list[str]) -> None:
        self._update_visibility("users", users)

    @property
    def public(self) -> bool:
        return self._sv_obj._get_visibility().get("public", False)

    @public.setter
    def public(self, public: bool) -> None:
        self._update_visibility("public", public)

    @property
    def tenant(self) -> bool:
        return self._sv_obj._get_visibility().get("tenant", False)

    @tenant.setter
    def tenant(self, tenant: bool) -> None:
        self._update_visibility("tenant", tenant)


class SimvueObject(abc.ABC):
    def __init__(self, identifier: typing.Optional[str] = None, **kwargs) -> None:
        self._logger = logging.getLogger(f"simvue.{self.__class__.__name__}")
        self._label: str = getattr(self, "_label", self.__class__.__name__.lower())
        self._identifier: typing.Optional[str] = identifier
        self._user_config = SimvueConfiguration.fetch(**kwargs)
        self._headers: dict[str, str] = {
            "Authorization": f"Bearer {self._user_config.server.token}",
            "User-Agent": f"Simvue Python client {__version__}",
        }

    def _get_visibility(self) -> dict[str, bool | list[str]]:
        if not (visibility := self._get().get("visibility")):
            raise RuntimeError("Expected key 'visibility' in response")
        return visibility

    @classmethod
    def new(cls, **kwargs) -> "SimvueObject":
        _obj = SimvueObject()
        _obj._post(**kwargs)
        return _obj

    @property
    def id(self) -> typing.Optional[str]:
        return self._identifier

    @property
    def _url_path(self) -> pathlib.Path:
        return pathlib.Path(f"api/{self._label}s")

    @property
    def _base_url(self) -> str:
        _url = bo_url.URL(self._user_config.server.url)
        _url.path = self._url_path
        return f"{_url}"

    @property
    def url(self) -> typing.Optional[str]:
        if not self._identifier:
            return None
        _url = bo_url.URL(self._user_config.server.url)
        _url.path = f"{self._url_path / self._identifier}"
        return f"{_url}"

    def _post(self, **kwargs) -> dict[str, typing.Any]:
        _response = sv_post(
            url=self._base_url, headers=self._headers, data=kwargs, is_json=True
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

    def _delete(self) -> dict[str, typing.Any]:
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
