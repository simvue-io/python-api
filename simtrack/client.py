import configparser
import hashlib
import os
import re
import requests
import socket
import subprocess
import time
import cpuinfo
import platform
import randomname

SIMTRACK_INIT_MISSING = 'initialize a run using init() first'

def get_gpu_info():
    try:
        output = subprocess.check_output(["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv"])
        lines = output.split(b'\n')
        tokens = lines[1].split(b', ')
    except Exception:
        return {'name': '', 'driver_version': ''}

    return {'name': tokens[0].decode(), 'driver_version': tokens[1].decode()}

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
    except Exception:
        pass

    return None

class Simtrack(object):
    def __init__(self):
        self._name = None

    def __enter__(self):
        return self

    def __exit__(self, type, value, tb):
        if self._name:
            self.set_status('completed')

    def init(self, name=None, metadata={}, tags=[], description=None, folder='/'):
        """
        Initialise a run
        """
        self._suppress_errors = False
        self._status = None

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
  
        if not name:
            name = randomname.get_name()

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
        self._start_time = time.time()

        data = {'name': name,
                'metadata': metadata,
                'tags': tags}

        if description:
            data['description'] = description

        cpu = cpuinfo.get_cpu_info()
        gpu = get_gpu_info()
        
        data['system'] = {}
        data['system']['cwd'] = os.getcwd()
        data['system']['hostname'] = socket.gethostname()
        data['system']['platform'] = {}
        data['system']['platform']['system'] = platform.system()
        data['system']['platform']['release'] = platform.release()
        data['system']['platform']['version'] = platform.version() 
        data['system']['cpu'] = {}
        data['system']['cpu']['arch'] = cpu['arch_string_raw']
        data['system']['cpu']['processor'] = cpu['brand_raw']
        data['system']['gpu'] = {}
        data['system']['gpu']['name'] = gpu['name']
        data['system']['gpu']['driver'] = gpu['driver_version']

        if not folder.startswith('/'):
            raise RuntimeError('the folder must begin with /')

        data['folder'] = folder

        t1 = time.time()
        try:
            response = requests.post('%s/api/runs' % self._url, headers=self._headers, json=data)
        except Exception:
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
        except Exception:
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

        if self._status is not None:
            raise RuntimeError('Cannot log metrics after run has ended')

        if not isinstance(metrics, dict) and not self._suppress_errors:
            raise RuntimeError('Metrics must be a dict')

        data = {}
        data['run'] = self._name
        data['values'] = metrics
        data['time'] = time.time() - self._start_time

        try:
            response = requests.post('%s/api/metrics' % self._url, headers=self._headers, json=data, timeout=timeout)
        except Exception:
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
        except Exception:
            return False

        if 'url' in resp.json():
            # Upload file
            try:
                with open(filename, 'rb') as fh:
                    response = requests.put(resp.json()['url'], data=fh, timeout=30)
                    if response.status_code != 200:
                        return False
            except Exception:
                return False

        return True

    def set_status(self, status):
        """
        Set run status
        """
        if status not in ('completed', 'failed', 'deleted'):
            raise RuntimeError('invalid status')

        data = {'name': self._name, 'status': status}
        self._status = status

        try:
            response = requests.put('%s/api/runs' % self._url, headers=self._headers, json=data)
        except Exception:
            return False

        if response.status_code == 200:
            return True

        return False

    def set_folder_details(self, path, metadata={}, tags=[], description=None):
        """
        Add metadata to the specified folder
        """
        if not isinstance(metadata, dict):
            raise RuntimeError('metadata must be a dict')

        if not isinstance(tags, list):
            raise RuntimeError('tags must be a list')

        data = {'path': path}

        if metadata:
            data['metadata'] = metadata

        if tags:
            data['tags'] = tags

        if description:
            data['description'] = description

        try:
            response = requests.put('%s/api/folders' % self._url, headers=self._headers, json=data)
        except Exception:
            return False

        if response.status_code == 200:
            return True

        return False

    def add_alert(self, name, type, metric, frequency, window, threshold=None, range_low=None, range_high=None):
        """
        Creates an alert with the specified name (if it doesn't exist) and applies it to the current run
        """
        if type not in ('is below', 'is above', 'is outside range', 'is inside range'):
            raise RuntimeError('alert type invalid')

        if type in ('is below', 'is above') and threshold is None:
            raise RuntimeError('threshold must be defined for the specified alert type')

        if type in ('is outside range', 'is inside range') and (range_low is None or range_high is None):
            raise RuntimeError('range_low and range_high must be defined for the specified alert type')

        alert = {'name': name,
                'type': type,
                'metric': metric,
                'frequency': frequency,
                'window': window}

        if threshold is not None:
            alert['threshold'] = threshold
        elif range_low is not None and range_high is not None:
            alert['range_low'] = range_low
            alert['range_high'] = range_high

        try:
            response = requests.post('%s/api/alerts' % self._url, headers=self._headers, json=alert)
        except Exception:
            return False

        if response.status_code != 200 and response.status_code != 409:
            raise RuntimeError('unable to create alert')

        data = {'name': self._name, 'alert': name}

        try:
            response = requests.put('%s/api/runs' % self._url, headers=self._headers, json=data)
        except Exception:
            return False

        if response.status_code == 200:
            return True
