import logging
import requests

from .utilities import get_auth

logger = logging.getLogger(__name__)

UPLOAD_TIMEOUT = 30
DEFAULT_API_TIMEOUT = 10

class Remote(object):
    """
    Class which interacts with Simvue REST API
    """
    def __init__(self, name, suppress_errors=False):
        self._name = name
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
            response = requests.post(f"{self._url}/api/runs",
                                     headers=self._headers,
                                     json=data,
                                     timeout=DEFAULT_API_TIMEOUT)
        except requests.exceptions.RequestException as err:
            self._error(f"Exception creating run: {str(err)}")
            return False

        if response.status_code == 409:
            self._error(f"Duplicate run, name {data['name']} already exists")
        elif response.status_code != 200:
            self._error(f"Got status code {response.status_code} when creating run")
            return False

        return True

    def update(self, data):
        """
        Update metadata, tags or status
        """
        try:
            response = requests.put(f"{self._url}/api/runs",
                                    headers=self._headers,
                                    json=data,
                                    timeout=DEFAULT_API_TIMEOUT)
        except requests.exceptions.RequestException as err:
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
            response = requests.put(f"{self._url}/api/folders",
                                    headers=self._headers,
                                    json=data,
                                    timeout=DEFAULT_API_TIMEOUT)
        except requests.exceptions.RequestException as err:
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
            response = requests.post(f"{self._url}/api/data",
                                 headers=self._headers,
                                 json=data,
                                 timeout=DEFAULT_API_TIMEOUT)
        except requests.exceptions.RequestException as err:
            self._error(f"Got exception when uploading file {data['name']} to object storage: {str(err)}")
            return False

        if response.status_code == 409:
            return True

        if response.status_code != 200:
            self._error(f"Got status code {response.status_code} when registering file {data['name']}")
            return False

        if 'url' in response.json():
            try:
                with open(data['originalPath'], 'rb') as fh:
                    response = requests.put(response.json()['url'],
                                            data=fh,
                                            timeout=UPLOAD_TIMEOUT)
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
            response = requests.post(f"{self._url}/api/alerts",
                                     headers=self._headers,
                                     json=data,
                                     timeout=DEFAULT_API_TIMEOUT)
        except requests.exceptions.RequestException as err:
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
            response = requests.post(f"{self._url}/api/metrics",
                                     headers=self._headers_mp,
                                     data=data,
                                     timeout=DEFAULT_API_TIMEOUT)
        except requests.exceptions.RequestException as err:
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
            response = requests.post(f"{self._url}/api/events",
                                     headers=self._headers_mp,
                                     data=data,
                                     timeout=DEFAULT_API_TIMEOUT)
        except requests.exceptions.RequestException as err:
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
            response = requests.put(f"{self._url}/api/runs/heartbeat",
                                    headers=self._headers,
                                    json={'name': self._name},
                                    timeout=DEFAULT_API_TIMEOUT)
        except requests.exceptions.RequestException as err:
            self._error(f"Exception creating run: {str(err)}")
            return False

        if response.status_code == 200:
            return True

        self._error(f"Got status code {response.status_code} when sending heartbeat")
        return False
