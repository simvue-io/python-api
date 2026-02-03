import threading
import abc
import typing
import pympler.asizeof

MAX_ITEM_SIZE_BYTES: int = 10 * 1024 * 1024


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

    def add_item(self, item: typing.Any, object_type: str, *_, **__) -> None:
        if pympler.asizeof.asizeof(item) > MAX_ITEM_SIZE_BYTES:
            raise AssertionError(
                "Cannot append item to dispatch queue, "
                + f"size exceeds maximum allowance of {MAX_ITEM_SIZE_BYTES // 1024 // 1024}MB"
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
