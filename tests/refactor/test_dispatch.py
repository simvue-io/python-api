import pytest
import string
import typing
import time
import multiprocessing
from threading import Event

from simvue.dispatch import Dispatcher

@pytest.mark.dispatch
@pytest.mark.parametrize(
    "overload_buffer", (True, False),
    ids=("overload", "normal")
)
@pytest.mark.parametrize("multiple", (True, False), ids=("multiple", "single"))
def test_dispatcher(overload_buffer: bool, multiple: bool) -> None:
    buffer_size: int = 10
    n_elements: int = buffer_size - 1 if not overload_buffer else 2 * buffer_size
    max_read_rate: float = 0.2
    time_threshold: float = 1 if not overload_buffer else 1 + (1 / max_read_rate)

    start_time = time.time()

    check_dict = {}

    variables = ["lemons"]

    if multiple:
        variables.append("limes")

    event = Event()
    dispatchers: list[Dispatcher] = []

    for variable in variables:
        check_dict[variable] = {"counter": 0}
        def callback(___: list[typing.Any], _: str, __: dict[str, typing.Any], args=check_dict, var=variable) -> None:
            args[var]["counter"] += 1
        dispatchers.append(
            Dispatcher(callback, [variable], event, max_buffer_size=buffer_size, max_read_rate=max_read_rate)
        )

    for i in range(n_elements):
        for variable, dispatcher in zip(variables, dispatchers):  
            dispatcher.add_item({string.ascii_uppercase[i % 26]: i}, variable, False)

    for dispatcher in dispatchers:
        dispatcher.start()

    while not dispatcher.empty:
        time.sleep(0.1)

    event.set()

    for variable in variables:
        assert check_dict[variable]["counter"] > 0, f"Check of counter for dispatcher '{variable}' failed with {check_dict[variable]['counter']} = {0}"
    assert time.time() - start_time < time_threshold

