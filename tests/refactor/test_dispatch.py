import pytest
import string
import typing
import time
from threading import Event, Thread

from simvue.dispatch import Dispatcher

# FIXME: Update the layout of these tests

@pytest.mark.dispatch
@pytest.mark.parametrize(
    "overload_buffer", (True, False),
    ids=("overload", "normal")
)
@pytest.mark.parametrize(
    "append_during_dispatch", (True, False),
    ids=("pre_append", "append")
)
@pytest.mark.parametrize("multiple", (True, False), ids=("multiple", "single"))
def test_dispatcher(overload_buffer: bool, multiple: bool, append_during_dispatch: bool) -> None:
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

    if not append_during_dispatch:
        for i in range(n_elements):
            for variable, dispatcher in zip(variables, dispatchers):  
                dispatcher.add_item({string.ascii_uppercase[i % 26]: i}, variable, False)

    for dispatcher in dispatchers:
        dispatcher.start()

    if append_during_dispatch:
        for i in range(n_elements):
            for variable, dispatcher in zip(variables, dispatchers):  
                dispatcher.add_item({string.ascii_uppercase[i % 26]: i}, variable, False)

    while not dispatcher.empty:
        time.sleep(0.1)

    event.set()

    for variable in variables:
        assert check_dict[variable]["counter"] >= 2 if overload_buffer else 1, f"Check of counter for dispatcher '{variable}' failed with {check_dict[variable]['counter']} = {0}"
    assert time.time() - start_time < time_threshold


@pytest.mark.dispatch
@pytest.mark.parametrize("multi_queue", (True, False))
def test_nested_dispatch(multi_queue: bool) -> None:
    check_dict = [{"counter": 0} for _ in range(10)]
    buffer_size: int = 10
    n_elements: int = 2 * buffer_size
    max_read_rate: float = 0.2
    variable: str | list[str] = "demo" if not multi_queue else ["events", "metrics"]

    event = Event()
    def callback(___: list[typing.Any], _: str, attributes: dict[str, typing.Any], check_dict=check_dict) -> None:
        check_dict[attributes["index"]]["counter"] += 1
    def _main(index, dispatch_callback=callback, term_event=event, variable=variable) -> None:
        dispatcher = Dispatcher(
            dispatch_callback,
            [variable] if isinstance(variable, str) else variable,
            term_event,
            max_buffer_size=buffer_size,
            max_read_rate=max_read_rate,
            attributes={"index": index}
        )

        dispatcher.start()

        for i in range(n_elements):
            if isinstance(variable, str):
                dispatcher.add_item({string.ascii_uppercase[i % 26]: i}, variable, False)
            else:
                for var in variable:
                    dispatcher.add_item({string.ascii_uppercase[i % 26]: i}, var, False)

        while not dispatcher.empty:
            time.sleep(0.1)

        term_event.set()

    threads = []

    for i in range(10):
        _thread = Thread(target=_main, args=(i,))
        _thread.start()
        threads.append(_thread)
    
    for thread in threads:
        thread.join()

        assert check_dict[i]["counter"] >= 2, f"Check of counter for dispatcher '{variable}' failed with {check_dict[i]['counter']} = {0}"
