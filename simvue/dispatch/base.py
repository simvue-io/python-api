import threading
import abc
import typing

from simvue.exception import ObjectDispatchError


class DispatcherBaseClass(abc.ABC):
    """Base class to all dispatchers.

    A dispatcher is an object which sends data to a location,
    in this case it executes a callback based on criteria.
    """

    def __init__(
        self,
        *,
        callback: typing.Callable[[list[typing.Any], str], None],
        object_types: list[str],
        termination_trigger: threading.Event,
        thresholds: dict[str, int | float] | None = None,
    ) -> None:
        """Initialise a dispatcher.

        Parameters
        ----------
        callback : Callable[[list[Any]], str] | None
            callback to execute on data.
        object_types : list[str]
            categories of items for separate handling
        termination_trigger : Event
            trigger for closing this dispatcher
        thresholds : dict[str, int | float] | None, optional
            any additional thresholds to consider when handling items.
            This assumes metadata defining the values to compare to
            such thresholds is included when appending.
        """
        super().__init__()
        self._thresholds: dict[str, int | float] = thresholds or {}
        self._object_types: list[str] = object_types
        self._termination_trigger = termination_trigger
        self._callback = callback

    def add_item(
        self,
        item: typing.Any,
        *,
        object_type: str,
        metadata: dict[str, int | float] | None = None,
        **__,
    ) -> None:
        """Add an item to the dispatcher.

        Parameters
        ----------
        item : Any
            item to add to dispatch
        object_type : str
            category of item
        metadata : dict[str, int | float] | None, optional
            additional metadata relating to the item to be
            used for threshold comparisons
        """
        _ = item
        _ = object_type
        if not metadata:
            return
        for key, threshold in self._thresholds.items():
            if key in metadata and metadata[key] > threshold:
                raise ObjectDispatchError(
                    label=key, threshold=threshold, value=metadata[key]
                )

    @abc.abstractmethod
    def run(self) -> None:
        """Start the dispatcher."""
        pass

    @abc.abstractmethod
    def start(self) -> None:
        """Not used, this allows the class to be similar to a thread."""
        pass

    @abc.abstractmethod
    def join(self) -> None:
        """Not used, this allows the class to be similar to a thread."""
        pass

    @abc.abstractmethod
    def purge(self) -> None:
        """Clear the dispatcher of items."""
        pass

    @abc.abstractmethod
    def is_alive(self) -> bool:
        """Whether the dispatcher is operating correctly."""
        pass

    @property
    @abc.abstractmethod
    def empty(self) -> bool:
        """Whether the dispatcher is empty."""
        pass
