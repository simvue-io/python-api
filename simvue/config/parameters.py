"""
Simvue Configuration File Models
================================

Pydantic models for elements of the Simvue configuration file

"""

import logging
import time
import pydantic
import typing
import pathlib

import simvue.models as sv_models
from simvue.utilities import get_expiry


logger = logging.getLogger(__file__)


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
    mode: typing.Literal["offline", "disabled", "online"] = "online"


class ClientGeneralOptions(pydantic.BaseModel):
    debug: bool = False
