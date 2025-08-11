"""
Simvue Configuration File Model
===============================

Pydantic model for the Simvue TOML configuration file

"""

import functools
import logging
import os
import typing
import http
import pathlib
import pydantic
import toml
import semver

import simvue.utilities as sv_util
from simvue.config.parameters import (
    ClientGeneralOptions,
    DefaultRunSpecifications,
    MetricsSpecifications,
    ServerSpecifications,
    OfflineSpecifications,
)

from simvue.config.files import (
    CONFIG_FILE_NAMES,
    CONFIG_INI_FILE_NAMES,
    DEFAULT_OFFLINE_DIRECTORY,
)
from simvue.version import __version__
from simvue.api.request import get as sv_get
from simvue.api.url import URL
from simvue.eco.config import EcoConfig

logger = logging.getLogger(__name__)

SIMVUE_SERVER_UPPER_CONSTRAINT: semver.Version | None = semver.Version.parse("2.0.0")
SIMVUE_SERVER_LOWER_CONSTRAINT: semver.Version | None = semver.Version.parse("1.0.0")


class SimvueConfiguration(pydantic.BaseModel):
    # Hide values as they contain token and URL
    model_config = pydantic.ConfigDict(
        hide_input_in_errors=True, revalidate_instances="always"
    )
    client: ClientGeneralOptions = ClientGeneralOptions()
    server: ServerSpecifications = pydantic.Field(
        ..., description="Specifications for Simvue server"
    )
    run: DefaultRunSpecifications = DefaultRunSpecifications()
    offline: OfflineSpecifications = OfflineSpecifications()
    metrics: MetricsSpecifications = MetricsSpecifications()
    eco: EcoConfig = EcoConfig()

    @classmethod
    def _load_pyproject_configs(cls) -> dict | None:
        """Recover any Simvue non-authentication configurations from pyproject.toml"""
        _pyproject_toml = sv_util.find_first_instance_of_file(
            file_names=["pyproject.toml"], check_user_space=False
        )

        if not _pyproject_toml:
            return None

        _project_data = toml.load(_pyproject_toml)

        if not (_simvue_setup := _project_data.get("tool", {}).get("simvue")):
            return None

        # Do not allow reading of authentication credentials within a project file
        _server_credentials = _simvue_setup.get("server", {})
        _offline_credentials = _simvue_setup.get("offline", {})

        if any(
            [
                _server_credentials.get("token"),
                _server_credentials.get("url"),
                _offline_credentials.get("cache"),
            ]
        ):
            raise RuntimeError(
                "Provision of Simvue URL, Token or offline directory in pyproject.toml is not allowed."
            )

        return _simvue_setup

    @classmethod
    @functools.lru_cache
    def _check_server(
        cls, token: str, url: str, mode: typing.Literal["offline", "online", "disabled"]
    ) -> None:
        if mode in ("offline", "disabled"):
            return

        headers: dict[str, str] = {
            "Authorization": f"Bearer {token}",
            "User-Agent": f"Simvue Python client {__version__}",
        }
        try:
            _url = URL(url) / "version"
            _response = sv_get(f"{_url}", headers)

            if _response.status_code != http.HTTPStatus.OK or not (
                _version_str := _response.json().get("version")
            ):
                raise AssertionError

            if _response.status_code == http.HTTPStatus.UNAUTHORIZED:
                raise AssertionError("Unauthorised token")

        except Exception as err:
            raise AssertionError(
                f"Exception retrieving server version:\n {str(err)}"
            ) from err

        _version = semver.Version.parse(_version_str)

        if (
            SIMVUE_SERVER_UPPER_CONSTRAINT
            and _version >= SIMVUE_SERVER_UPPER_CONSTRAINT
        ):
            raise AssertionError(
                f"Python API v{_version_str} is not compatible with Simvue server versions "
                f">= {SIMVUE_SERVER_UPPER_CONSTRAINT}"
            )
        if SIMVUE_SERVER_LOWER_CONSTRAINT and _version < SIMVUE_SERVER_LOWER_CONSTRAINT:
            raise AssertionError(
                f"Python API v{_version_str} is not compatible with Simvue server versions "
                f"< {SIMVUE_SERVER_LOWER_CONSTRAINT}"
            )

    @pydantic.validate_call
    def write(self, out_directory: pydantic.DirectoryPath) -> None:
        with out_directory.joinpath(CONFIG_FILE_NAMES[0]).open("w") as out_f:
            toml.dump(self.model_dump(), out_f)

    @pydantic.model_validator(mode="after")
    @classmethod
    def check_valid_server(cls, values: "SimvueConfiguration") -> "SimvueConfiguration":
        if os.environ.get("SIMVUE_NO_SERVER_CHECK"):
            return values

        cls._check_server(values.server.token, values.server.url, values.run.mode)

        return values

    @classmethod
    @sv_util.prettify_pydantic
    def fetch(
        cls,
        server_url: str | None = None,
        server_token: str | None = None,
        mode: typing.Literal["offline", "online", "disabled"] | None = None,
    ) -> "SimvueConfiguration":
        """Retrieve the Simvue configuration from this project

        Will retrieve the configuration options set for this project either using
        local or global configurations.

        Parameters
        ----------
        server_url : str | URL, optional
            override the URL used for this session
        server_token : str, optional
            override the token used for this session
        mode : 'online' | 'offline' | 'disabled'
            set the run mode for this session
                * online - send metrics and data to a server.
                * offline - run in offline mode.
                * disabled - run in disabled mode.

        Return
        ------
        SimvueConfiguration
            object containing configurations

        """
        _config_dict: dict[str, dict[str, str]] = cls._load_pyproject_configs() or {}

        try:
            # NOTE: Legacy INI support has been removed
            _config_dict |= toml.load(cls.config_file())

        except FileNotFoundError:
            if not server_token or not server_url:
                _config_dict = {"server": {}}
                logger.debug("No config file found, checking environment variables")

        _config_dict["server"] = _config_dict.get("server", {})

        _config_dict["offline"] = _config_dict.get("offline", {})

        _config_dict["run"] = _config_dict.get("run", {})

        # Allow override of specification of offline directory via environment variable
        if not (_default_dir := os.environ.get("SIMVUE_OFFLINE_DIRECTORY")):
            _default_dir = _config_dict["offline"].get(
                "cache", DEFAULT_OFFLINE_DIRECTORY
            )
        pathlib.Path(_default_dir).mkdir(parents=True, exist_ok=True)

        _config_dict["offline"]["cache"] = _default_dir

        # Ranking of configurations for token and URl is:
        # Environment Variables > Run Definition > Configuration File

        _server_url = os.environ.get(
            "SIMVUE_URL", server_url or _config_dict["server"].get("url")
        )

        if isinstance(_server_url, URL):
            _server_url = str(_server_url)

        _server_token = os.environ.get(
            "SIMVUE_TOKEN", server_token or _config_dict["server"].get("token")
        )

        _run_mode = mode or _config_dict["run"].get("mode") or "online"

        if not _server_url and _run_mode != "offline":
            raise RuntimeError("No server URL was specified")

        if not _server_token and _run_mode != "offline":
            raise RuntimeError("No server token was specified")

        _config_dict["server"]["token"] = _server_token
        _config_dict["server"]["url"] = _server_url
        _config_dict["run"]["mode"] = _run_mode

        return SimvueConfiguration(**_config_dict)

    @classmethod
    @functools.lru_cache
    def config_file(cls) -> pathlib.Path:
        """Returns the path of top level configuration file used for the session"""
        _config_file: pathlib.Path | None = sv_util.find_first_instance_of_file(
            CONFIG_FILE_NAMES, check_user_space=True
        )

        # NOTE: Legacy INI support has been removed
        if not _config_file and sv_util.find_first_instance_of_file(
            CONFIG_INI_FILE_NAMES, check_user_space=True
        ):
            raise RuntimeError(
                "Simvue INI configuration file format has been deprecated in simvue>=1.2, "
                "please use TOML file"
            )

        if not _config_file:
            raise FileNotFoundError("Failed to find Simvue configuration file")

        return _config_file
