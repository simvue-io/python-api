"""
Simvue Configuration File Model
===============================

Pydantic model for the Simvue TOML configuration file

"""

import functools
import logging
import os
import typing
import pathlib

import pydantic
import toml

import simvue.utilities as sv_util
from simvue.config.parameters import (
    ClientGeneralOptions,
    DefaultRunSpecifications,
    ServerSpecifications,
    OfflineSpecifications,
)

from simvue.config.files import (
    CONFIG_FILE_NAMES,
    CONFIG_INI_FILE_NAMES,
    DEFAULT_OFFLINE_DIRECTORY,
)

logger = logging.getLogger(__name__)


class SimvueConfiguration(pydantic.BaseModel):
    # Hide values as they contain token and URL
    model_config = pydantic.ConfigDict(hide_input_in_errors=True)
    client: ClientGeneralOptions = ClientGeneralOptions()
    server: ServerSpecifications = pydantic.Field(
        ..., description="Specifications for Simvue server"
    )
    run: DefaultRunSpecifications = DefaultRunSpecifications()
    offline: OfflineSpecifications = OfflineSpecifications()

    @classmethod
    def _load_pyproject_configs(cls) -> typing.Optional[dict]:
        """Recover any Simvue non-authentication configurations from pyproject.toml"""
        _pyproject_toml = sv_util.find_first_instance_of_file(
            file_names=["pyproject.toml"], check_user_space=False
        )

        if not _pyproject_toml:
            return

        _project_data = toml.load(_pyproject_toml)

        if not (_simvue_setup := _project_data.get("tool", {}).get("simvue")):
            return

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
    @sv_util.prettify_pydantic
    def fetch(
        cls,
        server_url: typing.Optional[str] = None,
        server_token: typing.Optional[str] = None,
    ) -> "SimvueConfiguration":
        """Retrieve the Simvue configuration from this project

        Will retrieve the configuration options set for this project either using
        local or global configurations.

        Parameters
        ----------
        server_url : str, optional
            override the URL used for this session
        server_token : str, optional
            override the token used for this session

        Return
        ------
        SimvueConfiguration
            object containing configurations

        """
        _config_dict: dict[str, dict[str, str]] = cls._load_pyproject_configs() or {}

        try:
            logger.info(f"Using config file '{cls.config_file()}'")

            # NOTE: Legacy INI support has been removed
            _config_dict |= toml.load(cls.config_file())

        except FileNotFoundError:
            if not server_token or not server_url:
                _config_dict = {"server": {}}
                logger.warning("No config file found, checking environment variables")

        _config_dict["server"] = _config_dict.get("server", {})

        _config_dict["offline"] = _config_dict.get("offline", {})

        # Allow override of specification of offline directory via environment variable
        if not (_default_dir := os.environ.get("SIMVUE_OFFLINE_DIRECTORY")):
            _default_dir = _config_dict["offline"].get(
                "cache", DEFAULT_OFFLINE_DIRECTORY
            )

        _config_dict["offline"]["cache"] = _default_dir

        # Ranking of configurations for token and URl is:
        # Envionment Variables > Run Definition > Configuration File

        _server_url = os.environ.get(
            "SIMVUE_URL", server_url or _config_dict["server"].get("url")
        )

        _server_token = os.environ.get(
            "SIMVUE_TOKEN", server_token or _config_dict["server"].get("token")
        )

        if not _server_url:
            raise RuntimeError("No server URL was specified")

        if not _server_token:
            raise RuntimeError("No server token was specified")

        _config_dict["server"]["token"] = _server_token
        _config_dict["server"]["url"] = _server_url

        return SimvueConfiguration(**_config_dict)

    @classmethod
    @functools.lru_cache
    def config_file(cls) -> pathlib.Path:
        """Returns the path of top level configuration file used for the session"""
        _config_file: typing.Optional[pathlib.Path] = (
            sv_util.find_first_instance_of_file(
                CONFIG_FILE_NAMES, check_user_space=True
            )
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
