"""
CO2 Monitor
===========

Provides an interface for estimating CO2 usage for processes on the CPU.
"""

__author__ = "Kristian Zarebski"
__version__ = "0.1.0"
__license__ = "MIT"
__date__ = "2025-02-27"

import datetime
import json
import pydantic
import dataclasses
import threading
import time
import logging
import typing
import psutil
import humanfriendly
import pathlib
import os

from simvue.eco.api_client import APIClient, CO2SignalResponse

TIME_FORMAT: str = "%Y_%m_%d_%H_%M_%S"


@dataclasses.dataclass
class ProcessData:
    process: psutil.Process
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

    @pydantic.validate_call(config={"arbitrary_types_allowed": True})
    def attach_process(
        self, process: psutil.Process | None = None, label: str | None = None
    ) -> str:
        """
        Attach a process to the CO2 Monitor.

        Parameters
        ----------
        process : psutil.Process | None
            The process to monitor, if None measures the current running process. Default is None.
        label : str | None
            The label to assign to the process. Default is process_<pid>.

        Returns
        -------
        int
            The PID of the process.
        """
        if process is None:
            process = psutil.Process(pid=os.getpid())

        self._logger.info(f"📎 Attaching process with PID {process.pid}")

        label = label or f"process_{process.pid}"
        self._processes[label] = ProcessData(process=process)

        return label

    def estimate_co2_emissions(self) -> None:
        """Estimate the CO2 emissions"""
        self._logger.info("📐 Measuring CPU usage and power.")

        if self._local_data is None:
            raise RuntimeError("Expected local data to be initialised.")

        if not self._data_file_path:
            raise RuntimeError("Expected local data file to be defined.")

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

        for label, process in self._processes.items():
            process.cpu_percentage = process.process.cpu_percent(
                interval=self.cpu_interval
            )
            _previous_energy: float = process.e
            process.power_usage = min(
                self.cpu_idle_power,
                (process.cpu_percentage / 100.0) * self.thermal_design_power_per_core,
            )
            process.total_energy += process.power_usage * self.cpu_interval
            process.energy_delta = process.total_energy - _previous_energy

            # Measured value is in g/kWh, convert to kg/kWs
            _carbon_intensity_kgpws: float = _current_co2_intensity / (60 * 60 * 1e3)

            _previous_emission: float = process.co2_emission

            process.co2_delta = (
                process.power_usage * _carbon_intensity_kgpws * self.cpu_interval
            )

            process.co2_emission += process.co2_delta

            self._logger.debug(
                f"📝 For process '{label}', recorded: CPU={process.cpu_percentage}%, "
                f"Power={process.power_usage}W, CO2={process.co2_emission}{_co2_units}"
            )

    @pydantic.validate_call(config={"arbitrary_types_allowed": True})
    def run(
        self,
        termination_trigger: threading.Event,
        callback: typing.Callable,
        measure_interval: pydantic.PositiveFloat = pydantic.Field(default=10.0, gt=2.0),
        return_all: bool = False,
    ) -> None:
        """Run the API client in a thread.

        Parameters
        ----------
        termination_trigger : threading.Event
            thread event used to terminate monitor
        callback : typing.Callable
            callback to execute on measured results
        measure_interval : float, optional
            interval of measurement, note the API is limited at a rate of 30 requests per
            hour, therefore any interval less than 2 minutes will use the previously recorded CO2 intensity.
            Default is 10 seconds.
        return_all : bool, optional
            whether to return all processes or just the current. Default is False.

        Returns
        -------
        ProcessData | dict[str, ProcessData]
            Either the process data for the current process or for all processes.
        """
        self._logger.info("🧵 Launching monitor in multi-threaded mode.")
        self._logger.info(f"⌚ Will record at interval of {measure_interval}s.")

        def _run(
            monitor: "CO2Monitor" = self,
            callback: typing.Callable = callback,
            return_all: bool = return_all,
        ) -> None:
            if not return_all and not monitor.last_process:
                raise ValueError("No processes attached to monitor.")

            while not termination_trigger.is_set():
                monitor.estimate_co2_emissions()
                # Depending on user choice either
                # return all process data or just the last
                callback(
                    monitor.process_data
                    if return_all
                    else monitor.process_data[monitor.last_process]  # type: ignore
                )
                time.sleep(measure_interval)

        _thread = threading.Thread(target=_run)
        _thread.start()

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
    def total_cpu_percentage(self) -> float:
        return sum(process.cpu_percentage for process in self._processes.values())

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
        return sum(process.energy for process in self._processes.values())
