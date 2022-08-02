import configparser
import hashlib
import os
import random
import re
import requests
import time

SIMTRACK_INIT_MISSING = 'initialize a run using init(name, metadata, tags) first'

def calculate_sha256(filename):
    """
    Calculate sha256 checksum of the specified file
    """
    sha256_hash = hashlib.sha256()
    try:
        with open(filename, "rb") as f:
            for byte_block in iter(lambda: f.read(4096),b""):
                sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
    except:
        pass

    return None

class Simtrack(object):
    def __init__(self):
        self._name = None

    def init(self, name, metadata={}, tags=[]):
        """
        Initialise a run
        """
        self._suppress_errors = False

        # Try environment variables
        token = os.getenv('SIMTRACK_TOKEN')
        self._url = os.getenv('SIMTRACK_URL')

        if not token or not self._url:
            # Try config file
            try:
                config = configparser.ConfigParser()
                config.read('simtrack.ini')
                token = config.get('server', 'token')
                self._url = config.get('server', 'url')
            except:
                pass

        if not token or not self._url:
            raise RuntimeError('Unable to get URL and token from environment variables or config file')

        if not re.match(r'^[a-zA-Z0-9\-\_\s\/\.:]+$', name):
            raise RuntimeError('specified name is invalid')

        if not isinstance(tags, list):
            raise RuntimeError('tags must be a list')

        if not isinstance(metadata, dict):
            raise RuntimeError('metadata must be a dict')

        self._headers = {"Authorization": "Bearer %s" % token}
        self._name = name
        data = {'name': name, 'metadata': metadata, 'tags': tags}
        self._start_time = time.time()

        try:
            response = requests.post('%s/api/runs' % self._url, headers=self._headers, json=data)
        except:
            return False

        if response.status_code == 409:
            raise RuntimeError('Run with name %s already exists' % name)

        if response.status_code != 200:
            raise RuntimeError('Unable to create run due to: %s', response.text)

        return True

    def suppress_errors(self, value):
        """
        Specify if errors should raise exceptions or not
        """
        if not isinstance(value, bool):
            raise RuntimeError('value must be boolean')

        self._suppress_errors = value

    def metadata(self, metadata):
        """
        Add/update metadata
        """
        if not self._name:
            raise RuntimeError(SIMTRACK_INIT_MISSING)

        if not isinstance(metadata, dict):
            raise RuntimeError('metadata must be a dict')

        data = {'run': self._name, 'metadata': metadata}

        try:
            response = requests.put('%s/runs' % self._url, headers=self._headers, json=data)
        except:
            return False

        if response.status_code == 200:
            return True

        return False

    def log(self, metrics, timeout=10):
        """
        Write metrics
        """
        if not self._name:
            raise RuntimeError(SIMTRACK_INIT_MISSING)

        if not isinstance(metrics, dict) and not self._suppress_errors:
            raise RuntimeError('Metrics must be a dict')

        data = {}
        data['run'] = self._name
        data['values'] = metrics
        data['time'] = time.time() - self._start_time

        try:
            response = requests.post('%s/api/metrics' % self._url, headers=self._headers, json=data, timeout=timeout)
        except Exception as err:
            return False

        if response.status_code == 200:
            return True
 
        return False

    def save(self, filename, category):
        """
        Upload file
        """
        if not self._name:
            raise RuntimeError(SIMTRACK_INIT_MISSING)

        if not os.path.isfile(filename):
            raise RuntimeError('File %s does not exist' % filename)

        data = {}
        data['name'] = os.path.basename(filename)
        data['run'] = self._name
        data['category'] = category
        data['checksum'] = calculate_sha256(filename)

        # Get presigned URL
        try:
            resp = requests.post('%s/api/data' % self._url, headers=self._headers, json=data)
        except:
            return False

        if 'url' in resp.json():
            # Upload file
            try:
                with open(filename, 'rb') as fh:
                    response = requests.put(resp.json()['url'], data=fh, timeout=30)
                    if response.status_code != 200:
                        return False
            except:
                return False

        return True
