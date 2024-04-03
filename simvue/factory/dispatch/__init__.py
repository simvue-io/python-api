import typing

if typing.TYPE_CHECKING:
    from .base import DispatcherBaseClass
    from threading import Event

from .queued import QueuedDispatcher
from .prompt import PromptDispatcher


def Dispatcher(
    mode: typing.Literal["prompt", "queued"],
    callback: typing.Callable[[list[typing.Any], str, dict[str, typing.Any]], None],
    object_types: list[str],
    termination_trigger: "Event",
    attributes: dict[str, typing.Any] | None = None,
    **kwargs,
) -> "DispatcherBaseClass":
    if mode == "prompt":
        return PromptDispatcher(
            callback=callback,
            object_types=object_types,
            termination_trigger=termination_trigger,
            attributes=attributes,
            **kwargs,
        )
    else:
        return QueuedDispatcher(
            callback=callback,
            object_types=object_types,
            termination_trigger=termination_trigger,
            attributes=attributes,
            **kwargs,
        )
