import configparser
import hashlib
import os

def get_auth():
    """
    Get the URL and access token
    """
    url = None
    token = None

    # Try reading from config file
    for filename in (os.path.join(os.path.expanduser("~"), '.simvue.ini'), 'simvue.ini'):
        try:
            config = configparser.ConfigParser()
            config.read(filename)
            token = config.get('server', 'token')
            url = config.get('server', 'url')
        except:
            pass

    # Try environment variables
    token = os.getenv('SIMVUE_TOKEN', token)
    url = os.getenv('SIMVUE_URL', url)

    return url, token

def get_offline_directory():
    """
    Get directory for offline cache
    """
    directory = None

    for filename in (os.path.join(os.path.expanduser("~"), '.simvue.ini'), 'simvue.ini'):
        try:
            config = configparser.ConfigParser()
            config.read(filename)
            directory = config.get('offline', 'cache')
        except:
            pass

    return directory

def get_directory_name(name):
    """
    Return the SHA256 sum of the provided name
    """
    return hashlib.sha256(name.encode('utf-8')).hexdigest()
