import configparser
import os
import uuid
import tempfile

def create_config():
    """
    Rewrite offline cache into config file
    """
    config = configparser.ConfigParser()
    config.read('simvue.ini')

    with tempfile.TemporaryDirectory() as temp_d:

        config['offline'] = {}
        config['offline']['cache'] = os.path.join(temp_d, 'offline')
        os.makedirs(os.path.join(temp_d, 'offline'), exist_ok=True)

        with open(os.path.join(temp_d, 'simvue.ini'), 'w') as configfile:
            config.write(configfile)
        yield temp_d

FOLDER = '/test-%s' % str(uuid.uuid4())
FILENAME1 = str(uuid.uuid4())
FILENAME2 = str(uuid.uuid4())
FILENAME3 = str(uuid.uuid4())
RUNNAME1 = 'test-%s' % str(uuid.uuid4())
RUNNAME2 = 'test-%s' % str(uuid.uuid4())
RUNNAME3 = 'test-%s' % str(uuid.uuid4())

SIMVUE_API_VERSION = os.getenv('SIMVUE_API_VERSION')
