import pytest
import string
import typing
import time
from threading import Event, Thread
from queue import Queue
from concurrent.futures import ThreadPoolExecutor


from simvue.dispatch.queued import QueuedDispatcher

from simvue.dispatch.direct import DirectDispatcher
from simvue.exception import ObjectDispatchError

# FIXME: Update the layout of these tests


@pytest.mark.dispatch
@pytest.mark.parametrize("scenario", ("overload_buffer", "normal", "size_threshold_single", "size_threshold_total"))
@pytest.mark.parametrize(
    "append_during_dispatch", (True, False), ids=("pre_append", "append")
)
@pytest.mark.parametrize("multiple", (True, False), ids=("multiple", "single"))
def test_queued_dispatcher(
    scenario: typing.Literal["overload_buffer", "normal", "size_threshold_single", "size_threshold_total"], multiple: bool, append_during_dispatch: bool
) -> None:
    buffer_size: int = 10
    if scenario == "overload_buffer":
        n_elements = 2 * buffer_size
    elif scenario in ("size_threshold_total", "size_threshold_single"):
        n_elements = 1
    else:
        n_elements = buffer_size - 1
    max_read_rate: float = 0.2
    time_threshold: float = 1 + (1 / max_read_rate) if scenario == "overload_buffer" else 1

    start_time = time.time()

    check_dict = {}

    variables = ["lemons"]

    if multiple:
        variables.append("limes")

    event = Event()
    dispatchers: list[QueuedDispatcher] = []

    thresholds = {"max_size" : 10} if scenario in ("size_threshold_single", "size_threshold_total") else None

    for variable in variables:
        check_dict[variable] = {"counter": 0}

        def callback(
            ___: list[typing.Any], _: str, args=check_dict, var=variable
        ) -> None:
            args[var]["counter"] += 1

        dispatchers.append(
            QueuedDispatcher(
                callback=callback,
                object_types=[variable],
                termination_trigger=event,
                max_buffer_size=buffer_size,
                max_read_rate=max_read_rate,
                name=f"Queued_Dispatcher_{variable}",
                thresholds=thresholds
            )
        )

    if not append_during_dispatch:
        for i in range(n_elements):
            for variable, dispatcher in zip(variables, dispatchers):
                sizes = [10]
                if scenario == "size_threshold_total":
                    sizes = [1, 8, 7, 2]
                if scenario == "size_threshold_single":
                    with pytest.raises(ObjectDispatchError):
                        dispatcher.add_item(
                        {string.ascii_uppercase[i % 26]: i}, object_type=variable, blocking=False, metadata={"max_size": 12}
                        )
                    return

                for size in sizes:
                    dispatcher.add_item(
                        {string.ascii_uppercase[i % 26]: i}, object_type=variable, blocking=False, metadata={"max_size": size}
                    )

    for dispatcher in dispatchers:
        dispatcher.start()

    if append_during_dispatch:
        for i in range(n_elements):
            for variable, dispatcher in zip(variables, dispatchers):
                sizes = [10]
                if scenario == "size_threshold_total":
                    sizes = [1, 8, 7, 2]
                if scenario == "size_threshold_single":
                    with pytest.raises(ObjectDispatchError):
                        dispatcher.add_item(
                        {string.ascii_uppercase[i % 26]: i}, object_type=variable, blocking=False, metadata={"max_size": 12}
                        )
                    return

                for size in sizes:
                    dispatcher.add_item(
                        {string.ascii_uppercase[i % 26]: i}, object_type=variable, blocking=False, metadata={"max_size": size}
                    )

    counter = 0

    while not dispatcher.empty and counter < 100:
        counter += 1
        time.sleep(0.1)

    if counter >= 100:
        raise AssertionError("Failed to empty dispatch queue")

    event.set()

    dispatcher.join()
    time.sleep(0.1)

    for variable in variables:
        assert check_dict[variable]["counter"] >= (2 if scenario in ("overload_buffer", "size_threshold_total") else 1), (
            f"Check of counter for dispatcher '{variable}' failed with count = {check_dict[variable]['counter']}"
        )

    if scenario in ("size_threshold_single", "size_threshold_total"):
        return

    assert time.time() - start_time < time_threshold


