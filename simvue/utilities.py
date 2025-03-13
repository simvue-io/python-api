import datetime
import hashlib
import logging
import json
import mimetypes
import tabulate
import pydantic
import importlib.util
import functools
import contextlib
import os
import pathlib
import typing
import jwt
from deepmerge import Merger

from datetime import timezone
from simvue.models import DATETIME_FORMAT


CHECKSUM_BLOCK_SIZE = 4096
EXTRAS: tuple[str, ...] = ("plot", "torch")

logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    from simvue.run import Run


def find_first_instance_of_file(
    file_names: list[str] | str, check_user_space: bool = True
) -> pathlib.Path | None:
    """Traverses a file hierarchy from bottom upwards to find file

    Returns the first instance of 'file_names' found when moving
    upward from the current directory.

    Parameters
    ----------
        candidate names of file to locate
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
    """Parse ValidationError response from server

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
        raise RuntimeError(
            "Expected key 'detail' in server response during validation failure"
        )

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
    def decorator(
        class_func: typing.Callable | None = None,
    ) -> typing.Callable | None:
        @functools.wraps(class_func)
        def wrapper(self, *args, **kwargs) -> typing.Any:
            if extra_name == "plot" and not all(
                [
                    importlib.util.find_spec("matplotlib"),
                    importlib.util.find_spec("plotly"),
                ]
            ):
                raise RuntimeError(
                    f"Plotting features require the '{extra_name}' extension to Simvue"
                )
            elif extra_name == "eco":
                if not importlib.util.find_spec("geocoder"):
                    raise RuntimeError(
                        f"Eco features require the '{extra_name}' extenstion to Simvue"
                    )
            elif extra_name == "torch":
                if not importlib.util.find_spec("torch"):
                    raise RuntimeError(
                        "PyTorch features require the 'torch' module to be installed"
                    )
            elif extra_name not in EXTRAS:
                raise RuntimeError(f"Unrecognised extra '{extra_name}'")
            return class_func(self, *args, **kwargs) if class_func else None

        return wrapper

    return decorator


def parse_pydantic_error(error: pydantic.ValidationError) -> str:
    out_table: list[str] = []
    for data in json.loads(error.json()):
        _input = data.get("input") if data["input"] is not None else "None"
        if isinstance(_input, dict):
            _input_str = json.dumps(_input, indent=2)
            _input_str = "\n".join(
                f"{line[:47]}..." if len(line) > 50 else line
                for line in _input_str.split("\n")
            )
        else:
            _input_str = (
                _input_str
                if len((_input_str := f"{_input}")) < 50
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
    on_failure_return: typing.Any | None = None,
) -> typing.Callable:
    """Decorator for ensuring if Simvue throws an exception any other code continues.

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
        def wrapper(self: "Run", *args, **kwargs) -> typing.Any:
            if getattr(self, failure_attr, None) and getattr(
                self, ignore_exc_attr, None
            ):
                logger.debug(
                    f"Skipping call to '{class_func.__name__}', "
                    f"client in fail state (see logs)."
                )
                return on_failure_return

            # Handle case where Pydantic validates the inputs
            try:
                return class_func(self, *args, **kwargs)
            except pydantic.ValidationError as e:
                error_str = parse_pydantic_error(e)
                if getattr(self, ignore_exc_attr, True):
                    setattr(self, failure_attr, True)
                    logger.error(error_str)
                    return on_failure_return
                self._error(error_str)

        setattr(wrapper, "__fail_safe", True)
        return wrapper

    return decorator


def prettify_pydantic(class_func: typing.Callable) -> typing.Callable:
    """Converts pydantic validation errors to a table

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
    def wrapper(self, *args, **kwargs) -> typing.Any:
        try:
            return class_func(self, *args, **kwargs)
        except pydantic.ValidationError as e:
            error_str = parse_pydantic_error(e)
            raise RuntimeError(error_str)

    return wrapper


def create_file(filename: str) -> None:
    """
    Create an empty file
    """
    try:
        with open(filename, "w") as fh:
            fh.write("")
    except Exception as err:
        logger.error("Unable to write file %s due to: %s", filename, str(err))


def remove_file(filename: str) -> None:
    """
    Remove file
    """
    if os.path.isfile(filename):
        try:
            os.remove(filename)
        except Exception as err:
            logger.error("Unable to remove file %s due to: %s", filename, str(err))


def get_expiry(token) -> int | None:
    """
    Get expiry date from a JWT token
    """
    expiry: int | None = None
    with contextlib.suppress(jwt.DecodeError):
        expiry = jwt.decode(token, options={"verify_signature": False})["exp"]

    return expiry


def prepare_for_api(data_in, all=True):
    """
    Remove references to pickling
    """
    data = data_in.copy()
    if "pickled" in data:
        del data["pickled"]
    if "pickledFile" in data and all:
        del data["pickledFile"]
    return data


def calculate_sha256(filename: str | typing.Any, is_file: bool) -> str | None:
    """
    Calculate sha256 checksum of the specified file
    """
    sha256_hash = hashlib.sha256()
    if is_file:
        try:
            with open(filename, "rb") as fd:
                for byte_block in iter(lambda: fd.read(CHECKSUM_BLOCK_SIZE), b""):
                    sha256_hash.update(byte_block)
                return sha256_hash.hexdigest()
        except Exception:
            return None

    if isinstance(filename, str):
        sha256_hash.update(bytes(filename, "utf-8"))
    else:
        sha256_hash.update(bytes(filename))
    return sha256_hash.hexdigest()


def validate_timestamp(timestamp):
    """
    Validate a user-provided timestamp
    """
    try:
        datetime.datetime.strptime(timestamp, DATETIME_FORMAT)
    except ValueError:
        return False

    return True


def simvue_timestamp(date_time: datetime.datetime | None = None) -> str:
    """Return the Simvue valid timestamp

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
        date_time = datetime.datetime.now(timezone.utc)
    return date_time.strftime(DATETIME_FORMAT)


@functools.lru_cache
def get_mimetypes() -> list[str]:
    """Returns a list of allowed MIME types"""
    mimetypes.init()
    _valid_mimetypes = ["application/vnd.plotly.v1+json"]
    _valid_mimetypes += list(mimetypes.types_map.values())
    return _valid_mimetypes


def get_mimetype_for_file(file_path: pathlib.Path) -> str:
    """Return MIME type for the given file"""
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
