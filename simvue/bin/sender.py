"""Send locally cached data to server."""

import logging
import pathlib
import click

from simvue.sender import Sender, UPLOAD_ORDER, UploadItem


_logger = logging.getLogger(__name__)
_logger.setLevel(logging.INFO)


@click.command("simvue-sender")
@click.option(
    "--max-workers",
    "-w",
    type=int,
    default=5,
    required=False,
    help="The maximum number of worker threads to use in parallel, by default 5",
)
@click.option(
    "-n",
    "--threading-threshold",
    type=int,
    required=False,
    default=10,
    help="The number of objects of a given type above which items will be sent to the server in parallel, by default 10",
)
@click.option(
    "-o",
    "--objects-to-upload",
    type=str,
    multiple=True,
    required=False,
    default=UPLOAD_ORDER,
    help="The object types to upload, by default All",
)
@click.option(
    "-i",
    "--cache-directory",
    type=click.Path(
        file_okay=False,
        dir_okay=True,
        exists=True,
        writable=True,
        path_type=pathlib.Path,
    ),
    help="Location of cache directory to use",
    default=None,
    required=False,
)
def run(
    cache_directory: pathlib.Path | None,
    objects_to_upload: list[UploadItem] | None,
    threading_threshold: int,
    max_workers: int,
) -> None:
    try:
        _logger.info("Starting Simvue Sender")
        _sender = Sender(
            cache_directory=cache_directory,
            max_workers=max_workers,
            threading_threshold=threading_threshold,
            throw_exceptions=True,
        )
        _sender.upload(objects_to_upload)
    except Exception as err:
        _logger.critical("Exception running sender: %s", str(err))
        raise click.Abort
