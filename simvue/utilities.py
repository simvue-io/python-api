import configparser
import os

def get_config():
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
