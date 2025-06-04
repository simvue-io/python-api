"""Simvue API Utility methods."""

import contextlib
import datetime
import functools
import hashlib
import importlib.util
import json
import logging
import mimetypes
import os
import pathlib
import typing

import jwt
import pydantic
import tabulate
from deepmerge import Merger

try:
    from typing import Self
except ImportError:
    from typing import Self

from simvue.api.objects.artifact import file
from simvue.models import DATETIME_FORMAT

CHECKSUM_BLOCK_SIZE = 4096
EXTRAS: tuple[str, ...] = ("plot", "torch")

logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    from simvue.run import Run


def find_first_instance_of_file(
    file_names: list[str] | str, *, check_user_space: bool = True
) -> pathlib.Path | None:
    """Traverses a file hierarchy from bottom upwards to find file.

    Returns the first instance of 'file_names' found when moving
    upward from the current directory.

    Parameters
    ----------
    file_names: list[str] | str
        candidate names of file to locate
    *
    check_user_space: bool, optional
        check the users home area if current working directory is not
        within it. Default is True.

    Returns
    -------
    pathlib.Path | None
        first matching file if found
    """
    if isinstance(file_names, str):
        file_names = [file_names]

    for file_name in file_names:
        _user_file = pathlib.Path.cwd().joinpath(file_name)
        if _user_file.exists():
            return _user_file

    # If the user is running on different mounted volume or outside
    # of their user space then the above will not return the file
    if check_user_space:
        for file_name in file_names:
            _user_file = pathlib.Path.home().joinpath(file_name)
            if _user_file.exists():
                return _user_file

    return None


def parse_validation_response(
    response: dict[str, list[dict[str, str]]],
) -> str:
    """Parse ValidationError response from server.

    Reformats the error information from a validation error into a human
    readable table. Checks if 'body' exists within response to determine
    whether or not the output can contain the original input.

    Parameters
    ----------
    response : dict[str, list[dict[str, str]]]
        response from Simvue server

    Returns
    -------
    str
        return the validation information
    """
    if not (issues := response.get("detail")):
        _exc_msg = "Expected key 'detail' in server response during validation failure"

        raise RuntimeError(_exc_msg)

    out: list[list[str]] = []

    if isinstance(issues, str):
        return tabulate.tabulate(
            ["Unknown", "N/A", issues],
            headers=["Type", "Location", "Message"],
            tablefmt="fancy_grid",
        )

    for issue in issues:
        obj_type: str = issue["type"]
        location: list[str] = issue["loc"]
        location.remove("body")
        location_addr: str = "".join(
            (f"[{loc}]" if isinstance(loc, int) else f"{'.' if i > 0 else ''}{loc}")
            for i, loc in enumerate(location)
        )
        headers = ["Type", "Location", "Message"]
        information = [obj_type, location_addr]

        # Check if server response contains 'body'
        if body := response.get("body"):
            headers = ["Type", "Location", "Input", "Message"]
            input_arg = body
            for loc in location:
                try:
                    input_arg = None if obj_type == "missing" else input_arg[loc]
                except TypeError:
                    break
            information.append(input_arg)

        msg: str = issue["msg"]
        information.append(msg)
        out.append(information)

    _table = tabulate.tabulate(out, headers=headers, tablefmt="fancy_grid")
    return str(_table)


