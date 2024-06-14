"""
Geant4 Simvue
=============

Example of repeating simulation of a proton fired at a target of beryllium
monitoring the yield of key particles of interest
"""

import multiparser
import multiparser.parsing.file as mp_file_parse
import simvue
import uproot
import multiprocessing
import typing
import click
import pathlib
import os
import tempfile

from particle import Particle


@click.command
@click.argument("g4_binary", type=click.Path(exists=True))
@click.option("--config", type=click.Path(exists=True), default=None)
@click.option("--ci", is_flag=True, default=False)
@click.option("--momentum", type=float, default=10)
@click.option("--events", type=int, default=100)
def geant4_simvue_example(
    g4_binary: str, config: typing.Optional[str], ci: bool, momentum: float, events: int
) -> None:
    @mp_file_parse.file_parser
    def root_file_parser(
        file_name: str, *_, **__
    ) -> tuple[dict[str, typing.Any], dict[str, typing.Any]]:
        with uproot.open(file_name) as root_data:
            hit_data: dict[str, uproot.TBranch]
            if not (hit_data := root_data.get("Hits")):
                raise RuntimeError("Expected key 'Hits' in ROOT file")

        particles_of_interest = [2212, 211, 11, 22, 2112]

        all_particles = hit_data["fID"].array(library="np").tolist()

        out_data = {
            Particle.from_pdgid(abs(identifier)).name: [
                abs(i) for i in all_particles
            ].count(abs(identifier))
            for identifier in particles_of_interest
        }

        return {}, out_data

    termination_trigger = multiprocessing.Event()

    with simvue.Run() as run:
        run.init(
            "Geant4_simvue_demo",
            folder="/simvue_client_demos",
            tags=[
                "Geant4",
            ],
            description="Geant4 fixed target scenario",
            retention_period="1 hour" if ci else None,
        )

        kwargs: dict[str, typing.Any] = {}

        if config:
            kwargs["script"] = config
        with tempfile.TemporaryDirectory() as tempd:
            with multiparser.FileMonitor(
                per_thread_callback=lambda metrics, *_: run.log_metrics(metrics),
                exception_callback=run.log_event,
                terminate_all_on_fail=False,
                plain_logging=True,
                flatten_data=True,
                termination_trigger=termination_trigger,
            ) as monitor:
                monitor.track(
                    path_glob_exprs=[f'{pathlib.Path(tempd).joinpath("*")}'],
                    parser_func=root_file_parser,
                    static=True,
                )
                monitor.run()

                for i in range(events):
                    if i % 10 == 0:
                        click.secho(
                            f"Running {i+1}/{events} with momentum {momentum} GeV",
                            bold=True,
                            fg="cyan",
                        )
                    running_simulation = multiprocessing.Event()
                    run.add_process(
                        identifier=f"Geant4_simulation_{momentum}GeV_{i}",
                        executable=g4_binary,
                        momentum=momentum,
                        batch=True,
                        output=pathlib.Path(tempd).joinpath(
                            f"output_{momentum}GeV_{i+1}.root"
                        ),
                        completion_trigger=running_simulation
                        if i == events - 1
                        else None,
                        **kwargs,
                    )

                termination_trigger.set()

    for file in pathlib.Path().cwd().glob("Geant4*.err"):
        os.remove(file)

    for file in pathlib.Path().cwd().glob("Geant4*.out"):
        os.remove(file)


if __name__ in "__main__":
    geant4_simvue_example()
