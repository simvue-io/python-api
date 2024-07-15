import os.path
import os
import logging
import datetime
import argparse
import multiprocessing
import click

from multiparser import FileMonitor
import multiparser.parsing.tail as mp_tail_parse
from simvue import Run


@click.command
@click.argument("input_file")
@click.argument("tracking_directory")
@click.option("--ci", default=False)
def run_fds_example(input_file: str, tracking_directory: str, ci: bool) -> None:
    logging.getLogger().setLevel(logging.DEBUG)
    parser = argparse.ArgumentParser()
    parser.add_argument("input_file")
    parser.add_argument("tracking_dir")
    args = parser.parse_args()

    _trigger = multiprocessing.Event()

    with Run() as run:

        def debug_callback(data, meta, run_instance: Run = run):
            data = {k.strip(): v.strip() for k, v in data.items()}
            out_data = {}
            if "Value" not in data:
                return

            key = data["ID"].replace(" ", "_").strip()
            value = float(data["Value"])
            time = datetime.datetime.fromtimestamp(float(data["Time (s)"])).strftime(
                "%Y-%m-%d %H:%M:%S.%f"
            )
            out_data[key] = value

            print(f"Recorded: {out_data}\n{meta}")
            run_instance.log_metrics(out_data, timestamp=time)

        def meta_update(data, meta, run_instance: Run = run):
            print(f"Received '{meta}'\n\n'{data}'")
            run_instance.update_metadata(metadata={k: v for k, v in data.items() if v})

        run.init(
            "fire_simulator_demo",
            folder="/simvue_client_demos",
            tags=["FDS"],
            description="Vent activation demo in FDS",
            retention_period="1 hour" if ci else None,
            visibility="tenant" if ci else None,
        )

        run.add_process(
            "simulation",
            executable="fds_unlim",
            ulimit="unlimited",
            input_file=f"{args.input_file}",
            completion_trigger=_trigger,
            print_stdout=True,
            env=os.environ
            | {"PATH": f"{os.environ['PATH']}:{os.path.dirname(__file__)}"},
        )

        with FileMonitor(
            per_thread_callback=debug_callback,
            exception_callback=run.log_event,
            interval=1,
            log_level=logging.DEBUG,
            flatten_data=True,
            plain_logging=True,
            termination_trigger=_trigger,
        ) as monitor:
            monitor.track(
                path_glob_exprs=args.input_file,
                callback=meta_update,
                file_type="fortran",
                static=True,
            )
            monitor.tail(
                path_glob_exprs=os.path.join(args.tracking_dir, "*_devc*.csv"),
                parser_func=mp_tail_parse.record_csv,
                parser_kwargs={"header_pattern": "Time"},
            )
            monitor.run()


if __name__ in "__main__":
    run_fds_example()
