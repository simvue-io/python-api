import pydantic
import logging
import toml
import typing
import os

import simvue.utilities as sv_util

from simvue.config.parameters import (
    ClientGeneralOptions,
    ServerSpecifications,
    DefaultRunSpecifications,
    CONFIG_FILE_NAMES
)

logger = logging.getLogger(__file__)

class SimvueConfiguration(pydantic.BaseModel):
    client: ClientGeneralOptions=ClientGeneralOptions()
    server: ServerSpecifications=pydantic.Field(
        ...,
        description="Specifications for Simvue server"
    )
    run: DefaultRunSpecifications=DefaultRunSpecifications()

    @classmethod
    def fetch(
        cls,
        server_url: typing.Optional[str]=None,
        server_token: typing.Optional[str]=None
    ) -> "SimvueConfiguration":
        _config_dict: dict[str, dict[str, str]] = {}

        try:
            logger.info(f"Using config file '{cls.config_file()}'")   
            _config_dict = toml.load(cls.config_file())
        except FileNotFoundError:            
            if not server_token or not server_url:
                _config_dict = {"server": {}}
                logger.warning("No config file found, checking environment variables")
        
        _config_dict["server"] = _config_dict.get("server", {})

        if server_url:
            _config_dict["server"]["url"] = server_url
        if server_token:
            _config_dict["server"]["token"] = server_token

        _config_dict["server"]["url"] = os.environ.get(
            "SIMVUE_URL",
            _config_dict["server"].get("url")
        )
        _config_dict["server"]["token"] = os.environ.get(
            "SIMVUE_TOKEN",
            _config_dict["server"].get("token")
        )

        return SimvueConfiguration(**_config_dict)

    @classmethod
    def config_file(cls) -> str:
        _config_file: typing.Optional[str] = sv_util.find_first_instance_of_file(CONFIG_FILE_NAMES, check_user_space=True)
        if not _config_file:
            raise FileNotFoundError(
                "Failed to find Simvue configuration file"
            )
        return _config_file