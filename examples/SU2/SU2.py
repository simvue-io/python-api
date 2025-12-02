import os
import click
import requests

from typing import Any

import multiparser.parsing.tail as mp_tail_parse
import multiparser.parsing.file as mp_file_parse

from simvue_integrations.connectors.generic import WrappedRun

# # Create a custom class which inherits from WrappedRun:
class SU2Run(WrappedRun):
    # Store these output files
    output_files: list[str] = ["flow.vtk", "surface_flow.vtk", "restart_flow.dat"]

    # Collect these metadata attributes from the config file
    metadata_attrs: list[str] = [
        "SOLVER",
        "MATH_PROBLEM",
        "MACH_NUMBER",
        "AOA",
        "SIDESLIP_ANGLE",
        "FREESTREAM_PRESSURE",
        "FREESTREAM_TEMPERATURE",
    ]
    
    @mp_file_parse.file_parser
    def metadata_parser(self, input_file: str, **_) -> tuple[dict[str, Any], dict[str, Any]]:
        metadata = {"SU2": {}}
        with open(input_file) as in_csv:
            file_content = in_csv.read()

        for line in file_content.splitlines():
            for attr in self.metadata_attrs:
                if line.startswith(attr):
                    metadata["SU2"][attr.lower()] = line.split("%s= " % attr)[1].strip()
        return {}, metadata
    
    def _pre_simulation(self):
        super()._pre_simulation()
        
        environment: dict[str, str] = os.environ.copy()
        environment["PATH"] = (
            f"{os.path.abspath(self.su2_binary_directory)}:{os.environ['PATH']}"
        )
        environment["PYTHONPATH"] = (
            f"{os.path.abspath(self.su2_binary_directory)}{f':{pypath}' if (pypath := os.environ.get('PYTHONPATH')) else ''}"
        )
        
        self.add_process(
            identifier="SU2_simulation",
            executable="SU2_CFD",
            script=self.config_filename,
            env=environment,
            completion_trigger=self._trigger,
        )
        
    def _during_simulation(self):
        self.file_monitor.track(
            path_glob_exprs=self.config_filename,
            parser_func=self.metadata_parser,
            callback=lambda meta, *_: self.update_metadata(meta),
            static=True,
        )
        self.file_monitor.tail(
            path_glob_exprs=["history.csv"],
            parser_func=mp_tail_parse.record_csv,
            callback=lambda metrics, *_: self.log_metrics(
                {
                    key.replace("[", "_").replace("]", ""): value
                    for key, value in metrics.items()
                }
            
            ))
        
    def _post_simulation(self):        
        for file in self.output_files:
            if os.path.exists(file):
                self.save_file(file, "output")
                
        super()._post_simulation()
        
        
    def launch(self, su2_binary_directory: str, config_filename: str):
        self.su2_binary_directory = su2_binary_directory
        self.config_filename = config_filename
        super().launch()


@click.command
@click.argument("su2_binary_directory", type=click.Path(exists=True))
@click.option("--config", help="URL or path of config file", default=None)
@click.option("--mesh", help="URL or path of mesh file", default=None)
@click.option("--ci", is_flag=True, default=False)
def run_su2_example(
    su2_binary_directory: str, config: str | None, mesh: str | None, ci: bool
) -> None:
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

    # Use your custom class as a context manager in the same way you'd use a Simvue Run
    with SU2Run() as run:
        
        # Delete any previous results files
        for file_name in run.output_files + ["history.csv"]:
            if os.path.exists(file_name):
                os.remove(file_name)
            
        # Since WrappedRun inherits from Simvue Run, you have access to all normal methods
        
        # Start by initialising the run    
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
        
        # Then run your custom 'launch' method, which will run each of the internal methods you created
        run.launch(su2_binary_directory, config_filename)

if __name__ == "__main__":
    run_su2_example()
