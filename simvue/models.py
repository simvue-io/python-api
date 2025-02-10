import datetime
import typing
import pydantic


FOLDER_REGEX: str = r"^/.*"
NAME_REGEX: str = r"^[a-zA-Z0-9\-\_\s\/\.:]+$"
METRIC_KEY_REGEX: str = r"^[a-zA-Z0-9\-\_\s\/\.:=><]+$"
DATETIME_FORMAT: str = "%Y-%m-%dT%H:%M:%S.%f"

MetadataKeyString = typing.Annotated[
    str, pydantic.StringConstraints(pattern=r"^[\w\-\s\.]+$")
]
TagString = typing.Annotated[str, pydantic.StringConstraints(pattern=r"^[\w\-\s\.]+$")]
MetricKeyString = typing.Annotated[
    str, pydantic.StringConstraints(pattern=METRIC_KEY_REGEX)
]


# Pydantic class to validate run.init()
class RunInput(pydantic.BaseModel):
    name: str | None = pydantic.Field(None, pattern=NAME_REGEX)
    metadata: dict[MetadataKeyString, str | int | float | None] | None = None
    tags: list[TagString] | None = None
    description: str | None = None
    folder: str = pydantic.Field(pattern=FOLDER_REGEX)
    status: str | None = None
    ttl: pydantic.PositiveInt | None = None


class MetricSet(pydantic.BaseModel):
    time: pydantic.NonNegativeFloat | pydantic.NonNegativeInt
    timestamp: str
    step: pydantic.NonNegativeInt
    values: dict[str, int | float | bool]

    @pydantic.field_validator("timestamp", mode="after")
    @classmethod
    def timestamp_str(cls, value: str) -> str:
        try:
            datetime.datetime.strptime(value, DATETIME_FORMAT)
        except ValueError as e:
            raise AssertionError(
                f"Invalid timestamp, expected form '{DATETIME_FORMAT}'"
            ) from e
        return value


class EventSet(pydantic.BaseModel):
    message: str
    timestamp: str

    @pydantic.field_validator("timestamp", mode="after")
    @classmethod
    def timestamp_str(cls, value: str) -> str:
        try:
            datetime.datetime.strptime(value, DATETIME_FORMAT)
        except ValueError as e:
            raise AssertionError(
                f"Invalid timestamp, expected form '{DATETIME_FORMAT}'"
            ) from e
        return value
