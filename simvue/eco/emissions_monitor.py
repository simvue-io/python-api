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
import os.path

from simvue.eco.api_client import APIClient, CO2SignalResponse

TIME_FORMAT: str = "%Y_%m_%d_%H_%M_%S"
CO2_SIGNAL_API_INTERVAL_LIMIT: int = 2 * 60


@dataclasses.dataclass
class ProcessData:
    cpu_percentage: float = 0.0
    gpu_percentage: float | None = None
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

    thermal_design_power_per_cpu: pydantic.PositiveFloat | None
    n_cores_per_cpu: pydantic.PositiveInt | None
    thermal_design_power_per_gpu: pydantic.PositiveFloat | None
    local_data_directory: pydantic.DirectoryPath
    intensity_refresh_interval: int | None | str
    co2_intensity: float | None
    co2_signal_api_token: pydantic.SecretStr | None
    offline: bool = False

    def now(self) -> str:
        """Return data file timestamp for the current time"""
        _now: datetime.datetime = datetime.datetime.now(datetime.timezone.utc)
        return _now.strftime(TIME_FORMAT)

    @property
    def outdated(self) -> bool:
        """Checks if the current data is out of date."""
        if not self.intensity_refresh_interval:
            return False

        _now: datetime.datetime = datetime.datetime.now()
        _latest_time: datetime.datetime = datetime.datetime.strptime(
            self._local_data["last_updated"], TIME_FORMAT
        )
        return (_now - _latest_time).seconds > self.intensity_refresh_interval

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
        thermal_design_power_per_cpu: float | None
            the TDP value for each CPU, default is 80W.
        n_cores_per_cpu: int | None
            the number of cores in each CPU, default is 4.
        thermal_design_power_per_gpu: float | None
            the TDP value for each GPU, default is 130W.
        local_data_directory: pydantic.DirectoryPath
            the directory in which to store CO2 intensity data.
        intensity_refresh_interval: int | str | None
            the interval in seconds at which to call the CO2 signal API. The default is once per day,
            note the API is restricted to 30 requests per hour for a given user. Also accepts a
            time period as a string, e.g. '1 week'
        co2_intensity: float | None
            disable using RestAPIs to retrieve CO2 intensity and instead use this value.
            Default is None, use remote data. Value is in kgCO2/kWh
        co2_signal_api_token: str
            The API token for CO2 signal, default is None.
        offline: bool, optional
            Run without any server interaction
        """
        _logger = logging.getLogger(self.__class__.__name__)

        if not (
            kwargs.get("co2_intensity")
            or kwargs.get("co2_signal_api_token")
            or kwargs.get("offline")
        ):
            raise ValueError(
                "ElectricityMaps API token or hardcoeded CO2 intensity value is required for emissions tracking."
            )

        if not isinstance(kwargs.get("thermal_design_power_per_cpu"), float):
            kwargs["thermal_design_power_per_cpu"] = 80.0
            _logger.warning(
                "⚠️  No TDP value provided for current CPU, will use arbitrary value of 80W."
            )

        if not isinstance(kwargs.get("n_cores_per_cpu"), float):
            kwargs["n_cores_per_cpu"] = 4
            _logger.warning(
                "⚠️  No core count provided for current CPU, will use arbitrary value of 4."
            )

        if not isinstance(kwargs.get("thermal_design_power_per_gpu"), float):
            kwargs["thermal_design_power_per_gpu"] = 130.0
            _logger.warning(
                "⚠️  No TDP value provided for current GPUs, will use arbitrary value of 130W."
            )
        super().__init__(*args, **kwargs)
        self._last_local_write = datetime.datetime.now()

        if self.intensity_refresh_interval and isinstance(
            self.intensity_refresh_interval, str
        ):
            self.intensity_refresh_interval = int(
                humanfriendly.parse_timespan(self.intensity_refresh_interval)
            )

        if (
            self.intensity_refresh_interval
            and self.intensity_refresh_interval <= CO2_SIGNAL_API_INTERVAL_LIMIT
        ):
            raise ValueError(
                "Invalid intensity refresh rate, CO2 signal API restricted to 30 calls per hour."
            )

        if self.co2_intensity:
            _logger.warning(
                f"⚠️ Disabling online data retrieval, using {self.co2_intensity} eqCO2g/kwh for CO2 intensity."
            )

        self._data_file_path: pathlib.Path | None = None

        # Load any local data first, if the data is missing or due a refresh this will be None
        self._local_data: dict[str, str | dict[str, float | str]] | None = (
            self._load_local_data() or {}
        )
        self._measure_time = datetime.datetime.now()
        self._logger = _logger
        self._client: APIClient | None = (
            None
            if self.co2_intensity or self.offline
            else APIClient(co2_api_token=self.co2_signal_api_token, timeout=10)
        )
        self._processes: dict[str, ProcessData] = {}

    def check_refresh(self) -> bool:
        """Check to see if an intensity value refresh is required.

        Returns
        -------
        bool
            whether a refresh of the CO2 intensity was requested
            from the CO2 Signal API.
        """
        # Need to check if the local cache has been modified
        # even if running offline
        if (
            self._data_file_path.exists()
            and (
                _check_write := datetime.datetime.fromtimestamp(
                    os.path.getmtime(f"{self._data_file_path}")
                )
            )
            > self._last_local_write
        ):
            self._last_local_write = _check_write
            with self._data_file_path.open("r") as in_f:
                self._local_data = json.load(in_f)

        if not self._client:
            return False

        if (
            not self._local_data.setdefault(self._client.country_code, {})
            or self.outdated
        ):
            self._logger.info("🌍 CO2 emission outdated, calling API.")
            _data: CO2SignalResponse = self._client.get()
            self._local_data[self._client.country_code] = _data.model_dump(mode="json")
            self._local_data["last_updated"] = self.now()
            with self._data_file_path.open("w") as out_f:
                json.dump(self._local_data, out_f, indent=2)
            return True
        return False

    def estimate_co2_emissions(
        self,
        process_id: str,
        cpu_percent: float,
        gpu_percent: float | None,
        measure_interval: float,
    ) -> None:
        """Estimate the CO2 emissions"""
        self._logger.debug(
            f"📐 Estimating CO2 emissions from CPU usage of {cpu_percent}% "
            f"and GPU usage of {gpu_percent}%"
            if gpu_percent
            else f"in interval {measure_interval}s."
        )

        if self._local_data is None:
            raise RuntimeError("Expected local data to be initialised.")

        if not self._data_file_path:
            raise RuntimeError("Expected local data file to be defined.")

        if not (_process := self._processes.get(process_id)):
            self._processes[process_id] = (_process := ProcessData())

        if self.co2_intensity:
            _current_co2_intensity = self.co2_intensity
        else:
            self.check_refresh()
            # If no local data yet then return
            if not (_country_codes := list(self._local_data.keys())):
                self._logger.warning(
                    "No CO2 emission data recorded as no CO2 intensity value "
                    "has been provided and there is no local intensity data available."
                )
                return False

            if self._client:
                _country_code = self._client.country_code
            else:
                _country_code = _country_codes[0]
                self._logger.debug(
                    f"🗂️ Using data for region '{_country_code}' from local cache for offline estimation."
                )
            self._current_co2_data = CO2SignalResponse(
                **self._local_data[_country_code]
            )
            _current_co2_intensity = self._current_co2_data.data.carbon_intensity
        _process.gpu_percentage = gpu_percent
        _process.cpu_percentage = cpu_percent
        _process.power_usage = (_process.cpu_percentage / 100.0) * (
            self.thermal_design_power_per_cpu / self.n_cores_per_cpu
        )

        if _process.gpu_percentage and self.thermal_design_power_per_gpu:
            _process.power_usage += (
                _process.gpu_percentage / 100.0
            ) * self.thermal_design_power_per_gpu
        # Convert W to kW
        _process.power_usage /= 1000
        # Measure energy in kWh
        _process.energy_delta = _process.power_usage * measure_interval / 3600
        _process.total_energy += _process.energy_delta

        # Measured value is in g/kWh, convert to kg/kWh
        _carbon_intensity: float = _current_co2_intensity / 1000

        _process.co2_delta = _process.energy_delta * _carbon_intensity
        _process.co2_emission += _process.co2_delta

        self._logger.debug(
            f"📝 For process '{process_id}', in interval {measure_interval}, recorded: CPU={_process.cpu_percentage:.2f}%, "
            f"Power={_process.power_usage:.2f}kW, Energy = {_process.energy_delta}kWh, CO2={_process.co2_delta:.2e}kg"
        )
        return True

    def simvue_metrics(self) -> dict[str, float]:
        """Retrieve metrics to send to Simvue server."""
        return {
            "sustainability.emissions.total": self.total_co2_emission,
            "sustainability.emissions.delta": self.total_co2_delta,
            "sustainability.energy_consumed.total": self.total_energy,
            "sustainability.energy_consumed.delta": self.total_energy_delta,
        }

    @property
    def last_process(self) -> str | None:
        return list(self._processes.keys())[-1] if self._processes else None

    @property
    def process_data(self) -> dict[str, ProcessData]:
        return self._processes

    @property
    def current_carbon_intensity(self) -> float:
        return self.co2_intensity or self._client.get().data.carbon_intensity

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
