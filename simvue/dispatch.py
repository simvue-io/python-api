import logging
import queue
import threading
import time
import typing

MAX_REQUESTS_PER_SECOND: float = 1.0
MAX_BUFFER_SIZE: int = 16000

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class Dispatcher(threading.Thread):
    def __init__(
        self,
        callback: typing.Callable[[list[typing.Any], str, dict[str, typing.Any]], None],
        queue_categories: list[str],
        termination_trigger: threading.Event,
        queue_blocking: bool = False,
        max_buffer_size: int = MAX_BUFFER_SIZE,
        max_read_rate: float = MAX_REQUESTS_PER_SECOND,
        attributes: dict[str, typing.Any] | None = None,
    ) -> None:
        super().__init__()

        self._termination_trigger = termination_trigger
        self._attributes: dict[str, typing.Any] = attributes or {}
        self._callback = callback
        self._queues = {label: queue.Queue() for label in queue_categories}
        self._max_read_rate = max_read_rate
        self._max_buffer_size = max_buffer_size
        self._send_timer = 0
        self._queue_blocking = queue_blocking

    def add_item(self, item: typing.Any, queue_label: str, blocking: bool) -> None:
        if queue_label not in self._queues:
            raise KeyError(f"No queue '{queue_label}' found")
        self._queues[queue_label].put(item, block=blocking)

    @property
    def empty(self) -> bool:
        return all(queue.empty() for queue in self._queues.values())

    @property
    def can_send(self) -> bool:
        if time.time() - self._send_timer >= 1 / self._max_read_rate:
            self._send_timer = time.time()
            return True
        return False

    def _create_buffer(self, queue_label: str) -> list[typing.Any]:
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
        while not self._termination_trigger.is_set():
            time.sleep(0.1)
            if not self.can_send:
                continue

            for queue_label in self._queues:
                if not (_buffer := self._create_buffer(queue_label)):
                    continue
                logger.debug(f"Executing '{queue_label}' callback on buffer {_buffer}")
                self._callback(_buffer, queue_label, self._attributes)