@pytest.mark.dispatch
@pytest.mark.parametrize("multi_queue", (True, False))
def test_nested_queued_dispatch(multi_queue: bool) -> None:
    check_dict = [{"counter": 0} for _ in range(10)]
    buffer_size: int = 10
    n_elements: int = 2 * buffer_size
    max_read_rate: float = 0.2
    variable: str | list[str] = ["events", "metrics"] if multi_queue else "demo"

    result_queue = Queue()

    event = Event()

    def create_callback(index):
        def callback(
            ___: list[typing.Any], _: str, check_dict=check_dict[index]
        ) -> None:
            check_dict["counter"] += 1

        return callback

    def _main(
        res_queue,
        index,
        dispatch_callback=create_callback,
        term_event=event,
        variable=variable,
    ) -> bool:
        term_event = Event()
        dispatcher = QueuedDispatcher(
            callback=dispatch_callback(index),
            object_types=[variable] if isinstance(variable, str) else variable,
            termination_trigger=term_event,
            max_buffer_size=buffer_size,
            max_read_rate=max_read_rate,
            name=f"test_nested_queued_dispatch"
        )

        dispatcher.start()

        try:
            for i in range(n_elements):
                if isinstance(variable, str):
                    dispatcher.add_item(
                        {string.ascii_uppercase[i % 26]: i}, object_type=variable, blocking=False
                    )
                else:
                    for var in variable:
                        dispatcher.add_item(
                            {string.ascii_uppercase[i % 26]: i}, object_type=var, blocking=False
                        )
        except RuntimeError:
            res_queue.put("AARGHGHGHGHAHSHGHSDHFSEDHSE")

        time.sleep(0.1)

        while not dispatcher.empty:
            time.sleep(0.1)

        term_event.set()

        dispatcher.join()

        return True

    threads = []

    for i in range(3):
        _thread = Thread(
            target=_main,
            args=(
                result_queue,
                i,
            ),
            daemon=True,
            name=f"nested_queue_dispatch_{i}_Thread",
        )
        _thread.start()
        threads.append(_thread)

    for i in range(3):
        threads[i].join()

    if not result_queue.empty():
        assert False

    for i in range(3):
        assert check_dict[i]["counter"] >= 2, (
            f"Check of counter for dispatcher '{variable}' failed with count = {check_dict[i]['counter']}"
        )


def test_queued_dispatch_error_adding_item_after_termination() -> None:
    trigger = Event()

    dispatcher = QueuedDispatcher(
        callback=lambda *_: None,
        object_types=["q"],
        termination_trigger=trigger,
        max_buffer_size=5,
        max_read_rate=2,
        name="test_queued_dispatch_error_adding_item_after_termination"
    )
    dispatcher.start()

    trigger.set()

    with pytest.raises(RuntimeError):
        dispatcher.add_item("blah", object_type="q", blocking=False)


def test_queued_dispatch_error_attempting_to_use_non_existent_queue() -> None:
    trigger = Event()
    dispatcher = QueuedDispatcher(
        callback=lambda *_: None,
        object_types=["q"],
        termination_trigger=trigger,
        max_buffer_size=5,
        max_read_rate=2,
        name="test_queued_dispatch_error_attempting_to_use_non_existent_queue"
    )
    dispatcher.start()

    with pytest.raises(KeyError):
        dispatcher.add_item("blah", object_type="z", blocking=False)

    trigger.set()


@pytest.mark.dispatch
@pytest.mark.parametrize("scenario", ("multiple", "single", "max_exceed"))
def test_direct_dispatcher(scenario: typing.Literal["multiple", "single", "max_exceed"]) -> None:
    n_elements: int = 10
    time_threshold: float = 1

    start_time = time.time()

    check_dict = {}

    variables = ["lemons"]

    if scenario == "multiple":
        variables.append("limes")

    event = Event()
    dispatchers: list[DirectDispatcher] = []

    thresholds = {} if scenario != "max_exceed" else {"max_size": 10}

    for variable in variables:
        check_dict[variable] = {"counter": 0}

        def callback(
            ___: list[typing.Any], _: str, args=check_dict, var=variable
        ) -> None:
            args[var]["counter"] += 1

        dispatchers.append(DirectDispatcher(callback=callback, object_types=[variable], termination_trigger=event, thresholds=thresholds))

    for i in range(n_elements):
        for variable, dispatcher in zip(variables, dispatchers):
            if scenario == "max_exceed":
                with pytest.raises(ObjectDispatchError):
                    dispatcher.add_item({string.ascii_uppercase[i % 26]: i}, object_type=variable, metadata={"max_size": 12})
                return
            dispatcher.add_item({string.ascii_uppercase[i % 26]: i}, object_type=variable)

    event.set()

    for variable in variables:
        assert check_dict[variable]["counter"] >= 1, (
            f"Check of counter for dispatcher '{variable}' failed with count = {check_dict[variable]['counter']}"
        )
    assert time.time() - start_time < time_threshold
