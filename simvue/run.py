import configparser
import datetime
import hashlib
import logging
import mimetypes
import os
import re
import multiprocessing
import socket
import subprocess
import sys
import time as tm
import platform
import requests
import randomname

from .worker import Worker
from .simvue import Simvue
from .utilities import get_auth

INIT_MISSING = 'initialize a run using init() first'
QUEUE_SIZE = 10000
CHECKSUM_BLOCK_SIZE = 4096
UPLOAD_TIMEOUT = 30

logger = logging.getLogger(__name__)

def walk_through_files(path):
    for (dirpath, _, filenames) in os.walk(path):
        for filename in filenames:
            yield os.path.join(dirpath, filename)

def get_cpu_info():
    """
    Get CPU info
    """
    model_name = ''
    arch = ''

    try:
        info = subprocess.check_output('lscpu').decode().strip()
        for line in info.split('\n'):
            if 'Model name' in line:
                model_name = line.split(':')[1].strip()
            if 'Architecture' in line:
                arch = line.split(':')[1].strip()
    except:
        # TODO: Try /proc/cpuinfo
        pass

    return model_name, arch


def get_gpu_info():
    """
    Get GPU info
    """
    try:
        output = subprocess.check_output(["nvidia-smi",
                                          "--query-gpu=name,driver_version",
                                          "--format=csv"])
        lines = output.split(b'\n')
        tokens = lines[1].split(b', ')
    except:
        return {'name': '', 'driver_version': ''}

    return {'name': tokens[0].decode(), 'driver_version': tokens[1].decode()}


def get_system():
    """
    Get system details
    """
    cpu = get_cpu_info()
    gpu = get_gpu_info()

    system = {}
    system['cwd'] = os.getcwd()
    system['hostname'] = socket.gethostname()
    system['pythonversion'] = (f"{sys.version_info.major}."
                               f"{sys.version_info.minor}."
                               f"{sys.version_info.micro}")
    system['platform'] = {}
    system['platform']['system'] = platform.system()
    system['platform']['release'] = platform.release()
    system['platform']['version'] = platform.version()
    system['cpu'] = {}
    system['cpu']['arch'] = cpu[1]
    system['cpu']['processor'] = cpu[0]
    system['gpu'] = {}
    system['gpu']['name'] = gpu['name']
    system['gpu']['driver'] = gpu['driver_version']

    return system


def calculate_sha256(filename):
    """
    Calculate sha256 checksum of the specified file
    """
    sha256_hash = hashlib.sha256()
    try:
        with open(filename, "rb") as fd:
            for byte_block in iter(lambda: fd.read(CHECKSUM_BLOCK_SIZE), b""):
                sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
    except:
        pass

    return None


def validate_timestamp(timestamp):
    """
    Validate a user-provided timestamp
    """
    try:
        datetime.datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S.%f')
    except ValueError:
        return False

    return True


