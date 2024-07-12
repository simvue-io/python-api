import os
import multiprocessing
import click
import multiparser
import requests

import multiparser.parsing.tail as mp_tail_parse
import multiparser.parsing.file as mp_file_parse

from typing import Any

import simvue


@click.command
@click.argument("su2_binary_directory", type=click.Path(exists=True))
@click.option("--config", help="URL or path of config file", default=None)
@click.option("--mesh", help="URL or path of mesh file", default=None)
@click.option("--ci", is_flag=True, default=False)
def run_su2_example(
    su2_binary_directory: str, config: str | None, mesh: str | None, ci: bool
) -> None:
    # Name of history file to collect metrics from
    HISTORY: str = "history.csv"

    config_url = (
        config
        or "https://raw.githubusercontent.com/su2code/Tutorials/master/compressible_flow/Inviscid_ONERAM6/inv_ONERAM6.cfg"
    )

    mesh_url = (
        mesh
        or "https://raw.githubusercontent.com/su2code/Tutorials/master/compressible_flow/Inviscid_ONERAM6/mesh_ONERAM6_inv_ffd.su2"
    )

    config_filename: str = (
        os.path.basename(config_url) if "http" in config_url else config_url
    )
    mesh_filename: str = os.path.basename(mesh_url) if "http" in mesh_url else mesh_url

    for url, file_name in zip((config_url, mesh_url), (config_filename, mesh_filename)):
        if "http" not in url:
            continue

        req_response = requests.get(url)

        if req_response.status_code != 200:
            raise RuntimeError(f"Failed to retrieve file '{url}'")

        with open(file_name, "wb") as out_f:
            out_f.write(req_response.content)

    # Store these output files
    OUTPUT_FILES: list[str] = ["flow.vtk", "surface_flow.vtk", "restart_flow.dat"]

    for file_name in OUTPUT_FILES + [HISTORY]:
        if os.path.exists(file_name):
            os.remove(file_name)

    # Collect these metadata attributes from the config file
    METADATA_ATTRS: list[str] = [
        "SOLVER",
        "MATH_PROBLEM",
        "MACH_NUMBER",
        "AOA",
        "SIDESLIP_ANGLE",
        "FREESTREAM_PRESSURE",
        "FREESTREAM_TEMPERATURE",
    ]

    @mp_file_parse.file_parser
    def metadata_parser(file_name: str, **_) -> tuple[dict[str, Any], dict[str, Any]]:
        metadata = {}
        with open(file_name) as in_csv:
            file_content = in_csv.read()

        for line in file_content.splitlines():
            for attr in METADATA_ATTRS:
                if line.startswith(attr):
                    metadata[attr] = line.split("%s= " % attr)[1].strip()
        return {}, metadata

    termination_trigger = multiprocessing.Event()

    environment: dict[str, str] = os.environ.copy()
    environment["PATH"] = (
        f"{os.path.abspath(su2_binary_directory)}:{os.environ['PATH']}"
    )
    environment["PYTHONPATH"] = (
        f"{os.path.abspath(su2_binary_directory)}{f':{pypath}' if (pypath := os.environ.get('PYTHONPATH')) else ''}"
    )

    with simvue.Run() as run:
        run.init(
            "SU2_simvue_demo",
            folder="/simvue_client_demos",
            tags=[
                "SU2",
                os.path.splitext(os.path.basename(config_filename))[0],
                os.path.splitext(os.path.basename(mesh_filename))[0],
                "simvue_client_examples",
            ],
            description="SU2 tutorial https://su2code.github.io/tutorials/Inviscid_ONERAM6/",
            retention_period="1 hour" if ci else None,
            visibility="tenant" if ci else None,
        )
        run.add_process(
            identifier="SU2_simulation",
            executable="SU2_CFD",
            script=config_filename,
            env=environment,
            completion_callback=lambda *_, **__: termination_trigger.set()
        )
        with multiparser.FileMonitor(
            # Metrics cannot have square brackets in their names so we remove
            # these before passing them to log_metrics
            per_thread_callback=lambda metrics, *_: run.log_metrics(
                {
                    key.replace("[", "_").replace("]", ""): value
                    for key, value in metrics.items()
                }
            ),
            exception_callback=run.log_event,
            terminate_all_on_fail=True,
            plain_logging=True,
            flatten_data=True,
            termination_trigger=termination_trigger,
        ) as monitor:
            monitor.track(
                path_glob_exprs=[config_filename],
                parser_func=metadata_parser,
                callback=lambda meta, *_: run.update_metadata(meta),
                static=True,
            )
            monitor.tail(
                path_glob_exprs=[HISTORY],
                parser_func=mp_tail_parse.record_csv,
            )
            monitor.track(
                path_glob_exprs=OUTPUT_FILES,
                callback=lambda *_, meta: run.save_file(meta["file_name"], "output"),
                parser_func=lambda *_, **__: ({}, {}),
            )
            monitor.run()


if __name__ == "__main__":
    run_su2_example()
