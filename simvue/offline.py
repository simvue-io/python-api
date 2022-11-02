import json
import logging
import os
import time

from .utilities import get_offline_directory, get_directory_name

logger = logging.getLogger(__name__)

class Offline(object):
    """
    Class for offline runs
    """
    def __init__(self, name, suppress_errors=False):
        self._name = name
        self._directory = os.path.join(get_offline_directory(), get_directory_name(name))
        self._suppress_errors = suppress_errors

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
            os.mkdir(self._directory)
        except:
            pass
        
        filename = f"{self._directory}/run.json"
        with open(filename, 'w') as fh:
            json.dump(data, fh)

        status = data['status']
        filename = f"{self._directory}/{status}"
        with open(filename, 'w') as fh:
            fh.write('')

        return True

    def update(self, data):
        """
        Update metadata, tags or status
        """
        unique_id = time.time()
        filename = f"{self._directory}/update-{unique_id}.json"
        with open(filename, 'w') as fh:
            json.dump(data, fh)

        if 'status' in data:
            status = data['status']
            filename = f"{self._directory}/{status}"
            with open(filename, 'w') as fh:
                fh.write('')

            if status == 'completed':
                status_running = f"{self._directory}/running"
                if os.path.isfile(status_running):
                    os.remove(status_running)

        return True

    def set_folder_details(self, data):
        """
        Set folder details
        """
        unique_id = time.time()
        filename = f"{self._directory}/folder-{unique_id}.json"
        with open(filename, 'w') as fh:
            json.dump(data, fh)

        return True

    def save_file(self, data):
        """
        Save file
        """
        unique_id = time.time()
        filename = f"{self._directory}/file-{unique_id}.json"
        with open(filename, 'w') as fh:
            json.dump(data, fh)

        return True

    def add_alert(self, data):
        """
        Add an alert
        """
        unique_id = time.time()
        filename = f"{self._directory}/alert-{unique_id}.json"
        with open(filename, 'w') as fh:
            json.dump(data, fh)

        return True
