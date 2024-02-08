import copy
import json
import requests
from tenacity import retry, wait_exponential, stop_after_attempt

DEFAULT_API_TIMEOUT = 10
RETRY_MULTIPLIER = 1
RETRY_MIN = 4
RETRY_MAX = 10
RETRY_STOP = 5

def set_json_header(headers):
    """
    Return a copy of the headers with Content-Type set to
    application/json
    """
    headers = copy.deepcopy(headers)
    headers['Content-Type'] = 'application/json'
    return headers

@retry(wait=wait_exponential(multiplier=RETRY_MULTIPLIER, min=RETRY_MIN, max=RETRY_MAX),
                             stop=stop_after_attempt(RETRY_STOP), reraise=True)
def post(url, headers, data, is_json=True):
    """
    HTTP POST with retries
    """
    if is_json:
        data = json.dumps(data)
        headers = set_json_header(headers)
    response = requests.post(url, headers=headers, data=data, timeout=DEFAULT_API_TIMEOUT)
    
    if response.status_code in (401, 403):
        raise Exception(f'Authorization error [{response.status_code}]: {response.text}')
        
    if response.status_code not in (200, 201, 409):
        raise Exception(f'HTTP error [{response.status_code}]: {response.text}')

    return response

@retry(wait=wait_exponential(multiplier=RETRY_MULTIPLIER, min=RETRY_MIN, max=RETRY_MAX),
                             stop=stop_after_attempt(RETRY_STOP))
def put(url, headers, data, is_json=True, timeout=DEFAULT_API_TIMEOUT):
    """
    HTTP PUT with retries
    """
    if is_json:
        data = json.dumps(data)
        headers = set_json_header(headers)
    response = requests.put(url, headers=headers, data=data, timeout=timeout)
    response.raise_for_status()

    return response

def get(url, headers, timeout=DEFAULT_API_TIMEOUT):
    """
    HTTP GET
    """
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()

    return response
