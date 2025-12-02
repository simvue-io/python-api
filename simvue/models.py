import datetime
import typing
import numpy
import warnings
import pydantic


FOLDER_REGEX: str = r"^/.*"
NAME_REGEX: str = r"^[a-zA-Z0-9\-\_\s\/\.:]+$"
METRIC_KEY_REGEX: str = r"^[a-zA-Z0-9\-\_\s\/\.:=><+\(\)]+$"
DATETIME_FORMAT: str = "%Y-%m-%dT%H:%M:%S.%f"
OBJECT_ID: str = r"^[A-Za-z0-9]{22}$"

MetadataKeyString = typing.Annotated[
    str, pydantic.StringConstraints(pattern=r"^[\w\-\s\.]+$")
]
TagString = typing.Annotated[str, pydantic.StringConstraints(pattern=r"^[\w\-\s\.]+$")]
MetricKeyString = typing.Annotated[
    str, pydantic.StringConstraints(pattern=METRIC_KEY_REGEX)
]
ObjectID = typing.Annotated[str, pydantic.StringConstraints(pattern=OBJECT_ID)]


def validate_timestamp(timestamp: str, raise_except: bool = True) -> bool:
    """
    Validate a user-provided timestamp
    """
    try:
        _ = datetime.datetime.strptime(timestamp, DATETIME_FORMAT)
    except ValueError as e:
        if raise_except:
            raise e
        return False

    return True


@pydantic.validate_call(config={"validate_default": True})
def simvue_timestamp(
    date_time: datetime.datetime
    | typing.Annotated[str | None, pydantic.BeforeValidator(validate_timestamp)]
    | None = None,
) -> str:
    """Return the Simvue valid timestamp

    Parameters
    ----------
    date_time: datetime.datetime | str, optional
        if provided, the datetime object to convert,
        else use current date and time
        if a string assume to be local time.

    Returns
    -------
    str
        Datetime string valid for the Simvue server
    """
    if isinstance(date_time, str):
        warnings.warn(
            "Timestamps as strings for object recording will be deprecated in Python API >= 2.3"
        )
    if not date_time:
        date_time = datetime.datetime.now(datetime.timezone.utc)
    elif isinstance(date_time, str):
        _local_time = datetime.datetime.now().tzinfo
        date_time = (
            datetime.datetime.strptime(date_time, DATETIME_FORMAT)
            .replace(tzinfo=_local_time)
            .astimezone(datetime.timezone.utc)
        )
    return date_time.strftime(DATETIME_FORMAT)


# Pydantic class to validate run.init()
class RunInput(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")
    name: str | None = pydantic.Field(None, pattern=NAME_REGEX)
    metadata: dict[MetadataKeyString, str | int | float | None] | None = None
    tags: list[TagString] | None = None
    description: str | None = None
    folder: str = pydantic.Field(pattern=FOLDER_REGEX)
    status: str | None = None
    ttl: pydantic.PositiveInt | None = None


class MetricSet(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")
    time: pydantic.NonNegativeFloat | pydantic.NonNegativeInt
    timestamp: typing.Annotated[str | None, pydantic.BeforeValidator(simvue_timestamp)]
    step: pydantic.NonNegativeInt
    values: dict[str, int | float | bool]


class GridMetricSet(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(
        arbitrary_types_allowed=True, extra="forbid", validate_default=True
    )
    time: pydantic.NonNegativeFloat | pydantic.NonNegativeInt
    timestamp: typing.Annotated[str | None, pydantic.BeforeValidator(simvue_timestamp)]
    step: pydantic.NonNegativeInt
    array: list[float] | list[list[float]] | numpy.ndarray
    grid: str
    metric: str

    @pydantic.field_serializer("array", when_used="always")
    def serialize_array(
        self, value: numpy.ndarray | list[float] | list[list[float]], *_
    ) -> list[float] | list[list[float]]:
        if isinstance(value, list):
            return value
        return value.tolist()


class EventSet(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")
    message: str
    timestamp: typing.Annotated[str | None, pydantic.BeforeValidator(simvue_timestamp)]
