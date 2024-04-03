import threading
import abc
import typing


class DispatcherBaseClass(threading.Thread):
    def __init__(
        self,
        callback: typing.Callable[[list[typing.Any], str, dict[str, typing.Any]], None],
        object_types: list[str],
        termination_trigger: threading.Event,
        attributes: dict[str, typing.Any] | None = None,
        **_,
    ) -> None:
        super().__init__()
        self._object_types: list[str] = object_types
        self._termination_trigger = termination_trigger
        self._attributes: dict[str, typing.Any] = attributes or {}
        self._callback = callback

    @abc.abstractmethod
    def add_item(self, item: typing.Any, object_type: str, *_, **__) -> None:
        pass

    @abc.abstractmethod
    def run(self) -> None:
        pass
