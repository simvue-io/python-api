import pytest
import simvue
import time
import contextlib
import random
import threading
from multiprocessing import Process, Manager


@pytest.mark.scenario
def test_time_multi_run_create_threshold() -> None:
    start = time.time()
    for i in range(20):
        with simvue.Run() as run:
            run.init(
                f"test run {i}",
                tags=["test_benchmarking"],
                folder="/simvue_benchmark_testing",
            )
    end = time.time()
    client = simvue.Client()
    with contextlib.suppress(RuntimeError):
        client.delete_runs("/simvue_benchmark_testing")
        client.delete_folder(
            "/simvue_benchmark_testing",
            remove_runs=False,
            allow_missing=True,
            recursive=True,
        )
    assert start - end < 60.0


@pytest.mark.scenario
def test_uploaded_data_immediately_accessible() -> None:
    def upload(name: str, values_per_run: int, shared_dict) -> None:
        run = simvue.Run()
        run.init(name=name, tags=["simvue_client_tests"])
        shared_dict["ident"] = run._id
        for i in range(values_per_run):
            run.log_metrics({"increment": i})
        run.close()

    name = "Test-" + str(random.randint(0, 1000000000))
    manager = Manager()
    shared_dict = manager.dict()
    values_per_run = 100

    upload(name, values_per_run, shared_dict)

    values = simvue.Client().get_metrics(
        shared_dict["ident"], "increment", "step", max_points=2 * values_per_run
    )

    assert len(values) == values_per_run, "all uploaded values should be returned"

    for i in range(len(values)):
        assert i == int(values[i][1]), "values should be ascending ints"

    simvue.Client().delete_run(shared_dict["ident"])
