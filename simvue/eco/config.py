"""
Eco Config
==========

Configuration file extension for configuring the Simvue Eco sub-module.
"""

__date__ = "2025-03-06"

import pydantic


class EcoConfig(pydantic.BaseModel):
    """Configurations for CO2 emission metrics gathering.

    Parameters
    ----------
    co2_signal_api_token: str | None, optional
        the CO2 signal API token (Recommended), default is None
    cpu_thermal_design_power: int | None, optional
        the TDP for the CPU
    gpu_thermal_design_power: int | None, optional
        the TDP for each GPU
    """

    co2_signal_api_token: pydantic.SecretStr | None = None
    cpu_thermal_design_power: pydantic.PositiveInt | None = None
    cpu_n_cores: pydantic.PositiveInt | None = None
    gpu_thermal_design_power: pydantic.PositiveInt | None = None
    intensity_refresh_interval: pydantic.PositiveInt | str | None = pydantic.Field(
        default="1 hour", gt=2 * 60
    )
    co2_intensity: float | None = None
