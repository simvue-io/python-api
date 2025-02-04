"""Send runs to server"""

import logging

from simvue.sender import sender, UPLOAD_ORDER
import argparse

_logger = logging.getLogger(__name__)
_logger.setLevel(logging.INFO)


def run() -> None:
    parser = argparse.ArgumentParser(description="My script description")
    parser.add_argument(
        "-w",
        "--max-workers",
        type=int,
        required=False,
        default=5,
        help="The maximum number of worker threads to use in parallel, by default 5",
    )
    parser.add_argument(
        "-n",
        "--threading-threshold",
        type=int,
        required=False,
        default=10,
        help="The number of objects of a given type above which items will be sent to the server in parallel, by default 10",
    )
    parser.add_argument(
        "-o",
        "--objects-to-upload",
        type=str,
        nargs="+",
        required=False,
        default=UPLOAD_ORDER,
        help="The object types to upload, by default All",
    )
    args = parser.parse_args()
    try:
        _logger.info("Starting Simvue Sender")
        sender(**vars(args))
    except Exception as err:
        _logger.critical("Exception running sender: %s", str(err))
