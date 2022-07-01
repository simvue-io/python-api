import configparser
import os
import random
import requests
import time

class Observability(object):
    def __init__(self):
        pass

    def init(self, name, metadata={}, tags=[]):
        """
        Initialise simulation
        """
        # Try environment variables
        token = os.getenv('OBSERVABILITY_TOKEN')
        self._url = os.getenv('OBSERVABILITY_URL')

        if not token or not self._url:
            # Try config file
            try:
                config = configparser.ConfigParser()
                config.read('observability.ini')
                token = config.get('server', 'token')
                self._url = config.get('server', 'url')
            except:
                pass

        if not token or not self._url:
            return False

        self._headers = {"Authorization": "Token %s" % token}
        self._name = name
        data = {'name': name, 'metadata': metadata, 'tags': tags}
        self._start_time = time.time()

        try:
            response = requests.post('%s/simulations' % self._url, headers=self._headers, json=data)
        except:
            return False

        if response.status_code != 201:
            return False

        return True

    def metadata(self, metadata):
        """
        Add/update metadata
        """
        data = {'simulation': self._name, 'metadata': metadata}

        try:
            response = requests.put('%s/simulations' % self._url, headers=self._headers, json=data)
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
        data['simulation'] = self._name
        data['values'] = metrics
        data['time'] = time.time() - self._start_time

        try:
            response = requests.post('%s/metrics' % self._url, headers=self._headers, json=data)
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
        data['simulation'] = self._name
        data['category'] = category

        # Get presigned URL
        try:
            resp = requests.post('%s/data' % self._url, headers=self._headers, json=data)
        except:
            return False

        if 'url' in resp.json():
            # Upload file
            try:
                with open(filename, 'rb') as fh:
                    response = requests.put(resp.json()['url'], data=fh, timeout=30)
            except:
                return False

        if response.status_code != 200:
            return False

        return True
