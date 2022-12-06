import logging
import time
import requests

from .api import post, put
from .utilities import get_auth, get_expiry

logger = logging.getLogger(__name__)

UPLOAD_TIMEOUT = 30
DEFAULT_API_TIMEOUT = 10

class Remote(object):
    """
    Class which interacts with Simvue REST API
    """
    def __init__(self, name, uuid, suppress_errors=False):
        self._name = name
        self._uuid = uuid
        self._suppress_errors = suppress_errors
        self._url, self._token = get_auth()
        self._headers = {"Authorization": f"Bearer {self._token}"}
        self._headers_mp = self._headers.copy()
        self._headers_mp['Content-Type'] = 'application/msgpack'

    def _error(self, message):
        """
        Raise an exception if necessary and log error
        """
        if not self._suppress_errors:
            raise RuntimeError(message)
        else:
            logger.error(message)

    def create_run(self, data):
        """
        Create a run
        """
        try:
            response = post(f"{self._url}/api/runs", self._headers, data)
        except Exception as err:
            self._error(f"Exception creating run: {str(err)}")
            return False

        if response.status_code == 409:
            self._error(f"Duplicate run, name {data['name']} already exists")
        elif response.status_code != 200:
            self._error(f"Got status code {response.status_code} when creating run")
            return False

        if 'name' in response.json():
            self._name = response.json()['name']

        return self._name

    def update(self, data):
        """
        Update metadata, tags or status
        """
        try:
            response = put(f"{self._url}/api/runs", self._headers, data)
        except Exception as err:
            self._error(f"Exception creating updating run: {str(err)}")
            return False

        if response.status_code == 200:
            return True

        self._error(f"Got status code {response.status_code} when updating run")
        return False

    def set_folder_details(self, data):
        """
        Set folder details
        """
        try:
            response = put(f"{self._url}/api/folders", self._headers, data)
        except Exception as err:
            self._error(f"Exception setting folder details: {err}")
            return False

        if response.status_code == 200:
            return True

        self._error(f"Got status code {response.status_code} when updating folder details")
        return False

    def save_file(self, data):
        """
        Save file
        """
        # Get presigned URL
        try:
            response = post(f"{self._url}/api/data", self._headers, data)
        except Exception as err:
            self._error(f"Got exception when preparing to upload file {data['name']} to object storage: {str(err)}")
            return False

        if response.status_code == 409:
            return True

        if response.status_code != 200:
            self._error(f"Got status code {response.status_code} when registering file {data['name']}")
            return False

        if 'url' in response.json():
            url = response.json()['url']
            try:
                with open(data['originalPath'], 'rb') as fh:
                    response = put(url, {}, fh, is_json=False, timeout=UPLOAD_TIMEOUT)
                    if response.status_code != 200:
                        self._error(f"Got status code {response.status_code} when uploading file {data['name']} to object storage")
                        return None
            except Exception as err:
                self._error(f"Got exception when uploading file {data['name']} to object storage: {str(err)}")
                return None

        return True

    def add_alert(self, data):
        """
        Add an alert
        """
        try:
            response = post(f"{self._url}/api/alerts", self._headers, data)
        except Exception as err:
            self._error(f"Got exception when creating an alert: {str(err)}")
            return False

        if response.status_code in (200, 409):
            return True

        self._error(f"Got status code {response.status_code} when creating alert")
        return False

    def send_metrics(self, data):
        """
        Send metrics
        """
        try:
            response = post(f"{self._url}/api/metrics", self._headers_mp, data, is_json=False)
        except Exception as err:
            self._error(f"Exception sending metrics: {str(err)}")
            return False

        if response.status_code == 200:
            return True

        self._error(f"Got status code {response.status_code} when sending metrics")
        return False

    def send_event(self, data):
        """
        Send events
        """
        try:
            response = post(f"{self._url}/api/events", self._headers_mp, data, is_json=False)
        except Exception as err:
            self._error(f"Exception sending event: {str(err)}")
            return False

        if response.status_code == 200:
            return True

        self._error(f"Got status code {response.status_code} when sending events")
        return False

    def send_heartbeat(self):
        """
        Send heartbeat
        """
        try:
            response = put(f"{self._url}/api/runs/heartbeat", self._headers, {'name': self._name})
        except Exception as err:
            self._error(f"Exception creating run: {str(err)}")
            return False

        if response.status_code == 200:
            return True

        self._error(f"Got status code {response.status_code} when sending heartbeat")
        return False

    def check_token(self):
        """
        Check token
        """
        if time.time() - get_expiry(self._token) > 0:
            self._error("Token has expired")
