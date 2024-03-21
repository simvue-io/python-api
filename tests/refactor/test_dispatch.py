import pytest
import string
import typing
import time
from threading import Event

from simvue.dispatch import Dispatcher

@pytest.mark.dispatch
@pytest.mark.parametrize(
    "overload_buffer", (True, False)
)
def test_dispatcher(overload_buffer: bool) -> None:
    buffer_size: int = 10
    n_elements: int = buffer_size - 1 if not overload_buffer else 2 * buffer_size
    max_read_rate: float = 0.2
    time_threshold: float = 1 if not overload_buffer else 1 + (1 / max_read_rate)

    start_time = time.time()

    check_dict = {"counter": 0}

    def callback(___: list[typing.Any], _: str, __: dict[str, typing.Any], args=check_dict) -> None:
        check_dict["counter"] += 1

    event = Event()
    dispatcher = Dispatcher(callback, ["lemons"], event, max_buffer_size=buffer_size, max_read_rate=max_read_rate)

    for i in range(n_elements):
        dispatcher.add_item({string.ascii_uppercase[i % 26]: i}, "lemons", False)

    dispatcher.start()

    while not dispatcher.empty:
        time.sleep(0.1)

    event.set()
    assert check_dict["counter"] > 0
    assert time.time() - start_time < time_threshold