class Run(object):
    """
    Track simulation details based on token and URL
    """
    def __init__(self):
        self._name = None
        self._suppress_errors = False
        self._queue_blocking = False
        self._status = None
        self._upload_time_log = None
        self._upload_time_event = None
        self._data = []
        self._events = []
        self._step = 0
        self._queue_size = QUEUE_SIZE
        self._metrics_queue = None
        self._events_queue = None
        self._active = False
        self._url, self._token = get_auth()
        self._headers = {"Authorization": f"Bearer {self._token}"}
        self._simvue = None
        self._offline = False

    def __enter__(self):
        return self

    def __exit__(self, type, value, tb):
        if self._name and self._status == 'running':
            self.set_status('completed')

    def _start(self, reconnect=False):
        """
        Start a run
        """
        data = {'name': self._name, 'status': self._status}
        if reconnect:
            data['system'] = get_system()

            if not self._simvue.update(data):
                return False

        self._start_time = tm.time()

        self._metrics_queue = multiprocessing.Manager().Queue(maxsize=self._queue_size)
        self._events_queue = multiprocessing.Manager().Queue(maxsize=self._queue_size)
        self._worker = Worker(self._metrics_queue, self._events_queue, self._name, self._url, self._headers, self._offline)

        if multiprocessing.current_process()._parent_pid is None:
            self._worker.start()

        self._active = True

    def _error(self, message):
        """
        Raise an exception if necessary and log error
        """
        if not self._suppress_errors:
            raise RuntimeError(message)
        else:
            logger.error(message)

    def init(self, name=None, metadata={}, tags=[], description=None, folder='/', running=True, offline=False):
        """
        Initialise a run
        """
        if not name:
            name = randomname.get_name()

        if not self._token or not self._url:
            self._error('Unable to get URL and token from environment variables or config file')

        if not re.match(r'^[a-zA-Z0-9\-\_\s\/\.:]+$', name):
            self._error('specified name is invalid')

        if not isinstance(tags, list):
            self._error('tags must be a list')

        if not isinstance(metadata, dict):
            self._error('metadata must be a dict')

        self._name = name
        self._offline = offline

        if running:
            self._status = 'running'
        else:
            self._status = 'created'

        data = {'name': name,
                'metadata': metadata,
                'tags': tags,
                'system': {'cpu': {},
                           'gpu': {},
                           'platform': {}},
                'status': self._status}

        if description:
            data['description'] = description

        if not folder.startswith('/'):
            self._error('the folder must begin with /')

        data['folder'] = folder

        if self._status == 'running':
            data['system'] = get_system()

        self._simvue = Simvue(self._name, self._offline, self._suppress_errors)
        if not self._simvue.create_run(data):
            return False

        if self._status == 'running':
            self._start()

        return True

    @property
    def name(self):
        """
        Return the name of the run
        """
        return self._name

    def reconnect(self, name, offline=False):
        """
        Reconnect to a run in the created state
        """
        self._status = 'running'
        self._offline = offline
        self._name = name
        self._simvue = Simvue(self._name, self._offline, self._suppress_errors)
        self._start(reconnect=True)

    def config(self,
               suppress_errors=False,
               queue_blocking=False,
               queue_size=QUEUE_SIZE):
        """
        Optional configuration
        """
        if not isinstance(suppress_errors, bool):
            self._error('suppress_errors must be boolean')
        self._suppress_errors = suppress_errors

        if not isinstance(queue_blocking, bool):
            self._error('queue_blocking must be boolean')
        self._queue_blocking = queue_blocking

        if not isinstance(queue_size, int):
            self._error('queue_size must be an integer')
        self._queue_size = queue_size

    def update_metadata(self, metadata):
        """
        Add/update metadata
        """
        if not self._name:
            self._error(INIT_MISSING)
            return False

        if not self._active:
            self._error('Run is not active')
            return False

        if not isinstance(metadata, dict):
            self._error('metadata must be a dict')
            return False

        data = {'name': self._name, 'metadata': metadata}

        if self._simvue.update(data):
            return True

        return False

    def update_tags(self, tags):
        """
        Add/update tags
        """
        if not self._name:
            self._error(INIT_MISSING)
            return False

        if not self._active:
            self._error('Run is not active')
            return False

        data = {'name': self._name, 'tags': tags}

        if self._simvue.update(data):
            return True

        return False

    def log_event(self, message, timestamp=None):
        """
        Write event
        """
        if not self._name:
            self._error(INIT_MISSING)
            return False

        if not self._active:
            self._error('Run is not active')
            return False

        if self._status != 'running':
            self._error('Cannot log events when not in the running state')
            return False

        data = {}
        data['run'] = self._name
        data['message'] = message
        data['timestamp'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
        if timestamp is not None:
            if validate_timestamp(timestamp):
                data['timestamp'] = timestamp
            else:
                self._error('Invalid timestamp format')
                return False

        try:
            self._events_queue.put(data, block=self._queue_blocking)
        except:
            pass

        return True

    def log_metrics(self, metrics, step=None, time=None, timestamp=None):
        """
        Write metrics
        """
        if not self._name:
            self._error(INIT_MISSING)
            return False

        if not self._active:
            self._error('Run is not active')
            return False

        if self._status != 'running':
            self._error('Cannot log metrics when not in the running state')
            return False

        if not isinstance(metrics, dict) and not self._suppress_errors:
            self._error('Metrics must be a dict')
            return False

        data = {}
        data['run'] = self._name
        data['values'] = metrics
        data['time'] = tm.time() - self._start_time
        if time is not None:
            data['time'] = time
        data['timestamp'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
        if timestamp is not None:
            if validate_timestamp(timestamp):
                data['timestamp'] = timestamp
            else:
                self._error('Invalid timestamp format')
                return False

        if step is None:
            data['step'] = self._step
        else:
            data['step'] = step

        self._step += 1

        try:
            self._metrics_queue.put(data, block=self._queue_blocking)
        except:
            pass

        return True

    def save(self, filename, category, filetype=None, preserve_path=False):
        """
        Upload file
        """
        if not self._name:
            self._error(INIT_MISSING)
            return False

        if not self._active:
            self._error('Run is not active')
            return False

        if not os.path.isfile(filename):
            self._error(f"File {filename} does not exist")
            return False

        if filetype:
            mimetypes_valid = []
            mimetypes.init()
            for _, value in mimetypes.types_map.items():
                mimetypes_valid.append(value)

            if filetype not in mimetypes_valid:
                self._error('Invalid MIME type specified')
                return False

        data = {}
        if preserve_path:
            data['name'] = filename
            if data['name'].startswith('./'):
                data['name'] = data['name'][2:]
        else:
            data['name'] = os.path.basename(filename)
        data['run'] = self._name
        data['category'] = category
        data['checksum'] = calculate_sha256(filename)
        data['size'] = os.path.getsize(filename)
        data['originalPath'] = os.path.abspath(os.path.expanduser(os.path.expandvars(filename)))

        # Determine mimetype
        if not filetype:
            mimetypes.init()
            mimetype = mimetypes.guess_type(filename)[0]
            if not mimetype:
                mimetype = 'application/octet-stream'
        else:
            mimetype = filetype

        data['type'] = mimetype

        # Register file
        if not self._simvue.save_file(data):
            return False

        return True

    def save_directory(self, directory, category, filetype=None, preserve_path=False):
        """
        Upload a whole directory
        """
        if not self._name:
            self._error(INIT_MISSING)
            return False

        if not self._active:
            self._error('Run is not active')
            return False

        if not os.path.isdir(directory):
            self._error(f"Directory {directory} does not exist")
            return False

        if filetype:
            mimetypes_valid = []
            mimetypes.init()
            for _, value in mimetypes.types_map.items():
                mimetypes_valid.append(value)

            if filetype not in mimetypes_valid:
                self._error('Invalid MIME type specified')
                return False

        for filename in walk_through_files(directory):
            if os.path.isfile(filename):
                self.save(filename, category, filetype, preserve_path)

        return True

    def save_all(self, items, category, filetype=None, preserve_path=False):
        """
        Save the list of files and/or directories
        """
        for item in items:
            if os.path.isfile(item):
                self.save(item, category, filetype, preserve_path)
            elif os.path.isdir(item):
                self.save_directory(item, category, filetype, preserve_path)
            else:
                self._error(f"{item}: No such file or directory")

    def set_status(self, status):
        """
        Set run status
        """
        if not self._name:
            self._error(INIT_MISSING)
            return False

        if not self._active:
            self._error('Run is not active')
            return False

        if status not in ('completed', 'failed', 'terminated'):
            self._error('invalid status')

        data = {'name': self._name, 'status': status}
        self._status = status

        if self._simvue.update(data):
            return True

        return False

    def close(self):
        """
        Close the run
        """
        if not self._name:
            self._error(INIT_MISSING)
            return False

        if not self._active:
            self._error('Run is not active')
            return False

        self.set_status('completed')

    def set_folder_details(self, path, metadata={}, tags=[], description=None):
        """
        Add metadata to the specified folder
        """
        if not self._name:
            self._error(INIT_MISSING)
            return False

        if not self._active:
            self._error('Run is not active')
            return False

        if not isinstance(metadata, dict):
            self._error('metadata must be a dict')
            return False

        if not isinstance(tags, list):
            self._error('tags must be a list')
            return False

        data = {'path': path}

        if metadata:
            data['metadata'] = metadata

        if tags:
            data['tags'] = tags

        if description:
            data['description'] = description

        if self._simvue.set_folder_details(data):
            return True

        return False

    def add_alert(self,
                  name,
                  source='metrics',
                  frequency=5,
                  window=5,
                  rule=None,
                  metric=None,
                  threshold=None,
                  range_low=None,
                  range_high=None,
                  notification='none',
                  pattern=None):
        """
        Creates an alert with the specified name (if it doesn't exist) and applies it to the current run
        """
        if not self._name:
            self._error(INIT_MISSING)
            return False

        if not self._active:
            self._error('Run is not active')
            return False

        if rule:
            if rule not in ('is below', 'is above', 'is outside range', 'is inside range'):
                self._error('alert rule invalid')
                return False

        if type in ('is below', 'is above') and threshold is None:
            self._error('threshold must be defined for the specified alert type')
            return False

        if type in ('is outside range', 'is inside range') and (range_low is None or range_high is None):
            self._error('range_low and range_high must be defined for the specified alert type')
            return False

        if notification not in ('none', 'email'):
            self._error('notification must be either none or email')
            return False

        if source not in ('metrics', 'events'):
            self._error('source must be either metrics or events')
            return False

        alert_definition = {}

        if source == 'metrics':
            alert_definition['metric'] = metric
            alert_definition['window'] = window
            alert_definition['rule'] = rule
            if threshold is not None:
                alert_definition['threshold'] = threshold
            elif range_low is not None and range_high is not None:
                alert_definition['range_low'] = range_low
                alert_definition['range_high'] = range_high
        else:
            alert_definition['pattern'] = pattern

        alert = {'name': name,
                 'metric': metric,
                 'frequency': frequency,
                 'notification': notification,
                 'source': source,
                 'alert': alert_definition}

        if not self._simvue.add_alert(alert):
            self._error('unable to create alert')
            return False

        data = {'name': self._name, 'alert': name}

        if self._simvue.update(data):
            return True

        return False