"""Tests on future features being implemented."""
import pytest

from simvue.experimental.fetch import get_metric_values
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

