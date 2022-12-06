import requests
from tenacity import retry, wait_exponential, stop_after_attempt

DEFAULT_API_TIMEOUT = 10
RETRY_MULTIPLIER = 1
RETRY_MIN = 4
RETRY_MAX = 10
RETRY_STOP = 5

@retry(wait=wait_exponential(multiplier=RETRY_MULTIPLIER, min=RETRY_MIN, max=RETRY_MAX),
                             stop=stop_after_attempt(RETRY_STOP))
def post(url, headers, data, is_json=True):
    """
    HTTP POST with retries
    """
    if is_json:
        response = requests.post(url, headers=headers, json=data, timeout=DEFAULT_API_TIMEOUT)
    else:
        response = requests.post(url, headers=headers, data=data, timeout=DEFAULT_API_TIMEOUT)

    return response

@retry(wait=wait_exponential(multiplier=RETRY_MULTIPLIER, min=RETRY_MIN, max=RETRY_MAX),
                             stop=stop_after_attempt(RETRY_STOP))
def put(url, headers, data, is_json=True, timeout=DEFAULT_API_TIMEOUT):
    """
    HTTP PUT with retries
    """
    if is_json:
        response = requests.put(url, headers=headers, json=data, timeout=timeout)
    else:
        response = requests.put(url, headers=headers, data=data, timeout=timeout)

    return response
