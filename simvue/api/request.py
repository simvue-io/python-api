"""Simvue API Connection.

Provides methods for interacting with a Simvue server which include retry
policies. In cases where JSON is the expected form the data is firstly converted
to a JSON string
"""

from collections.abc import Generator
import copy
import http
import json as json_module
import logging
import typing

import requests
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from simvue.utilities import parse_validation_response

logger = logging.getLogger(__name__)

DEFAULT_API_TIMEOUT = 10
RETRY_MULTIPLIER = 1
RETRY_MIN = 4
RETRY_MAX = 10
RETRY_STOP = 5
MAX_ENTRIES_PER_PAGE: int = 100
RETRY_STATUS_CODES = (
    http.HTTPStatus.BAD_REQUEST,
    http.HTTPStatus.SERVICE_UNAVAILABLE,
    http.HTTPStatus.GATEWAY_TIMEOUT,
    http.HTTPStatus.REQUEST_TIMEOUT,
    http.HTTPStatus.TOO_EARLY,
)
RETRY_EXCEPTION_TYPES = (RuntimeError, requests.exceptions.ConnectionError)


def set_json_header(headers: dict[str, str]) -> dict[str, str]:
    """Return a copy of the headers with Content-Type set to application/json."""
    headers = copy.deepcopy(headers)
    headers["Content-Type"] = "application/json"
    return headers


def is_retryable_exception(exception: BaseException) -> bool:
    """Return if the given exception should lead to a retry being called."""
    if isinstance(exception, requests.HTTPError):
        return exception.response.status_code in RETRY_STATUS_CODES

    return isinstance(exception, RETRY_EXCEPTION_TYPES)


@retry(
    wait=wait_exponential(multiplier=RETRY_MULTIPLIER, min=RETRY_MIN, max=RETRY_MAX),
    stop=stop_after_attempt(RETRY_STOP),
    retry=retry_if_exception(is_retryable_exception),
    reraise=True,
)
def post(
    url: str,
    headers: dict[str, str],
    params: dict[str, str],
    data: object,
    *,
    is_json: bool = True,
    timeout: int | None = None,
    files: dict[str, typing.Any] | None = None,
) -> requests.Response:
    """HTTP POST with retries.

    Parameters
    ----------
    url : str
        URL to post to
    headers : dict[str, str]
        headers for the post request
    params : dict[str, str]
        query parameters for the post request
    data : dict[str, typing.Any]
        data to post
    is_json : bool, optional
        send as JSON string, by default True

    Returns
    -------
    requests.Response
        response from post to server

    """
    if is_json:
        data_sent: str | dict[str, typing.Any] | object = json_module.dumps(data)
        headers = set_json_header(headers)
    else:
        data_sent = data

    response = requests.post(
        url,
        headers=headers,
        params=params,
        data=data_sent,
        timeout=timeout,
        files=files,
    )

    if response.status_code == http.HTTPStatus.UNPROCESSABLE_ENTITY:
        _parsed_response = parse_validation_response(response.json())
        _out_msg: str = (
            f"Validation error for '{url}' [{response.status_code}]:"
            f"\n{_parsed_response}"
        )
        raise ValueError(_out_msg)

    return response


@retry(
    wait=wait_exponential(multiplier=RETRY_MULTIPLIER, min=RETRY_MIN, max=RETRY_MAX),
    retry=retry_if_exception(is_retryable_exception),
    stop=stop_after_attempt(RETRY_STOP),
    reraise=True,
)
def put(
    url: str,
    headers: dict[str, str],
    data: dict[str, typing.Any] | None = None,
    json: dict[str, typing.Any] | None = None,
    *,
    is_json: bool = True,
    timeout: int = DEFAULT_API_TIMEOUT,
) -> requests.Response:
    """HTTP PUT with retries.

    Parameters
    ----------
    url : str
        URL to put to
    headers : dict[str, str]
        headers for the post request
    data : dict[str, typing.Any]
        data to put
    json : dict | None
        json data to send
    is_json : bool, optional
        send as JSON string, by default True
    timeout : int, optional
        timeout of request, by default DEFAULT_API_TIMEOUT

    Returns
    -------
    requests.Response
        response from executing PUT
    """
    if is_json and data:
        data_sent: str | dict[str, typing.Any] | object = json_module.dumps(data)
        headers = set_json_header(headers)
    else:
        data_sent = data

    logger.debug("PUT: %s\n\tdata=%s\n\tjson=%s", url, data_sent, json)

    return requests.put(
        url, headers=headers, data=data_sent, timeout=timeout, json=json
    )


