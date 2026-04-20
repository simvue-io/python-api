"""Tests on future features being implemented."""
import pytest

from simvue.exception import ObjectNotFoundError
from simvue.experimental.fetch import get_metric_values, get_run_id_from_name
from simvue.api.objects import Run

@pytest.mark.online
@pytest.mark.experimental
def test_fetch_metric_values(create_test_run: tuple[Run, dict]) -> None:
    _run, _meta = create_test_run
    for _id, _data in get_metric_values(metric_names=_meta["metrics"][:-1], run_ids=[_run.id], x_axis="step"):
        assert _data.get(_meta["metrics"][0])[0].get("value") is not None
        assert _data.get(_meta["metrics"][0])[0].get("step") is not None
        assert _data.get(_meta["metrics"][1])[0].get("value") is not None
        assert _data.get(_meta["metrics"][1])[0].get("step") is not None


@pytest.mark.online
@pytest.mark.experimental
@pytest.mark.parametrize(
    "allow_failure", (True, False),
        ids=("allow_fail", "raise_exception")
)
@pytest.mark.parametrize(
    "run_exists", (True, False),
        ids=("run_exists", "run_absent")
)
def test_fetch_run_id_by_name(allow_failure: bool, run_exists: bool, create_plain_run: tuple[Run, dict]) -> None:
    _run, _meta = create_plain_run
    if run_exists:
        assert get_run_id_from_name(_meta["name"])
    elif allow_failure:
        assert not get_run_id_from_name("run_not_found", missing_ok=True)
    else:
        with pytest.raises(ObjectNotFoundError) as e:
            get_run_id_from_name("run_not_found")
        assert all(i in f"{e}" for i in ("run", "run_not_found"))
