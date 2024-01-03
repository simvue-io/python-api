import configparser
import jwt
import logging
import os
import requests
import contextlib
import tempfile
import typing
import functools

logger = logging.getLogger(__name__)


def skip_if_failed(
    failure_attr: str,
    ignore_exc_attr: str,
    on_failure_return: typing.Any | None = None
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
        def wrapper(self, *args, **kwargs) -> typing.Any:
            if (
                getattr(self, failure_attr, None) and 
                getattr(self, ignore_exc_attr, None)
            ):
                logger.debug(f"Skipping call to '{class_func.__name__}', client in fail state (see logs).")
                return on_failure_return
            return class_func(self, *args, **kwargs)

        return wrapper

    return decorator


def get_auth():
    """
    Get the URL and access token
    """
    url = None
    token = None

    # Try reading from config file
    for filename in (
        os.path.join(os.path.expanduser("~"), ".simvue.ini"),
        "simvue.ini",
    ):
        with contextlib.suppress(Exception):
            config = configparser.ConfigParser()
            config.read(filename)
            token = config.get("server", "token")
            url = config.get("server", "url")

    # Try environment variables
    token = os.getenv("SIMVUE_TOKEN", token)
    url = os.getenv("SIMVUE_URL", url)

    return url, token


def get_server_version() -> int  | None:
    """
    Get the server version
    """
    url, _ = get_auth()

    with contextlib.suppress(Exception):
        response = requests.get(f"{url}/api/version")
        
        if response.status_code != 200:
            return None

        _response_json: dict[str, str] = response.json()

        if (_version_string := _response_json.get("version")):
            return int(_version_string.split(".", 1)[0])

    return None


@functools.lru_cache
def get_offline_directory() -> str | tempfile.TemporaryDirectory:
    """
    Get directory for offline cache

    This function is cached so the same directory is returned
    if a temporary directory has been created
    """
    directory: str | None = None

    for filename in (
        os.path.join(os.path.expanduser("~"), ".simvue.ini"),
        "simvue.ini",
    ):
        with contextlib.suppress(Exception):
            config = configparser.ConfigParser()
            config.read(filename)
            directory = config.get("offline", "cache")

    # If no directory is specified the user does
    # not want to keep the cache so use temporary directory
    if not directory:
        return tempfile.mkdtemp()

    os.makedirs(directory, exist_ok=True)

    return directory


def create_file(filename) -> bool:
    """
    Create an empty file
    """
    try:
        with open(filename, "w") as fh:
            fh.write("")
        return True
    except Exception as err:
        logger.error("Unable to write file %s due to: %s", filename, str(err))
        return False


def remove_file(filename):
    """
    Remove file
    """
    if os.path.isfile(filename):
        try:
            os.remove(filename)
        except Exception as err:
            logger.error("Unable to remove file %s due to: %s", filename, str(err))


def get_expiry(token):
    """
    Get expiry date from a JWT token
    """
    expiry = 0
    try:
        expiry = jwt.decode(token, options={"verify_signature": False})["exp"]
    except:
        pass
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
