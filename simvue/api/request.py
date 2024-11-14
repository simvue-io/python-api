"""
Simvue API Connection
=====================

Provides methods for interacting with a Simvue server which include retry
policies. In cases where JSON is the expected form the data is firstly converted
to a JSON string
"""

import copy
import json
import typing
import http

import requests
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)
from simvue.utilities import parse_validation_response

DEFAULT_API_TIMEOUT = 10
RETRY_MULTIPLIER = 1
RETRY_MIN = 4
RETRY_MAX = 10
RETRY_STOP = 5
RETRY_STATUS_CODES = (
    http.HTTPStatus.BAD_REQUEST,
    http.HTTPStatus.SERVICE_UNAVAILABLE,
    http.HTTPStatus.GATEWAY_TIMEOUT,
    http.HTTPStatus.REQUEST_TIMEOUT,
    http.HTTPStatus.TOO_EARLY,
)
RETRY_EXCEPTION_TYPES = (RuntimeError, requests.exceptions.ConnectionError)


def set_json_header(headers: dict[str, str]) -> dict[str, str]:
    """
    Return a copy of the headers with Content-Type set to
    application/json
    """
    headers = copy.deepcopy(headers)
    headers["Content-Type"] = "application/json"
    return headers


def is_retryable_exception(exception: Exception) -> bool:
    """Returns if the given exception should lead to a retry being called"""
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
    url: str, headers: dict[str, str], data: typing.Any, is_json: bool = True
) -> requests.Response:
    """HTTP POST with retries

    Parameters
    ----------
    url : str
        URL to post to
    headers : dict[str, str]
        headers for the post request
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
        data_sent: typing.Union[str, dict[str, typing.Any]] = json.dumps(data)
        headers = set_json_header(headers)
    else:
        data_sent = data

    response = requests.post(
        url, headers=headers, data=data_sent, timeout=DEFAULT_API_TIMEOUT
    )

    if response.status_code == http.HTTPStatus.UNPROCESSABLE_ENTITY:
        _parsed_response = parse_validation_response(response.json())
        raise ValueError(
            f"Validation error for '{url}' [{response.status_code}]:\n{_parsed_response}"
        )

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
    data: dict[str, typing.Any],
    is_json: bool = True,
    timeout: int = DEFAULT_API_TIMEOUT,
) -> requests.Response:
    """HTTP PUT with retries

    Parameters
    ----------
    url : str
        URL to put to
    headers : dict[str, str]
        headers for the post request
    data : dict[str, typing.Any]
        data to put
    is_json : bool, optional
        send as JSON string, by default True
    timeout : int, optional
        timeout of request, by default DEFAULT_API_TIMEOUT

    Returns
    -------
    requests.Response
        response from executing PUT
    """
    if is_json:
        data_sent: typing.Union[str, dict[str, typing.Any]] = json.dumps(data)
        headers = set_json_header(headers)
    else:
        data_sent = data

    response = requests.put(url, headers=headers, data=data_sent, timeout=timeout)

    response.raise_for_status()

    return response


@retry(
    wait=wait_exponential(multiplier=RETRY_MULTIPLIER, min=RETRY_MIN, max=RETRY_MAX),
    retry=retry_if_exception(is_retryable_exception),
    stop=stop_after_attempt(RETRY_STOP),
    reraise=True,
)
def get(
    url: str, headers: dict[str, str], timeout: int = DEFAULT_API_TIMEOUT
) -> requests.Response:
    """HTTP GET

    Parameters
    ----------
    url : str
        URL to put to
    headers : dict[str, str]
        headers for the post request
    timeout : int, optional
        timeout of request, by default DEFAULT_API_TIMEOUT

    Returns
    -------
    requests.Response
        response from executing GET
    """
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()

    return response


@retry(
    wait=wait_exponential(multiplier=RETRY_MULTIPLIER, min=RETRY_MIN, max=RETRY_MAX),
    retry=retry_if_exception(is_retryable_exception),
    stop=stop_after_attempt(RETRY_STOP),
    reraise=True,
)
def delete(
    url: str, headers: dict[str, str], timeout: int = DEFAULT_API_TIMEOUT
) -> requests.Response:
    """HTTP DELETE

    Parameters
    ----------
    url : str
        URL to put to
    headers : dict[str, str]
        headers for the post request
    timeout : int, optional
        timeout of request, by default DEFAULT_API_TIMEOUT

    Returns
    -------
    requests.Response
        response from executing DELETE
    """
    response = requests.delete(url, headers=headers, timeout=timeout)
    response.raise_for_status()

    return response


def get_json_from_response(
    expected_status: list[int],
    scenario: str,
    response: requests.Response,
) -> typing.Union[dict, list]:
    try:
        json_response = response.json()
        json_response = json_response or {}
    except json.JSONDecodeError:
        json_response = None

    error_str = f"{scenario} failed "

    if (_status_code := response.status_code) in expected_status:
        if json_response is not None:
            return json_response
        details = "could not request JSON response"
    else:
        error_str += f"with status {_status_code}"
        details = (json_response or {}).get("details")

    try:
        txt_response = response.text
    except UnicodeDecodeError:
        txt_response = None

    if details:
        error_str += f": {details}"
    elif txt_response:
        error_str += f": {txt_response}"

    raise RuntimeError(error_str)