def check_extra(extra_name: str) -> typing.Callable:
    """Check if extra component of API module is installed.

    Decorator for methods.

    Parameters
    ----------
    extra_name: str
        name of extra of simvue module to check for.
    """

    def decorator(
        class_func: typing.Callable | None = None,
    ) -> typing.Callable | None:
        @functools.wraps(class_func)
        def wrapper(
            self: Self, *args: tuple[object, ...], **kwargs: dict[str, object]
        ) -> object:
            if extra_name == "plot" and not all(
                [
                    importlib.util.find_spec("matplotlib"),
                    importlib.util.find_spec("plotly"),
                ]
            ):
                _exc_msg = (
                    f"Plotting features require the '{extra_name}' extension to Simvue"
                )

                raise RuntimeError(_exc_msg)

            if extra_name == "eco":
                if not importlib.util.find_spec("geocoder"):
                    _exc_msg = (
                        f"Eco features require the '{extra_name}' extenstion to Simvue"
                    )

                    raise RuntimeError(_exc_msg)

            elif extra_name == "torch":
                if not importlib.util.find_spec("torch"):
                    _exc_msg = (
                        "PyTorch features require the 'torch' module to be installed"
                    )

                    raise RuntimeError(_exc_msg)

            elif extra_name not in EXTRAS:
                _exc_msg = f"Unrecognised extra '{extra_name}'"
                raise RuntimeError(_exc_msg)

            return class_func(self, *args, **kwargs) if class_func else None

        return wrapper

    return decorator


def parse_pydantic_error(error: pydantic.ValidationError) -> str:
    """Parse the output of a Pydantic validation error."""
    out_table: list[str] = []
    for data in json.loads(error.json()):
        _input = data.get("input") if data["input"] is not None else "None"
        _line_limit = 50
        if isinstance(_input, dict):
            _input_str = json.dumps(_input, indent=2)
            _input_str = "\n".join(
                f"{line[:47]}..." if len(line) > _line_limit else line
                for line in _input_str.split("\n")
            )
        else:
            _input_str = (
                _input_str
                if len(_input_str := f"{_input}") < _line_limit
                else f"{_input_str[:50]}..."
            )
        _type: str = data["type"]

        _skip_type_compare_for = (
            "error",
            "missing",
            "unexpected",
            "union_tag",
            "parsing",
            "scheme",
            "syntax",
        )

        if (_input_type := type(_input)) != _type and all(
            e not in _type for e in _skip_type_compare_for
        ):
            _type = f"{_input_type.__name__} != {_type}"

        out_table.append(
            [
                _input_str,
                data["loc"],
                _type,
                data["msg"],
            ]
        )
    err_table = tabulate.tabulate(
        out_table,
        headers=["Input", "Location", "Type", "Message"],
        tablefmt="fancy_grid",
    )
    return f"`{error.title}` Validation:\n{err_table}"


def skip_if_failed(
    failure_attr: str,
    ignore_exc_attr: str,
    on_failure_return: object | None = None,
) -> typing.Callable:
    """Ensurine if Simvue throws an exception any other code continues.

    Decorator for methods.

    If Simvue throws an exception and the user has specified that such failure
    should not abort the run but rather log errors this decorator will skip
    functionality leaving the runner in a dormant state.

    Parameters
    ----------
    failure_attr : str
        the attribute of the parent class which determines if
        Simvue has failed
    ignore_exc_attr : str
        the attribute of the parent class which defines whether
        an exception should be raised or ignore, by default
    on_failure_return : typing.Any | None, optional
        the value to return instead, by default None

    Returns
    -------
    typing.Callable
        wrapped class method
    """

    def decorator(class_func: typing.Callable) -> typing.Callable:
        @functools.wraps(class_func)
        def wrapper(
            self: "Run", *args: tuple[object, ...], **kwargs: dict[str, object]
        ) -> object:
            if getattr(self, failure_attr, None) and getattr(
                self, ignore_exc_attr, None
            ):
                logger.debug(
                    "Skipping call to '%s', client in fail state (see logs).",
                    class_func.__name__,
                )
                return on_failure_return

            # Handle case where Pydantic validates the inputs
            try:
                return class_func(self, *args, **kwargs)
            except pydantic.ValidationError as e:
                _error_str = parse_pydantic_error(e)
                if getattr(self, ignore_exc_attr, True):
                    setattr(self, failure_attr, True)
                    logger.error(_error_str)  # noqa: TRY400
                    return on_failure_return
                self._error(_error_str)

        setattr(wrapper, "__fail_safe", True)
        return wrapper

    return decorator


