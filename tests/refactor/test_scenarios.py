import pytest
import simvue
import time
import contextlib

@pytest.mark.scenario
def test_time_multi_run_create_threshold() -> None:
    start = time.time()
    for i in range(20):
        with simvue.Run() as run:
            run.init(f"test run {i}", tags=["test_benchmarking"], folder="/simvue_benchmark_testing")
    end = time.time()
    client = simvue.Client()
    with contextlib.suppress(RuntimeError):
        client.delete_runs("/simvue_benchmark_testing")
        client.delete_folder("/simvue_benchmark_testing", remove_runs=False, allow_missing=True, recursive=True)
    assert start - end < 60.
