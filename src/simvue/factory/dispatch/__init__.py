"""
Dispatch
========

Contains factory method for selecting dispatcher type based on Simvue Configuration
"""

import typing
import logging

if typing.TYPE_CHECKING:
    from .base import DispatcherBaseClass
    from threading import Event

from .queued import QueuedDispatcher
from .direct import DirectDispatcher

logger = logging.getLogger(__name__)


def Dispatcher(
    mode: typing.Literal["direct", "queued"],
    callback: typing.Callable[[list[typing.Any], str, dict[str, typing.Any]], None],
    object_types: list[str],
    termination_trigger: "Event",
    name: str | None = None,
    **kwargs,
) -> "DispatcherBaseClass":
    """Returns instance of dispatcher based on configuration

    Options are 'queued' which is the default and adds objects to a queue as well
    as restricts the rate of dispatch, and 'prompt' which executes the callback
    immediately

    Parameters
    ----------
    mode : typing.Literal['prompt', 'queued']
        dispatcher mode
            * prompt - execute callback immediately, do not queue.
            * queue - execute callback on entries in a queue.
    callback : typing.Callable[[list[typing.Any], str, dict[str, typing.Any]], None]
        callback to be executed on each item provided
    object_types : list[str]
        categories, this is mainly used for creation of queues in a QueueDispatcher
    termination_trigger : Event
        event which triggers termination of the dispatcher
    name : str | None, optional
        name for the underlying thread, default None

    Returns
    -------
    DispatcherBaseClass
        either a DirectDispatcher or QueueDispatcher instance
    """
    if mode == "direct":
        logger.debug("Using direct dispatch for metric and queue sending")
        return DirectDispatcher(
            callback=callback,
            object_types=object_types,
            termination_trigger=termination_trigger,
            **kwargs,
        )
    else:
        logger.debug("Using queued dispatch for metric and queue sending")
        return QueuedDispatcher(
            callback=callback,
            object_types=object_types,
            termination_trigger=termination_trigger,
            name=name,
            **kwargs,
        )
