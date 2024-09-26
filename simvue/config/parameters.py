import logging
import time
import pydantic
import typing
import pathlib
import http

import simvue.models as sv_models
from simvue.utilities import get_expiry
from simvue.version import __version__
from simvue.api import get

CONFIG_FILE_NAMES: list[str] = ["simvue.toml", ".simvue.toml"]

CONFIG_INI_FILE_NAMES: list[str] = [
    f'{pathlib.Path.cwd().joinpath("simvue.ini")}',
    f'{pathlib.Path.home().joinpath(".simvue.ini")}',
]

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

    @pydantic.model_validator(mode="after")
    @classmethod
    def check_valid_server(cls, values: "ServerSpecifications") -> bool:
        headers: dict[str, str] = {
            "Authorization": f"Bearer {values.token}",
            "User-Agent": f"Simvue Python client {__version__}",
        }
        try:
            response = get(f"{values.url}/api/version", headers)

            if response.status_code != http.HTTPStatus.OK or not response.json().get(
                "version"
            ):
                raise AssertionError

            if response.status_code == http.HTTPStatus.UNAUTHORIZED:
                raise AssertionError("Unauthorised token")

        except Exception as err:
            raise AssertionError(f"Exception retrieving server version: {str(err)}")

        return values


class DefaultRunSpecifications(pydantic.BaseModel):
    description: typing.Optional[str] = None
    tags: list[str] | None = None
    folder: str = pydantic.Field("/", pattern=sv_models.FOLDER_REGEX)


class ClientGeneralOptions(pydantic.BaseModel):
    debug: bool = False
