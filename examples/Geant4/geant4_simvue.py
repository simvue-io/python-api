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
    g4_binary: str, config: str | None, ci: bool, momentum: float, events: int
) -> None:
    
    def root_file_parser(
        input_file: str, *_, **__
    ) -> tuple[dict[str, typing.Any], dict[str, typing.Any]]:
        """
        This function will parse the ROOT file which Geant4 produces as an output,
        and format the data as a dictionary of key/value pairs for upload as metrics.
        """
        with uproot.open(input_file) as root_data:
            hit_data: dict[str, uproot.TBranch]
            if not (hit_data := root_data.get("Hits")):
                raise RuntimeError("Expected key 'Hits' in ROOT file")

            particles_of_interest = [2212, 211, 11, 22, 2112]

            all_particles = hit_data["fID"].array(library="np").tolist()

            out_data = {
                Particle.from_pdgid(abs(identifier))
                .name.replace("+", "plus")
                .replace("-", "minus"): [abs(i) for i in all_particles].count(
                    abs(identifier)
                )
                for identifier in particles_of_interest
            }

        return out_data
    
    # Use the Simvue Run as a context manager
    with simvue.Run() as run:
        # Initialize a single run for all simulations we are tracking
        run.init(
            "Geant4_simvue_demo",
            folder="/simvue_client_demos",
            tags=[
                "Geant4",
            ],
            description="Geant4 fixed target scenario",
            retention_period="1 hour" if ci else None,
            visibility="tenant" if ci else None,
        )

        kwargs: dict[str, typing.Any] = {}
        if config:
            kwargs["script"] = config

        for i in range(events):
            # Create new multiprocessing Trigger which will register when the simulation is complete
            _trigger = multiprocessing.Event()
            
            if i % 10 == 0:
                click.secho(
                    f"Running {i+1}/{events} with momentum {momentum} GeV",
                    bold=True,
                    fg="cyan",
                )
            _output_file_path = pathlib.Path.cwd().joinpath(
                    f"Geant4_simvue_output_{momentum}GeV_{i+1}.root"
                )
            # Add the Geant4 simulation as a process, passing in command line arguments as extra kwargs
            # Also set the completion_trigger to our trigger, so that it is set once the sim is complete
            run.add_process(
                identifier=f"Geant4_simulation_{momentum}GeV_{i}",
                executable=g4_binary,
                momentum=momentum,
                batch=True,
                output=_output_file_path,
                completion_trigger=_trigger,
                **kwargs,
            )
            # Wait until simulation completes
            _trigger.wait()
            
            # Upload the parsed results from the ROOT file as metrics, and upload the ROOT file as an output
            run.log_metrics(root_file_parser(str(_output_file_path)))
            run.save_file(_output_file_path, category="output")

    # Delete any results files since these are now uploaded to Simvue!
    for file in pathlib.Path().cwd().glob("Geant4_simvue_*"):
        file.unlink()

if __name__ in "__main__":
    geant4_simvue_example()
