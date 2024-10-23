"""
Simvue Configuration File Models
================================

Pydantic models for elements of the Simvue configuration file

"""

import logging
import os
import time
import pydantic
import typing
import pathlib
import http
import functools
import semver

import simvue.models as sv_models
from simvue.utilities import get_expiry, valid_dictionary
from simvue.version import __version__
from simvue.api import get


logger = logging.getLogger(__file__)

SIMVUE_MINIMUM_SERVER_VERSION = semver.VersionInfo.parse("0.1.0")


class ServerSpecifications(pydantic.BaseModel):
    url: pydantic.AnyHttpUrl
    token: pydantic.SecretStr

    @pydantic.field_validator("url")
    @classmethod
    def url_to_str(cls, v: typing.Any) -> str:
        return f"{v}"

    @pydantic.field_validator("token")
    def check_token(cls, v: typing.Any) -> str:
        value = v.get_secret_value()
        if not (expiry := get_expiry(value)):
            raise AssertionError("Failed to parse Simvue token - invalid token form")
        if time.time() - expiry > 0:
            raise AssertionError("Simvue token has expired")
        return value

    @classmethod
    @functools.lru_cache
    def _check_server(cls, token: str, url: str) -> None:
        headers: dict[str, str] = {
            "Authorization": f"Bearer {token}",
            "User-Agent": f"Simvue Python client {__version__}",
        }
        try:
            response = get(f"{url}/api/version", headers)

            if response.status_code != http.HTTPStatus.OK or not (
                version := response.json().get("version")
            ):
                raise AssertionError

            if (
                semver.VersionInfo.parse(version.strip())
                < SIMVUE_MINIMUM_SERVER_VERSION
            ):
                raise AssertionError(
                    f"Unsupported Simvue server version <{SIMVUE_MINIMUM_SERVER_VERSION}"
                )

            if response.status_code == http.HTTPStatus.UNAUTHORIZED:
                raise AssertionError("Unauthorised token")

        except Exception as err:
            raise AssertionError(f"Exception retrieving server version: {str(err)}")

    @pydantic.model_validator(mode="after")
    @classmethod
    def check_valid_server(cls, values: "ServerSpecifications") -> bool:
        if os.environ.get("SIMVUE_NO_SERVER_CHECK"):
            return values

        cls._check_server(values.token, values.url)

        return values


class OfflineSpecifications(pydantic.BaseModel):
    cache: typing.Optional[pathlib.Path] = None

    @pydantic.field_validator("cache")
    @classmethod
    def cache_to_str(cls, v: typing.Any) -> str:
        return f"{v}"


class DefaultRunSpecifications(pydantic.BaseModel):
    name: typing.Optional[str] = None
    description: typing.Optional[str] = None
    tags: typing.Optional[list[str]] = None
    folder: str = pydantic.Field("/", pattern=sv_models.FOLDER_REGEX)
    metadata: typing.Optional[dict[str, typing.Union[str, int, float, bool]]] = None

    @pydantic.field_validator("metadata")
    @classmethod
    def cache_to_str(cls, v: typing.Any) -> str:
        if not valid_dictionary(v):
            raise AssertionError(
                "Base level keys must be of type int, float, bool or str"
            )
        return f"{v}"


class ClientGeneralOptions(pydantic.BaseModel):
    debug: bool = False
