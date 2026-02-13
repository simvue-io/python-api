"""Simvue logging handler."""

import logging
import typing

if typing.TYPE_CHECKING:
    from simvue import Run

try:
    from typing import override
except ImportError:
    from typing_extensions import override


class Handler(logging.Handler):
    """Class for handling logging as events to a Simvue server."""

    def __init__(self, simvue_run: "Run") -> None:
        """Initialise a new Simvue logging handler.

        Parameters
        ----------
        simvue_run: simvue.Run
            run to attach this handler to
        """
        logging.Handler.__init__(self)
        self._run_object: Run = simvue_run

    @override
    def emit(self, record: logging.LogRecord) -> None:
        """Perform the logging action of sending to server."""
        if "simvue." in record.name:
            return

        _msg: str = self.format(record)

        try:
            self._run_object.log_event(_msg)
        except Exception:
            logging.Handler.handleError(self, record)

    @override
    def close(self) -> None:
        """Execute nothing on closure."""
