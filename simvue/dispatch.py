"""
Dispatcher
==========

The Dispatcher provides a queue based system for execution of a callback on
a list of parameters. The purpose of the class is to apply constraints to how
often the callback can be executed, and the number of items it is called on.
"""

import logging
import queue
import threading
import time
import typing
import contextlib

MAX_REQUESTS_PER_SECOND: float = 1.0
MAX_BUFFER_SIZE: int = 16000
QUEUE_SIZE = 10000

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class Dispatcher(threading.Thread):
    """
    The Dispatcher class enforces a maximum rate of execution for a given function
    on items within a queue. Multiple queues can be defined with the dispatch
    of each being executed in series. Items are added to a buffer which is handed
    to the callback.
    """

    def __init__(
        self,
        callback: typing.Callable[[list[typing.Any], str], None],
        queue_categories: list[str],
        termination_trigger: threading.Event,
        notify_on_completion: typing.Optional[threading.Event] = None,
        queue_blocking: bool = False,
        max_buffer_size: int = MAX_BUFFER_SIZE,
        max_read_rate: float = MAX_REQUESTS_PER_SECOND,
    ) -> None:
        """
        Initialise a new dispatcher

        Parameters
        ----------
        callback : Callable[[list[Any], str, dict[str, Any]], None]
            function to execute on queued items
        queue_categories : list[str]
            labels for each queue
        queue_blocking : bool
            whether to block queues during object to queue assignment.
            Default is False.
        termination_trigger : threading.Event
            a threading event which when set declares that the dispatcher
            should terminate
        notify_on_completion : threading.Event
            if provided, this event is set by the dispatcher when the shutdown
            trigger has been set and the dispatcher has emptied all queues
        max_buffer_size : int
            maximum number of items allowed in created buffer.
        max_read_rate : float
            maximum rate at which the callback can be executed
        """
        super().__init__()

        self._termination_trigger = termination_trigger
        self._dispatch_complete = notify_on_completion
        self._callback = callback
        self._queues = {label: queue.Queue() for label in queue_categories}
        self._max_read_rate = max_read_rate
        self._max_buffer_size = max_buffer_size
        self._send_timer = 0
        self._queue_blocking = queue_blocking  # Does nothing

    def add_item(self, item: typing.Any, queue_label: str, blocking: bool) -> None:
        """Add an item to the specified queue with/without blocking"""
        if self._termination_trigger.is_set():
            raise RuntimeError(
                f"Cannot append item '{item}' to queue '{queue_label}', "
                "termination called."
            )
        if queue_label not in self._queues:
            raise KeyError(f"No queue '{queue_label}' found")
        self._queues[queue_label].put(item, block=blocking)

    @property
    def empty(self) -> bool:
        """Returns if all queues are empty"""
        return all(queue.empty() for queue in self._queues.values())

    def purge(self) -> None:
        """Purge all queues"""
        for q in self._queues.values():
            with contextlib.suppress(queue.Empty):
                q.get(block=False)
            q.task_done()

    @property
    def _can_send(self) -> bool:
        """Returns if time constraints are satisfied, hence the callback can be executed"""
        return time.time() - self._send_timer >= 1 / self._max_read_rate

    def _create_buffer(self, queue_label: str) -> list[typing.Any]:
        """Assemble queue items into a list as an argument to the callback

        The length of the buffer is constrained.
        """
        _buffer: list[typing.Any] = []

        while (
            not self._queues[queue_label].empty()
            and len(_buffer) < self._max_buffer_size
        ):
            _item = self._queues[queue_label].get(block=False)
            _buffer.append(_item)
            self._queues[queue_label].task_done()

        return _buffer

    def run(self) -> None:
        """Execute the dispatcher action

        The action consists of a loop in which each queue is processed to
        create a buffer with number of entries equal or less than the maximum
        size. These are then passed into the assigned callback.

        Depending on whether the user has specified to abort on trigger either
        the loop will continue after termination until all queues are empty,
        or abort immediately.
        """
        while not self._termination_trigger.is_set() or not self.empty:
            time.sleep(0.1)
            if not self._can_send:
                continue

            for queue_label in self._queues:
                if _buffer := self._create_buffer(queue_label):
                    logger.debug(
                        f"Executing '{queue_label}' callback on buffer {_buffer}"
                    )
                    self._callback(_buffer, queue_label)
            self._send_timer = time.time()
        if self._dispatch_complete:
            self._dispatch_complete.set()
