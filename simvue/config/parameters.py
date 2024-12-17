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
from simvue.api.url import URL


logger = logging.getLogger(__file__)


class ServerSpecifications(pydantic.BaseModel):
    url: pydantic.AnyHttpUrl
    token: pydantic.SecretStr

    @pydantic.field_validator("url")
    @classmethod
    def url_to_api_url(cls, v: typing.Any) -> str:
        if f"{v}".endswith("/api"):
            return URL(f"{v}")
        _url = URL(f"{v}") / "api"
        return f"{_url}"

    @pydantic.field_validator("token")
    def check_token(cls, v: typing.Any) -> str:
        value = v.get_secret_value()
        if not (expiry := get_expiry(value)):
            raise AssertionError("Failed to parse Simvue token - invalid token form")
        if time.time() - expiry > 0:
            raise AssertionError("Simvue token has expired")
        return v


class OfflineSpecifications(pydantic.BaseModel):
    cache: typing.Optional[pathlib.Path] = None


class MetricsSpecifications(pydantic.BaseModel):
    resources_metrics_interval: pydantic.PositiveInt | None = -1
    emission_metrics_interval: pydantic.PositiveInt | None = None
    enable_emission_metrics: bool = False


class DefaultRunSpecifications(pydantic.BaseModel):
    name: typing.Optional[str] = None
    description: typing.Optional[str] = None
    tags: typing.Optional[list[str]] = None
    folder: str = pydantic.Field("/", pattern=sv_models.FOLDER_REGEX)
    metadata: typing.Optional[dict[str, typing.Union[str, int, float, bool]]] = None
    mode: typing.Literal["offline", "disabled", "online"] = "online"


class ClientGeneralOptions(pydantic.BaseModel):
    debug: bool = False
