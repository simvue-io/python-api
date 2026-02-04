import threading
import abc
import typing

from simvue.exception import ObjectDispatchError


class DispatcherBaseClass(abc.ABC):
    def __init__(
        self,
        *,
        callback: typing.Callable[[list[typing.Any], str], None],
        object_types: list[str],
        termination_trigger: threading.Event,
        thresholds: dict[str, int | float] | None = None,
    ) -> None:
        super().__init__()
        self._thresholds: dict[str, int | float] = thresholds or {}
        self._object_types: list[str] = object_types
        self._termination_trigger = termination_trigger
        self._callback = callback

    def add_item(
        self,
        item: typing.Any,
        object_type: str,
        metadata: dict[str, int | float] | None = None,
        *_,
        **__,
    ) -> None:
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
        pass

    @abc.abstractmethod
    def start(self) -> None:
        pass

    @abc.abstractmethod
    def join(self) -> None:
        pass

    @abc.abstractmethod
    def purge(self) -> None:
        pass

    @abc.abstractmethod
    def is_alive(self) -> bool:
        pass

    @property
    @abc.abstractmethod
    def empty(self) -> bool:
        pass
