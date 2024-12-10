import typing
import logging
import datetime

from codecarbon import EmissionsTracker
from codecarbon.output_methods.base_output import BaseOutput as cc_BaseOutput
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
            self._simvue_run.update_metadata(
                {
                    "codecarbon.country": total.country_name,
                    "codecarbon.country_iso_code": total.country_iso_code,
                    "codecarbon.region": total.region,
                    "codecarbon.version": total.codecarbon_version,
                }
            )

        _cc_timestamp: datetime.datetime = datetime.datetime.strptime(
            total.timestamp, "%Y-%m-%dT%H:%M:%S"
        )

        logger.debug("Logging CodeCarbon metrics")
        self._simvue_run.log_metrics(
            metrics={
                "codecarbon.total.emissions": total.emissions,
                "codecarbon.total.energy_consumed": total.energy_consumed,
                "codecarbon.delta.emissions": delta.emissions,
                "codecarbon.delta.energy_consumed": delta.energy_consumed,
            },
            step=self._metrics_step,
            timestamp=simvue_timestamp(_cc_timestamp),
        )
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
