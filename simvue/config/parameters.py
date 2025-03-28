"""
Simvue Configuration File Models
================================

Pydantic models for elements of the Simvue configuration file

"""

import logging
import re
import time
import pydantic
import typing
import pathlib

import simvue.models as sv_models
from simvue.utilities import get_expiry
from simvue.api.url import URL


logger = logging.getLogger(__file__)


class ServerSpecifications(pydantic.BaseModel):
    url: pydantic.AnyHttpUrl | None
    token: pydantic.SecretStr | None

    @pydantic.field_validator("url")
    @classmethod
    def url_to_api_url(cls, v: typing.Any) -> str | None:
        if not v:
            return
        if f"{v}".endswith("/api"):
            return f"{v}"
        _url = URL(f"{v}") / "api"
        return f"{_url}"

    @pydantic.field_validator("token")
    def check_token(cls, v: typing.Any) -> str | None:
        if not v:
            return
        value = v.get_secret_value()
        if not (expiry := get_expiry(value)):
            raise AssertionError("Failed to parse Simvue token - invalid token form")
        if time.time() - expiry > 0:
            raise AssertionError("Simvue token has expired")
        return v


class OfflineSpecifications(pydantic.BaseModel):
    cache: pathlib.Path | None = None

    @pydantic.field_validator("cache")
    @classmethod
    def check_valid_cache_path(cls, cache: pathlib.Path) -> pathlib.Path:
        if not re.fullmatch(
            r"^(\/|([a-zA-Z]:\\))?([\w\s.-]+[\\/])*[\w\s.-]*$", f"{cache}"
        ):
            raise AssertionError(f"Value '{cache}' is not a valid cache path.")
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


class ClientGeneralOptions(pydantic.BaseModel):
    debug: bool = False
