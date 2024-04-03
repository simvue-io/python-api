import threading
import typing

from .base import DispatcherBaseClass


class PromptDispatcher(DispatcherBaseClass):
    def __init__(
        self,
        callback: typing.Callable[[list[typing.Any], str, dict[str, typing.Any]], None],
        object_types: list[str],
        termination_trigger: threading.Event,
        attributes: dict[str, typing.Any] | None = None,
        **_,
    ) -> None:
        super().__init__(
            callback=callback,
            object_types=object_types,
            termination_trigger=termination_trigger,
            attributes=attributes,
        )

    def add_item(self, item: typing.Any, object_type: str) -> None:
        self._callback([item], object_type, self._attributes)
