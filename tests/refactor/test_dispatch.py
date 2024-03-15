import pytest
import string
import typing
import time
from threading import Event

from simvue.dispatch import Dispatcher

@pytest.mark.dispatch
def test_dispatcher() -> None:
    check_dict = {"counter": 0}

    def callback(buffer: list[typing.Any], _: str, __: dict[str, typing.Any], args=check_dict) -> None:
        check_dict["counter"] += 1

    event = Event()
    dispatcher = Dispatcher(callback, ["lemons"], event, max_buffer_size=10)

    for i in range(12):
        dispatcher.add_item({string.ascii_uppercase[i]: i}, "lemons", False)

    dispatcher.start()

    while not dispatcher.empty:
        time.sleep(1)

    event.set()
    assert check_dict["counter"] > 0