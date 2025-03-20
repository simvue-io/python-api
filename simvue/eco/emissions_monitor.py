"""
CO2 Monitor
===========

Provides an interface for estimating CO2 usage for processes on the CPU.
"""

__author__ = "Kristian Zarebski"
__date__ = "2025-02-27"

import datetime
import json
import pydantic
import dataclasses
import logging
import humanfriendly
import pathlib

from simvue.eco.api_client import APIClient, CO2SignalResponse

TIME_FORMAT: str = "%Y_%m_%d_%H_%M_%S"


@dataclasses.dataclass
class ProcessData:
    cpu_percentage: float = 0.0
    power_usage: float = 0.0
    total_energy: float = 0.0
    energy_delta: float = 0.0
    co2_emission: float = 0.0
    co2_delta: float = 0.0


class CO2Monitor(pydantic.BaseModel):
    """
    CO2 Monitor

    Provides an interface for estimating CO2 usage for processes on the CPU.
    """

    thermal_design_power_per_core: pydantic.PositiveFloat | None
    cpu_idle_power: pydantic.PositiveFloat
    cpu_interval: float = 1.0
    local_data_directory: pydantic.DirectoryPath
    intensity_refresh_rate: int | None | str
    co2_intensity: float | None
    co2_signal_api_token: str | None

    def now(self) -> str:
        """Return data file timestamp for the current time"""
        _now: datetime.datetime = datetime.datetime.now(datetime.UTC)
        return _now.strftime(TIME_FORMAT)

    @property
    def outdated(self) -> bool:
        """Checks if the current data is out of date."""
        if not self.intensity_refresh_rate:
            return False

        _now: datetime.datetime = datetime.datetime.now()
        _last_updated: str = self._local_data["last_updated"]
        _latest_time: datetime.datetime = datetime.datetime.strptime(
            _last_updated, TIME_FORMAT
        )
        return (_now - _latest_time).seconds < self.intensity_refresh_rate

    def _load_local_data(self) -> dict[str, str | dict[str, str | float]] | None:
        """Loads locally stored CO2 intensity data"""
        self._data_file_path = self.local_data_directory.joinpath(
            "ecoclient_co2_intensity.json"
        )

        if not self._data_file_path.exists():
            return None

        with self._data_file_path.open() as in_f:
            _data: dict[str, str | dict[str, str | float]] | None = json.load(in_f)

        return _data or None

    def __init__(self, *args, **kwargs) -> None:
        """Initialise a CO2 Monitor.

        Parameters
        ----------
        thermal_design_power_per_core: float | None
            the TDP value for the CPU. Default of None uses naive 85W value.
        cpu_idle_power: float
            the idle power of the CPU, default is naive value of 10W.
        cpu_interval: float
            the interval within which to measure average CPU percentage, default is 1s.
        local_data_directory: pydantic.DirectoryPath
            the directory in which to store CO2 intensity data.
        intensity_refresh_rate: int | str | None
            the rate in seconds at which to call the CO2 signal API. The default is once per day,
            note the API is restricted to 30 requests per hour for a given user. Also accepts a
            time period as a string, e.g. '1 week'
        co2_intensity: float | None
            disable using RestAPIs to retrieve CO2 intensity and instead use this value.
            Default is None, use remote data. Value is in kgCO2/kWh
        co2_signal_api_token: str
            RECOMMENDED. The API token for CO2 signal, default is None.
        """
        _logger = logging.getLogger(self.__class__.__name__)
        if not isinstance(kwargs.get("thermal_design_power_per_core"), float):
            kwargs["thermal_design_power_per_core"] = 80.0
            _logger.warning(
                "⚠️  No TDP value provided for current CPU, will use arbitrary value of 80W."
            )
        super().__init__(*args, **kwargs)

        if self.intensity_refresh_rate and isinstance(self.intensity_refresh_rate, str):
            self.intensity_refresh_rate = int(
                humanfriendly.parse_timespan(self.intensity_refresh_rate)
            )

        if self.intensity_refresh_rate and self.intensity_refresh_rate <= 2 * 60:
            raise ValueError(
                "Invalid intensity refresh rate, CO2 signal API restricted to 30 calls per hour."
            )

        if self.co2_intensity:
            _logger.warning(
                f"⚠️ Disabling online data retrieval, using {self.co2_intensity} for CO2 intensity."
            )

        self._data_file_path: pathlib.Path | None = None

        # Load any local data first, if the data is missing or due a refresh this will be None
        self._local_data: dict[str, str | dict[str, float | str]] | None = (
            self._load_local_data() or {}
        )
        self._measure_time = datetime.datetime.now()
        self._logger = _logger
        self._client: APIClient = APIClient(
            co2_api_token=self.co2_signal_api_token, timeout=10
        )
        self._processes: dict[str, ProcessData] = {}

    def estimate_co2_emissions(
        self, process_id: str, cpu_percent: float, cpu_interval: float
    ) -> None:
        """Estimate the CO2 emissions"""
        self._logger.debug(
            f"📐 Estimating CO2 emissions from CPU usage of {cpu_percent}% in interval {cpu_interval}s."
        )

        if self._local_data is None:
            raise RuntimeError("Expected local data to be initialised.")

        if not self._data_file_path:
            raise RuntimeError("Expected local data file to be defined.")

        if not (_process := self._processes.get(process_id)):
            self._processes[process_id] = (_process := ProcessData())

        if (
            not self.co2_intensity
            and not self._local_data.setdefault(self._client.country_code, {})
            or self.outdated
        ):
            self._logger.info("🌍 CO2 emission outdated, calling API.")
            _data: CO2SignalResponse = self._client.get()
            self._local_data[self._client.country_code] = _data.model_dump(mode="json")
            self._local_data["last_updated"] = self.now()

            with self._data_file_path.open("w") as out_f:
                json.dump(self._local_data, out_f, indent=2)

        if self.co2_intensity:
            _current_co2_intensity = self.co2_intensity
            _co2_units = "kgCO2/kWh"
        else:
            self._current_co2_data = CO2SignalResponse(
                **self._local_data[self._client.country_code]
            )
            _current_co2_intensity = self._current_co2_data.data.carbon_intensity
            _co2_units = self._current_co2_data.carbon_intensity_units

        _process.cpu_percentage = cpu_percent
        _previous_energy: float = _process.total_energy
        _process.power_usage = min(
            self.cpu_idle_power,
            (_process.cpu_percentage / 100.0) * self.thermal_design_power_per_core,
        )
        _process.total_energy += _process.power_usage * self.cpu_interval
        _process.energy_delta = _process.total_energy - _previous_energy

        # Measured value is in g/kWh, convert to kg/kWs
        _carbon_intensity_kgpws: float = _current_co2_intensity / (60 * 60 * 1e3)

        _previous_emission: float = _process.co2_emission

        _process.co2_delta = (
            _process.power_usage * _carbon_intensity_kgpws * self.cpu_interval
        )

        _process.co2_emission += _process.co2_delta

        self._logger.debug(
            f"📝 For _process '{process_id}', recorded: CPU={_process.cpu_percentage}%, "
            f"Power={_process.power_usage}W, CO2={_process.co2_emission}{_co2_units}"
        )

    @property
    def last_process(self) -> str | None:
        return list(self._processes.keys())[-1] if self._processes else None

    @property
    def process_data(self) -> dict[str, ProcessData]:
        return self._processes

    @property
    def current_carbon_intensity(self) -> float:
        return self._client.get().data.carbon_intensity

    @property
    def total_power_usage(self) -> float:
        return sum(process.power_usage for process in self._processes.values())

    @property
    def total_co2_emission(self) -> float:
        return sum(process.co2_emission for process in self._processes.values())

    @property
    def total_co2_delta(self) -> float:
        return sum(process.co2_delta for process in self._processes.values())

    @property
    def total_energy_delta(self) -> float:
        return sum(process.energy_delta for process in self._processes.values())

    @property
    def total_energy(self) -> float:
        return sum(process.total_energy for process in self._processes.values())
