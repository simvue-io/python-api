"""Simvue Configuration File Models.

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
from simvue.utilities import get_expiry

logger = logging.getLogger(__name__)


class CertificateSpecifications(pydantic.BaseModel):
    storage_ca_cert: pydantic.FilePath | bool = True
    server_ca_cert: pydantic.FilePath | bool = True
    client_cert: pydantic.FilePath | None = None
    client_key: pydantic.SecretStr | None = None

    @pydantic.model_validator(mode="before")
    @classmethod
    def check_for_cert_env(
        cls, values: dict[str, pathlib.Path | str | None]
    ) -> dict[str, pathlib.Path | str | None]:
        """Check for CA certificate for storage specification in environment."""
        if (
            _env_ca_cert := os.environ.get("SIMVUE_STORAGE_CA_CERTIFICATE")
        ) is not None:
            values["storage_ca_cert"] = _env_ca_cert
        if (_env_ca_cert := os.environ.get("SIMVUE_SERVER_CA_CERTIFICATE")) is not None:
            values["server_ca_cert"] = _env_ca_cert
        if _env_client_cert := os.environ.get("SIMVUE_SERVER_CLIENT_CERTIFICATE"):
            values["client_cert"] = _env_client_cert
        return values


class ServerSpecifications(pydantic.BaseModel):
    model_config: typing.ClassVar[pydantic.ConfigDict] = pydantic.ConfigDict(
        extra="forbid",
        strict=True,
    )
    url: pydantic.AnyHttpUrl | None
    token: pydantic.SecretStr | None
    env: dict[str, str] | None = None
    certificates: CertificateSpecifications = pydantic.Field(
        default_factory=CertificateSpecifications
    )

    @pydantic.field_validator("url")
    @classmethod
    def url_to_api_url(cls, v: typing.Any) -> str | None:
        if not v:
            return None
        if f"{v}".endswith("/api"):
            return f"{v}"
        _url = URL(f"{v}") / "api"
        return f"{_url}"

    @pydantic.field_validator("token")
    @classmethod
    def check_token(cls, v: pydantic.SecretStr | None) -> pydantic.SecretStr | None:
        if not v:
            return None
        if not (expiry := get_expiry(v.get_secret_value())):
            raise AssertionError("Failed to parse Simvue token - invalid token form")
        if time.time() - expiry > 0:
            raise AssertionError("Simvue token has expired")
        return v


class OfflineSpecifications(pydantic.BaseModel):
    cache: pathlib.Path | None = None

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
    folder: str = pydantic.Field(default="/", pattern=sv_models.FOLDER_REGEX)
    metadata: dict[str, str | int | float | bool] | None = None
    mode: typing.Literal["offline", "disabled", "online"] = "online"
    record_shell_vars: list[str] | None = None


class ClientGeneralOptions(pydantic.BaseModel):
    debug: bool = False
