"""Tests for Simvue Object filters."""
import pytest

from simvue.api.objects import Run

@pytest.mark.filter
@pytest.mark.online
def test_run_filters(create_test_run: tuple[Run, dict]) -> None:
    """Test retrieving a single run by filter set."""
    _run, TEST_DATA = create_test_run
    _tags=TEST_DATA["tags"]
    _folder=TEST_DATA["folder"]
    _name=TEST_DATA["name"]
    _filter = Run.filter()
    for tag in _tags:
        _filter = _filter.has_tag(tag)
    _filter = _filter.in_folder(_folder)
    _filter = _filter.has_name(_name)
    _filter = _filter.created_within(hours=1)
    assert _filter.count() == 1
