"""
Eco Config
==========

Configuration file extension for configuring the Simvue Eco sub-module.
"""

__date__ = "2025-03-06"

import pydantic
import pathlib
import os

from simvue.config.files import DEFAULT_OFFLINE_DIRECTORY


class EcoConfig(pydantic.BaseModel):
    co2_signal_api_token: pydantic.SecretStr | None = None
    cpu_thermal_design_power: pydantic.PositiveInt = 80
    cpu_idle_power: pydantic.PositiveFloat = 10
    local_data_directory: pydantic.DirectoryPath | None = pydantic.Field(
        None, validate_default=True
    )
    intensity_refresh_rate: pydantic.PositiveInt | str | None = pydantic.Field(
        default="1 day", gt=2 * 60
    )
    co2_intensity: float | None = None

    @pydantic.field_validator("local_data_directory", mode="before", check_fields=True)
    @classmethod
    def check_local_data_env(
        cls, local_data_directory: pathlib.Path | None
    ) -> pathlib.Path:
        if _data_directory := os.environ.get("SIMVUE_ECO_DATA_DIRECTORY"):
            return pathlib.Path(_data_directory)
        if not local_data_directory:
            local_data_directory = pathlib.Path(DEFAULT_OFFLINE_DIRECTORY)
            local_data_directory.mkdir(exist_ok=True, parents=True)
        return local_data_directory
