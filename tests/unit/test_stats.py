import pytest

from simvue.api.objects import Stats

@pytest.mark.api
def test_stats() -> None:
    _statistics = Stats()
    assert isinstance(_statistics.runs.created, int)
    assert isinstance(_statistics.runs.running, int)
    assert isinstance(_statistics.runs.completed, int)
    assert isinstance(_statistics.runs.data, int)

    with pytest.raises(AttributeError):
        Stats.new()

