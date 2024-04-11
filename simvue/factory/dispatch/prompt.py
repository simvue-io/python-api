import threading
import typing

from .base import DispatcherBaseClass


class DirectDispatcher(DispatcherBaseClass):
    """The DirectDispatcher executes the provided callback immediately"""

    def __init__(
        self,
        callback: typing.Callable[[list[typing.Any], str, dict[str, typing.Any]], None],
        object_types: list[str],
        termination_trigger: threading.Event,
        attributes: dict[str, typing.Any] | None = None,
        **_,
    ) -> None:
        """Initialise a new DirectDispatcher instance

        Parameters
        ----------
        callback : typing.Callable[[list[typing.Any], str, dict[str, typing.Any]], None]
            callback to be executed on each item provided
        object_types : list[str]
            categories, this is mainly used for creation of queues in a QueueDispatcher
        termination_trigger : Event
            event which triggers termination of the dispatcher
        attributes : dict[str, typing.Any] | None, optional
            any additional attributes to be provided to the callback, by default None
        """
        super().__init__(
            callback=callback,
            object_types=object_types,
            termination_trigger=termination_trigger,
            attributes=attributes,
        )

    def add_item(self, item: typing.Any, object_type: str) -> None:
        """Execute callback on the given item"""
        self._callback([item], object_type, self._attributes)
