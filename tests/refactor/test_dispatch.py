import pytest
import string
import typing
import time
from threading import Event, Thread
from queue import Queue


from simvue.factory.dispatch.queued import QueuedDispatcher

from simvue.factory.dispatch.prompt import PromptDispatcher

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
def test_queued_dispatcher(overload_buffer: bool, multiple: bool, append_during_dispatch: bool) -> None:
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
    dispatchers: list[QueuedDispatcher] = []

    for variable in variables:
        check_dict[variable] = {"counter": 0}
        def callback(___: list[typing.Any], _: str, __: dict[str, typing.Any], args=check_dict, var=variable) -> None:
            args[var]["counter"] += 1
        dispatchers.append(
            QueuedDispatcher(callback, [variable], event, max_buffer_size=buffer_size, max_read_rate=max_read_rate)
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

    dispatcher.join()

    for variable in variables:
        assert check_dict[variable]["counter"] >= 2 if overload_buffer else 1, f"Check of counter for dispatcher '{variable}' failed with count = {check_dict[variable]['counter']}"
    assert time.time() - start_time < time_threshold


@pytest.mark.dispatch
@pytest.mark.parametrize("multi_queue", (True, False))
def test_nested_queued_dispatch(multi_queue: bool) -> None:
    check_dict = [{"counter": 0} for _ in range(10)]
    buffer_size: int = 10
    n_elements: int = 2 * buffer_size
    max_read_rate: float = 0.2
    variable: str | list[str] = "demo" if not multi_queue else ["events", "metrics"]

    result_queue = Queue()

    event = Event()
    def callback(___: list[typing.Any], _: str, attributes: dict[str, typing.Any], check_dict=check_dict) -> None:
        check_dict[attributes["index"]]["counter"] += 1
    def _main(res_queue, index, dispatch_callback=callback, term_event=event, variable=variable) -> bool:

        term_event = Event()
        dispatcher = QueuedDispatcher(
            dispatch_callback,
            [variable] if isinstance(variable, str) else variable,
            term_event,
            max_buffer_size=buffer_size,
            max_read_rate=max_read_rate,
            attributes={"index": index},
        )

        dispatcher.start()

        try:
            for i in range(n_elements):
                if isinstance(variable, str):
                    dispatcher.add_item({string.ascii_uppercase[i % 26]: i}, variable, False)
                else:
                    for var in variable:
                        dispatcher.add_item({string.ascii_uppercase[i % 26]: i}, var, False)
        except(RuntimeError):
            res_queue.put("AARGHGHGHGHAHSHGHSDHFSEDHSE")
        
        time.sleep(0.1)

        while not dispatcher.empty:
            time.sleep(0.1)

        term_event.set()

        dispatcher.join()

        return True

    threads = []

    for i in range(3):
        _thread = Thread(target=_main, args=(result_queue, i,))
        _thread.start()
        threads.append(_thread)
    
    for i in range(3):
        threads[i].join()

    if not result_queue.empty():
        assert False

    for i in range(3):
        assert check_dict[i]["counter"] >= 2, f"Check of counter for dispatcher '{variable}' failed with count = {check_dict[i]['counter']}"

def test_queued_dispatch_error_adding_item_after_termination() -> None:
    trigger = Event()

    dispatcher = QueuedDispatcher(lambda *_: None, ["q"], trigger, False, 5, 2)
    dispatcher.start()

    trigger.set()

    with pytest.raises(RuntimeError):
        dispatcher.add_item("blah", "q", False)

def test_queued_dispatch_error_attempting_to_use_non_existent_queue() -> None:
    trigger = Event()
    dispatcher = QueuedDispatcher(lambda *_: None, ["q"], trigger, False, 5, 2)
    dispatcher.start()

    with pytest.raises(KeyError):
        dispatcher.add_item("blah", "z", False)

    trigger.set()


@pytest.mark.dispatch
@pytest.mark.parametrize(
    "append_during_dispatch", (True, False),
    ids=("pre_append", "append")
)
@pytest.mark.parametrize("multiple", (True, False), ids=("multiple", "single"))
def test_prompt_dispatcher(multiple: bool, append_during_dispatch: bool) -> None:
    n_elements: int = 10
    time_threshold: float = 1

    start_time = time.time()

    check_dict = {}

    variables = ["lemons"]

    if multiple:
        variables.append("limes")

    event = Event()
    dispatchers: list[PromptDispatcher] = []

    for variable in variables:
        check_dict[variable] = {"counter": 0}
        def callback(___: list[typing.Any], _: str, __: dict[str, typing.Any], args=check_dict, var=variable) -> None:
            args[var]["counter"] += 1
        dispatchers.append(
            PromptDispatcher(callback, [variable], event)
        )

    if not append_during_dispatch:
        for i in range(n_elements):
            for variable, dispatcher in zip(variables, dispatchers):  
                dispatcher.add_item({string.ascii_uppercase[i % 26]: i}, variable)

    for dispatcher in dispatchers:
        dispatcher.start()

    if append_during_dispatch:
        for i in range(n_elements):
            for variable, dispatcher in zip(variables, dispatchers):  
                dispatcher.add_item({string.ascii_uppercase[i % 26]: i}, variable)

    event.set()

    dispatcher.join()

    for variable in variables:
        assert check_dict[variable]["counter"] >= 1, f"Check of counter for dispatcher '{variable}' failed with count = {check_dict[variable]['counter']}"
    assert time.time() - start_time < time_threshold


