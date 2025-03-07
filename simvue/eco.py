import typing
import logging
import datetime

from codecarbon import EmissionsTracker, OfflineEmissionsTracker
from codecarbon.output import BaseOutput as cc_BaseOutput
from simvue.utilities import simvue_timestamp

if typing.TYPE_CHECKING:
    from simvue import Run
    from codecarbon.output_methods.emissions_data import EmissionsData


logger = logging.getLogger(__file__)


class CodeCarbonOutput(cc_BaseOutput):
    def __init__(self, run: "Run") -> None:
        self._simvue_run = run
        self._metrics_step: int = 0

    def out(
        self, total: "EmissionsData", delta: "EmissionsData", meta_update: bool = True
    ) -> None:
        # Check if the run has been shutdown, if so do nothing
        if (
            self._simvue_run._shutdown_event
            and self._simvue_run._shutdown_event.is_set()
        ):
            logger.debug("Terminating CodeCarbon tracker")
            return

        if meta_update:
            logger.debug("Logging CodeCarbon metadata")
            try:
                self._simvue_run.update_metadata(
                    {
                        "sustainability": {
                            "country": total.country_name,
                            "country_iso_code": total.country_iso_code,
                            "region": total.region,
                            "codecarbon_version": total.codecarbon_version,
                        }
                    }
                )
            except AttributeError as e:
                logger.error(f"Failed to update metadata: {e}")
        try:
            _cc_timestamp = datetime.datetime.strptime(
                total.timestamp, "%Y-%m-%dT%H:%M:%S"
            )
        except ValueError as e:
            logger.error(f"Error parsing timestamp: {e}")
            return

        logger.debug("Logging CodeCarbon metrics")
        try:
            self._simvue_run.log_metrics(
                metrics={
                    "sustainability.emissions.total": total.emissions,
                    "sustainability.energy_consumed.total": total.energy_consumed,
                    "sustainability.emissions.delta": delta.emissions,
                    "sustainability.energy_consumed.delta": delta.energy_consumed,
                },
                step=self._metrics_step,
                timestamp=simvue_timestamp(_cc_timestamp),
            )
        except ArithmeticError as e:
            logger.error(f"Failed to log metrics: {e}")
            return

        self._metrics_step += 1

    def live_out(self, total: "EmissionsData", delta: "EmissionsData") -> None:
        self.out(total, delta, meta_update=False)


class SimvueEmissionsTracker(EmissionsTracker):
    def __init__(
        self, project_name: str, simvue_run: "Run", metrics_interval: int
    ) -> None:
        self._simvue_run = simvue_run
        logger.setLevel(logging.ERROR)
        super().__init__(
            project_name=project_name,
            measure_power_secs=metrics_interval,
            api_call_interval=1,
            experiment_id=None,
            experiment_name=None,
            logging_logger=CodeCarbonOutput(simvue_run),
            save_to_logger=True,
            allow_multiple_runs=True,
            log_level="error",
        )

    def set_measure_interval(self, interval: int) -> None:
        """Set the measure interval"""
        self._set_from_conf(interval, "measure_power_secs")

    def post_init(self) -> None:
        self._set_from_conf(self._simvue_run._id, "experiment_id")
        self._set_from_conf(self._simvue_run._name, "experiment_name")
        self.start()


class OfflineSimvueEmissionsTracker(OfflineEmissionsTracker):
    def __init__(
        self, project_name: str, simvue_run: "Run", metrics_interval: int
    ) -> None:
        self._simvue_run = simvue_run
        logger.setLevel(logging.ERROR)
        super().__init__(
            country_iso_code=simvue_run._user_config.offline.country_iso_code,
            project_name=project_name,
            measure_power_secs=metrics_interval,
            api_call_interval=1,
            experiment_id=None,
            experiment_name=None,
            logging_logger=CodeCarbonOutput(simvue_run),
            save_to_logger=True,
            allow_multiple_runs=True,
            log_level="error",
        )

    def set_measure_interval(self, interval: int) -> None:
        """Set the measure interval"""
        self._set_from_conf(interval, "measure_power_secs")

    def post_init(self) -> None:
        self._set_from_conf(self._simvue_run._id, "experiment_id")
        self._set_from_conf(self._simvue_run._name, "experiment_name")
        self.start()