@retry(
    wait=wait_exponential(multiplier=RETRY_MULTIPLIER, min=RETRY_MIN, max=RETRY_MAX),
    retry=retry_if_exception(is_retryable_exception),
    stop=stop_after_attempt(RETRY_STOP),
    reraise=True,
)
def get(
    url: str,
    headers: dict[str, str] | None = None,
    params: dict[str, str | int | float | None | list[str]] | None = None,
    timeout: int = DEFAULT_API_TIMEOUT,
    json: dict[str, typing.Any] | None = None,
) -> requests.Response:
    """HTTP GET.

    Parameters
    ----------
    url : str
        URL to put to
    headers : dict[str, str]
        headers for the post request
    timeout : int, optional
        timeout of request, by default DEFAULT_API_TIMEOUT
    json : dict[str, Any] | None, optional
        any json to send in request

    Returns
    -------
    requests.Response
        response from executing GET
    """
    logger.debug("GET: %s\n\tparams=%s", url, params)
    return requests.get(url, headers=headers, timeout=timeout, params=params, json=json)


@retry(
    wait=wait_exponential(multiplier=RETRY_MULTIPLIER, min=RETRY_MIN, max=RETRY_MAX),
    retry=retry_if_exception(is_retryable_exception),
    stop=stop_after_attempt(RETRY_STOP),
    reraise=True,
)
def delete(
    url: str,
    headers: dict[str, str],
    timeout: int = DEFAULT_API_TIMEOUT,
    params: dict[str, typing.Any] | None = None,
) -> requests.Response:
    """HTTP DELETE.

    Parameters
    ----------
    url : str
        URL to put to
    headers : dict[str, str]
        headers for the post request
    timeout : int, optional
        timeout of request, by default DEFAULT_API_TIMEOUT
    params : dict, optional
        parameters for deletion

    Returns
    -------
    requests.Response
        response from executing DELETE
    """
    logger.debug("DELETE: %s\n\tparams=%s", url, params)
    return requests.delete(url, headers=headers, timeout=timeout, params=params)


def get_json_from_response(
    expected_status: list[http.HTTPStatus],
    scenario: str,
    response: requests.Response,
    *,
    allow_parse_failure: bool = False,
    expected_type: type[dict[str, object] | list[object]] = dict,
) -> dict[str, object] | list[object]:
    """Retrieve the JSON data from a server response.

    Parameters
    ----------
    expected_status : list[http.HTTPStatus]
        list of valid response status codes.
    scenario : str
        description of the scenario.
    response : requests.Response
        the response object to process
    allow_parse_failure : bool, optional
        whether the attempt to parse failure response
        is allowed to itself fail, default False.
    expected_type : type[dict | list], optional
        the expected response type, default dict.

    Returns
    -------
    list | dict
        the response information.
    """
    try:
        json_response: list[dict[str, object]] | dict[str, object] | None = (
            response.json()
        )
        json_response = json_response or ({} if expected_type is dict else [])
        decode_error = ""
    except json_module.JSONDecodeError as e:
        json_response = {} if allow_parse_failure else None
        decode_error = f"{e}"

    error_str = f"{scenario} failed for url '{response.url}'"
    details: str | None = None

    if (_status_code := response.status_code) in expected_status:
        if json_response is None:
            details = f"could not request JSON response: {decode_error}"
        elif not isinstance(json_response, expected_type):
            details = f"expected type '{expected_type.__name__}' but got '{type(json_response).__name__}'"
        else:
            return json_response
    elif isinstance(json_response, dict):
        error_str += f" with status {_status_code}"
        details = (json_response or {}).get("detail")

    try:
        txt_response = response.text
    except UnicodeDecodeError:
        txt_response = None

    if details:
        error_str += f": {details}"
    elif txt_response:
        error_str += f": {txt_response}"

    raise RuntimeError(error_str)


def get_paginated(
    url: str,
    headers: dict[str, str] | None = None,
    timeout: int = DEFAULT_API_TIMEOUT,
    json: dict[str, typing.Any] | None = None,
    offset: int | None = None,
    count: int | None = None,
    **params,
) -> Generator[requests.Response]:
    """Paginate results of a server query.

    Parameters
    ----------
    url : str
        URL to put to
    headers : dict[str, str]
        headers for the post request
    timeout : int, optional
        timeout of request, by default DEFAULT_API_TIMEOUT
    json : dict[str, Any] | None, optional
        any json to send in request

    Yield
    -----
    requests.Response
        server response
    """
    _offset: int = offset or 0

    # Restrict the number of entries retrieved to be paginated,
    # if the count requested is below page limit use this value
    # else if undefined or greater than the page limit use the limit
    _request_count: int = min(count or MAX_ENTRIES_PER_PAGE, MAX_ENTRIES_PER_PAGE)

    try:
        while (
            _response := get(
                url=url,
                headers=headers,
                params=(params or {}) | {"count": _request_count, "start": _offset},
                timeout=timeout,
                json=json,
            )
        ).json():
            yield _response
            _offset += MAX_ENTRIES_PER_PAGE

            if (count and _offset > count) or (
                _response.json().get("count", 0) < _offset
            ):
                break
    except json_module.JSONDecodeError:
        raise RuntimeError(
            f"[{_response.status_code}] Failed to retrieve content from server: {_response.text}"
        )
