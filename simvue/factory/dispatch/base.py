import threading
import abc
import typing


class DispatcherBaseClass(abc.ABC):
    def __init__(
        self,
        callback: typing.Callable[[list[typing.Any], str], None],
        object_types: list[str],
        termination_trigger: threading.Event,
        **_,
    ) -> None:
        super().__init__()
        self._object_types: list[str] = object_types
        self._termination_trigger = termination_trigger
        self._callback = callback

    @abc.abstractmethod
    def add_item(self, item: typing.Any, object_type: str, *_, **__) -> None:
        pass

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
