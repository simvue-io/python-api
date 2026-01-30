import pathlib
import uuid
import pytest
import simvue
import time
import platform
import contextlib
import random
import tempfile
import threading
from multiprocessing import Process, Manager

from simvue.api.objects.artifact.fetch import Artifact


@pytest.mark.scenario
@pytest.mark.parametrize("file_size", (1, 10, 100))
def test_large_file_upload(
    file_size: int, create_plain_run: tuple[simvue.Run, dict]
) -> None:
    FILE_SIZE_MB: int = file_size
    _file = None
    _temp_file_name = None
    run = simvue.Run()
    _uuid = f"{uuid.uuid4()}".split("-")[0]
    run.init(
        "test_large_file_artifact",
        folder=f"/simvue_unit_testing/{_uuid}",
        retention_period="20 mins",
        tags=[platform.system(), "test_large_file_artifact"],
    )
    run.update_metadata({"file_size_mb": file_size})

    try:
        with tempfile.NamedTemporaryFile(mode="w+b", delete=False) as temp_f:
            temp_f.seek(FILE_SIZE_MB * 1024 * 1024 - 1)
            temp_f.write(b"\0")
            temp_f.flush()
            temp_f.seek(0)
            temp_f.close()
        _temp_file_name = temp_f.name
        _input_file_size = pathlib.Path(f"{_temp_file_name}").stat().st_size
        run.save_file(
            file_path=f"{temp_f.name}",
            category="output",
            name="test_large_file_artifact",
        )
        run.close()

        client = simvue.Client()

        with tempfile.TemporaryDirectory() as tempd:
            client.get_artifact_as_file(
                run_id=run.id, name="test_large_file_artifact", output_dir=tempd
            )

            _file = next(pathlib.Path(tempd).glob("*"))

            # Assert the returned file size
            assert _file.stat().st_size == _input_file_size
    except Exception as e:
        _run = simvue.Run()
        _run.reconnect(run.id)
        _run.set_status("failed")
        raise e
    finally:
        if _file and _file.exists():
            _file.unlink()
        if _temp_file_name and (_src := pathlib.Path(_temp_file_name)).exists():
            _src.unlink()
        with contextlib.suppress(Exception):
            Artifact.from_name("test_large_file_artifact", run_id=run.id).delete()


@pytest.mark.scenario
def test_time_multi_run_create_threshold() -> None:
    start = time.time()
    runs: list[simvue.Run] = []
    for i in range(10):
        run = simvue.Run()
        run.init(
            f"test run {i}",
            tags=[platform.system(), "test_benchmarking"],
            folder="/simvue_benchmark_testing",
            retention_period="1 hour",
        )
        runs.append(run)
    for run in runs:
        run.close()
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


@pytest.fixture
def run_deleter(request):
    ident_dict = {}

    def delete_run():
        simvue.Client().delete_run(ident_dict["ident"])

    request.addfinalizer(delete_run)
    return ident_dict


def upload(name: str, values_per_run: int, shared_dict) -> None:
    run = simvue.Run()
    run.init(name=name, tags=[platform.system(), "simvue_client_tests"])
    shared_dict["ident"] = run.id
    for i in range(values_per_run):
        run.log_metrics({"increment": i})
    run.close()


@pytest.mark.scenario
@pytest.mark.parametrize("values_per_run", (1, 2, 100, 1500))
@pytest.mark.parametrize("processing", ("local", "on_thread", "on_process"))
def test_uploaded_data_immediately_accessible(
    values_per_run: int, processing: str, run_deleter
) -> None:
    name = f"Test-{random.randint(0, 1000000000)}"
    manager = Manager()
    shared_dict = manager.dict()

    if processing == "local":
        upload(name, values_per_run, shared_dict)
    else:
        if processing == "on_thread":
            thread = threading.Thread(
                target=upload,
                args=(name, values_per_run, shared_dict),
                daemon=True,
                name=f"{name}_Thread",
            )
        else:
            thread = Process(target=upload, args=(name, values_per_run, shared_dict))
        thread.start()
        thread.join()

    run_deleter["ident"] = shared_dict["ident"]

    values = simvue.Client().get_metric_values(
        ["increment"],
        "step",
        run_ids=[shared_dict["ident"]],
        max_points=2 * values_per_run,
        aggregate=False,
    )["increment"]

    assert len(values) == values_per_run, "all uploaded values should be returned"

    for i in range(len(values)):
        assert i == int(values[(i, shared_dict["ident"])]), (
            "values should be ascending ints"
        )

@pytest.mark.scenario
def test_negative_time(create_plain_run: tuple[simvue.Run, dict]) -> None:
    _run, _ = create_plain_run

    for i in range(10):
        time.sleep(0.1)
        _run.log_metrics({"x": 10, "y": 20}, time=-10 + i)

