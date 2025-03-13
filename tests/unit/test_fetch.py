import pytest

from simvue.api.objects import Alert, Artifact, Tag, Run


@pytest.mark.api
@pytest.mark.online
@pytest.mark.parametrize(
    "sort_column,sort_descending",
    [
        ("name", True),
        ("created", False),
        (None, None)
    ],
    ids=("name-desc", "created-asc", "no-sorting")
)
def test_alerts_fetch(sort_column: str | None, sort_descending: bool | None) -> None:
    if sort_column:
        assert dict(Alert.get(sorting=[{"column": sort_column, "descending": sort_descending}], count=10))
    else:
        assert dict(Alert.get(count=10))


@pytest.mark.api
@pytest.mark.online
@pytest.mark.parametrize(
    "sort_column,sort_descending",
    [
        ("name", True),
        ("created", False),
        (None, None)
    ],
    ids=("name-desc", "created-asc", "no-sorting")
)
def test_artifacts_fetch(sort_column: str | None, sort_descending: bool | None) -> None:
    if sort_column:
        assert dict(Artifact.get(sorting=[{"column": sort_column, "descending": sort_descending}], count=10))
    else:
        assert dict(Artifact.get(count=10))


@pytest.mark.api
@pytest.mark.online
@pytest.mark.parametrize(
    "sort_column,sort_descending",
    [
        ("name", True),
        ("created", False),
        (None, None)
    ],
    ids=("name-desc", "created-asc", "no-sorting")
)
def test_tags_fetch(sort_column: str | None, sort_descending: bool | None) -> None:
    if sort_column:
        assert dict(Tag.get(sorting=[{"column": sort_column, "descending": sort_descending}], count=10))
    else:
        assert dict(Tag.get(count=10))


@pytest.mark.api
@pytest.mark.online
@pytest.mark.parametrize(
    "sort_column,sort_descending",
    [
        ("name", True),
        ("name", False),
        (None, None)
    ],
    ids=("name-desc", "created-asc", "no-sorting")
)
def test_runs_fetch(sort_column: str | None, sort_descending: bool | None) -> None:
    if sort_column:
        assert dict(Run.get(sorting=[{"column": sort_column, "descending": sort_descending}], count=10))
    else:
        assert dict(Run.get(count=10))
