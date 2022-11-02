import logging
import requests

from .utilities import get_auth

logger = logging.getLogger(__name__)

class Remote(object):
    """
    Class which interacts with Simvue REST API
    """
    def __init__(self, name, suppress_errors=False):
        self._name = name
        self._suppress_errors = suppress_errors
        self._url, self._token = get_auth()
        self._headers = {"Authorization": f"Bearer {self._token}"}

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
            response = requests.post(f"{self._url}/api/runs", headers=self._headers, json=data)
        except requests.exceptions.RequestException:
            return False

        if response.status_code != 200:
            self._error('Unable to reconnect to run')
            return False

        return True

    def update(self, data):
        """
        Update metadata, tags or status
        """
        try:
            response = requests.put(f"{self._url}/api/runs", headers=self._headers, json=data)
        except requests.exceptions.RequestException:
            pass

        if response.status_code == 200:
            return True

        return False

    def set_folder_details(self, data):
        """
        Set folder details
        """
        try:
            response = requests.put(f"{self._url}/api/folders", headers=self._headers, json=data)
        except requests.exceptions.RequestException:
            pass

        if response.status_code == 200:
            return True

        return False

    def add_alert(self, data):
        """
        Add an alert
        """
        try:
            response = requests.put(f"{self._url}/api/runs", headers=self._headers, json=data)
        except requests.exceptions.RequestException:
            pass

        if response.status_code == 200:
            return True

        return False
