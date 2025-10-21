import pytest

from simvue.api.objects import Stats

@pytest.mark.api
@pytest.mark.online
def test_stats() -> None:
    _statistics = Stats()
    assert f"{_statistics.url}" == f"{_statistics.base_url}"
    assert isinstance(_statistics.runs.created, int)
    assert isinstance(_statistics.runs.running, int)
    assert isinstance(_statistics.runs.completed, int)
    assert isinstance(_statistics.runs.data, int)
    assert _statistics.to_dict()
    assert _statistics.whoami()

    with pytest.raises(AttributeError):
        Stats.new()

