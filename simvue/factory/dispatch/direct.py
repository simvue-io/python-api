import threading
import typing

from .base import DispatcherBaseClass


class DirectDispatcher(DispatcherBaseClass):
    """The DirectDispatcher executes the provided callback immediately"""

    def __init__(
        self,
        callback: typing.Callable[[list[typing.Any], str], None],
        object_types: list[str],
        termination_trigger: threading.Event,
        **_,
    ) -> None:
        """Initialise a new DirectDispatcher instance

        Parameters
        ----------
        callback : typing.Callable[[list[typing.Any], str], None]
            callback to be executed on each item provided
        object_types : list[str]
            categories, this is mainly used for creation of queues in a QueueDispatcher
        termination_trigger : Event
            event which triggers termination of the dispatcher
        """
        super().__init__(
            callback=callback,
            object_types=object_types,
            termination_trigger=termination_trigger,
        )

    def add_item(self, item: typing.Any, object_type: str, *_, **__) -> None:
        """Execute callback on the given item"""
        self._callback([item], object_type)

    def run(self) -> None:
        """Run does not execute anything in this context"""
        pass

    def start(self) -> None:
        """Start does not execute anything in this context"""
        pass

    def join(self) -> None:
        """Join does not execute anything in this context"""
        pass

    def purge(self) -> None:
        """Purge does not execute anything in this context"""
        pass

    def is_alive(self) -> bool:
        """As unthreaded, state as not alive always"""
        return False

    @property
    def empty(self) -> bool:
        """No queue so always empty"""
        return True
