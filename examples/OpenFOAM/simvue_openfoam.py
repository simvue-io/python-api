"""
OpenFOAM v10 Simvue Example

This Simvue example launches the MovingCone example within the OpenFoam10 tutorials.

The contents of the log.PimpleFoam file are parsed using multiparser.

To run this example within an OpenFOAM 10 Docker container
ensure you have either a Simvue config file or you have
set the values for SIMVUE_TOKEN and SIMVUE_URL and run:

python simvue_openfoam.py /opt/openfoam10/tutorials/incompressible/pimpleFoam/laminar/movingCone/Allrun

"""

import os
import re
import click
import uuid
import simvue
import multiprocessing
import multiparser
import multiparser.parsing.tail as mp_tail_parse

from typing import Any


@click.command
@click.argument("all_run_script", type=click.Path(exists=True))
@click.option("--ci", is_flag=True, default=False)
def open_foam_simvue_demo(all_run_script: str, ci: bool) -> None:
    """Run the Allrun file for the given simulation and parse the log.PimpleFoam content

    Parameters
    ----------
    all_run_script : str
        path of the Allrun execution script
    """
    # Regular expressions

    uniq_id: str = f"{uuid.uuid4()}".split("-")[0]

    @mp_tail_parse.log_parser
    def custom_parser(file_content: str, **_) -> tuple[dict[str, Any], dict[str, Any]]:
        exp1: re.Pattern[str] = re.compile(
            "^(.+):  Solving for (.+), Initial residual = (.+), Final residual = (.+), No Iterations (.+)$"
        )
        exp2: re.Pattern[str] = re.compile("^ExecutionTime = ([0-9.]+) s")
        metrics = {}

        for line in file_content.splitlines():
            # Get time
            match = exp2.match(line)
            if match:
                ttime = match.group(1)
                if metrics:
                    run.log_metrics(metrics, time=ttime)
                    metrics = {}

            # Get metrics
            match = exp1.match(line)
            if match:
                metrics["residuals.initial.%s" % match.group(2)] = match.group(3)
                metrics["residuals.final.%s" % match.group(2)] = match.group(4)
        return {}, metrics

    log_location: str = os.path.dirname(all_run_script)
    termination_trigger = multiprocessing.Event()

    with simvue.Run() as run:
        run.init(
            f"open_foam_demo_{uniq_id}",
            folder="/simvue_client_demos",
            tags=["OpenFOAM", "simvue_client_examples"],
            retention_period="1 hour" if ci else None,
            visibility="tenant" if ci else None,
        )
        run.add_process(
            identifier="OpenFOAM",
            executable="/bin/sh",
            script=all_run_script,
            completion_callback=lambda *_, **__: termination_trigger.set(),
        )
        with multiparser.FileMonitor(
            per_thread_callback=lambda metrics: run.log_metrics(metrics),
            exception_callback=run.log_event,
            terminate_all_on_fail=True,
            plain_logging=True,
            flatten_data=True,
            interval=0.1,
            termination_trigger=termination_trigger,
        ) as monitor:
            monitor.tail(
                parser_func=custom_parser,
                path_glob_exprs=[os.path.join(log_location, "log.pimpleFoam")],
            )


if __name__ in "__main__":
    open_foam_simvue_demo()
