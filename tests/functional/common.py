import configparser
import os
import uuid

def update_config():
    """
    Rewrite offline cache into config file
    """
    config = configparser.ConfigParser()
    config.read('simvue.ini')
    token = config.get('server', 'token')
    url = config.get('server', 'url')

    current_pwd = os.getcwd()

    config['offline'] = {}
    config['offline']['cache'] = '%s/offline' % os.getcwd()

    with open('simvue.ini', 'w') as configfile:
        config.write(configfile)

FOLDER = '/test-%s' % str(uuid.uuid4())
FILENAME1 = str(uuid.uuid4())
FILENAME2 = str(uuid.uuid4())
FILENAME3 = str(uuid.uuid4())
RUNNAME1 = 'test-%s' % str(uuid.uuid4())
RUNNAME2 = 'test-%s' % str(uuid.uuid4())
RUNNAME3 = 'test-%s' % str(uuid.uuid4())
