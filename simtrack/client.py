import configparser
import hashlib
import os
import random
import requests
import time

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
        pass

    def init(self, name, metadata={}, tags=[]):
        """
        Initialise a run
        """
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
            return False

        self._headers = {"Authorization": "Bearer %s" % token}
        self._name = name
        data = {'name': name, 'metadata': metadata, 'tags': tags}
        self._start_time = time.time()

        try:
            response = requests.post('%s/api/runs' % self._url, headers=self._headers, json=data)
        except:
            return False

        if response.status_code != 201:
            return False

        return True

    def metadata(self, metadata):
        """
        Add/update metadata
        """
        data = {'run': self._name, 'metadata': metadata}

        try:
            response = requests.put('%s/runs' % self._url, headers=self._headers, json=data)
        except:
            return False

        if response.status_code == 200:
            return True

        return False

    def log(self, metrics):
        """
        Write metrics
        """
        data = {}
        data['run'] = self._name
        data['values'] = metrics
        data['time'] = time.time() - self._start_time

        try:
            response = requests.post('%s/api/metrics' % self._url, headers=self._headers, json=data)
        except Exception as err:
            return False

        if response.status_code == 201:
            return True

        return False

    def save(self, filename, category):
        """
        Upload file
        """
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
