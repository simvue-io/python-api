"""
Simvue Configuration File Models
================================

Pydantic models for elements of the Simvue configuration file

"""

import logging
import os
import pathlib
import time
import typing

import pydantic

import simvue.models as sv_models
from simvue.api.url import URL
from simvue.config.files import DEFAULT_OFFLINE_DIRECTORY
from simvue.utilities import get_expiry

logger = logging.getLogger(__file__)


class ServerSpecifications(pydantic.BaseModel):
    url: pydantic.AnyHttpUrl
    token: pydantic.SecretStr

    @pydantic.field_validator("url")
    @classmethod
    def url_to_api_url(cls, v: typing.Any) -> str | None:
        if f"{v}".endswith("/api"):
            return f"{v}"
        _url = URL(f"{v}") / "api"
        return f"{_url}"

    @pydantic.field_validator("token")
    def check_token(cls, v: typing.Any) -> str | None:
        value = v.get_secret_value()
        if not (expiry := get_expiry(value)):
            raise AssertionError("Failed to parse Simvue token - invalid token form")
        if time.time() - expiry > 0:
            raise AssertionError("Simvue token has expired")
        return v


class OfflineSpecifications(pydantic.BaseModel):
    cache: pathlib.Path = pathlib.Path(DEFAULT_OFFLINE_DIRECTORY)

    @pydantic.field_validator("cache")
    @classmethod
    def check_valid_cache_path(cls, cache: pathlib.Path) -> pathlib.Path:
        if not cache.parent.exists():
            raise FileNotFoundError(f"No such directory '{cache.parent}'.")
        if not cache.parent.is_dir():
            raise FileNotFoundError(f"'{cache.parent}' is not a directory.")
        if not os.access(cache.parent, os.W_OK):
            raise AssertionError(f"'{cache.parent}' is not a writable location.")
        return cache


class MetricsSpecifications(pydantic.BaseModel):
    system_metrics_interval: pydantic.PositiveInt | None = -1
    enable_emission_metrics: bool = False


class DefaultRunSpecifications(pydantic.BaseModel):
    name: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    folder: str = pydantic.Field("/", pattern=sv_models.FOLDER_REGEX)
    metadata: dict[str, str | int | float | bool] | None = None
    mode: typing.Literal["offline", "disabled", "online"] = "online"
    record_shell_vars: list[str] | None = None


class ClientGeneralOptions(pydantic.BaseModel):
    debug: bool = False