def prettify_pydantic(class_func: typing.Callable) -> typing.Callable:
    """Convert pydantic validation errors to a table.

    Parameters
    ----------
    class_func : typing.Callable
        function to wrap

    Returns
    -------
    typing.Callable
        wrapped function

    Raises
    ------
    RuntimeError
        the formatted validation error
    """

    @functools.wraps(class_func)
    def wrapper(
        self: Self, *args: tuple[object, ...], **kwargs: dict[str, object]
    ) -> object:
        try:
            return class_func(self, *args, **kwargs)
        except pydantic.ValidationError as e:
            error_str = parse_pydantic_error(e)
            raise RuntimeError(error_str) from e

    return wrapper


def create_file(filename: str) -> None:
    """Create an empty file."""
    try:
        with pathlib.Path(filename).open("w") as fh:
            fh.write("")
    except Exception:
        logger.exception("Unable to write file %s", filename)


def remove_file(filename: str) -> None:
    """Remove file."""
    if not pathlib.Path(filename).exists():
        return

    try:
        pathlib.Path(filename).unlink(missing_ok=True)
    except Exception:
        logger.exception("Unable to remove file %s", filename)


def get_expiry(token: str) -> int | None:
    """Get expiry date from a JWT token."""
    expiry: int | None = None
    with contextlib.suppress(jwt.DecodeError):
        expiry = jwt.decode(token, options={"verify_signature": False})["exp"]

    return expiry


def prepare_for_api(
    data_in: dict[str, object], *, pickle_all: bool = True
) -> dict[str, object]:
    """Remove references to pickling."""
    data = data_in.copy()
    if "pickled" in data:
        del data["pickled"]
    if "pickledFile" in data and pickle_all:
        del data["pickledFile"]
    return data


def calculate_sha256(filename: str | object, *, is_file: bool) -> str | None:
    """Calculate sha256 checksum of the specified file."""
    sha256_hash = hashlib.sha256()
    if is_file:
        try:
            with pathlib.Path(filename).open("rb") as fd:
                for byte_block in iter(lambda: fd.read(CHECKSUM_BLOCK_SIZE), b""):
                    sha256_hash.update(byte_block)
                return sha256_hash.hexdigest()
        except Exception:
            logger.exception("Failed to calculate hash for %s", filename)
            return None

    if isinstance(filename, str):
        sha256_hash.update(bytes(filename, "utf-8"))
    else:
        sha256_hash.update(bytes(filename))
    return sha256_hash.hexdigest()


def validate_timestamp(timestamp: str) -> bool:
    """Validate a user-provided timestamp."""
    try:
        datetime.datetime.strptime(timestamp, DATETIME_FORMAT).astimezone(datetime.UTC)
    except ValueError:
        return False

    return True


def simvue_timestamp(date_time: datetime.datetime | None = None) -> str:
    """Return the Simvue valid timestamp.

    Parameters
    ----------
    date_time: datetime.datetime, optional
        if provided, the datetime object to convert, else use current date and time

    Returns
    -------
    str
        Datetime string valid for the Simvue server
    """
    if not date_time:
        date_time = datetime.datetime.now(datetime.UTC)
    return date_time.strftime(DATETIME_FORMAT)


@functools.lru_cache
def get_mimetypes() -> list[str]:
    """Return a list of allowed MIME types."""
    mimetypes.init()
    _valid_mimetypes = ["application/vnd.plotly.v1+json"]
    _valid_mimetypes += list(mimetypes.types_map.values())
    return _valid_mimetypes


def get_mimetype_for_file(file_path: pathlib.Path) -> str:
    """Return MIME type for the given file."""
    _guess, *_ = mimetypes.guess_type(file_path)
    return _guess or "application/octet-stream"


# Create a new Merge strategy for merging local file and staging attributes
staging_merger = Merger(
    # pass in a list of tuple, with the
    # strategies you are looking to apply
    # to each type.
    [(list, ["override"]), (dict, ["merge"]), (set, ["union"])],
    # next, choose the fallback strategies,
    # applied to all other types:
    ["override"],
    # finally, choose the strategies in
    # the case where the types conflict:
    ["override"],
)
