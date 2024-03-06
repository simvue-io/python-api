import pytest
import random
import typing
import simvue.converters as sv_conf

try:
    import pandas
except ImportError:
    pandas = None


@pytest.mark.converters
@pytest.mark.parametrize(
    "xaxis", ("step", "time", "timestamp"),
)
@pytest.mark.parametrize(
    "name", (None, "values")
)
@pytest.mark.skipif(not pandas, reason="Pandas not installed")
def test_metrics_to_dataframe(xaxis: str, name: typing.Optional[str]) -> None:
    ROWS: int = 100
    COLUMNS: int = 10
    TEST_METRICS: list[list[float]] = [
        [random.random() for _ in range(COLUMNS)]
        for _ in range(ROWS)
    ]
    sv_conf.metrics_to_dataframe(
        data=TEST_METRICS,
        xaxis=xaxis,
        name=name
    )
