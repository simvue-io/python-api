import configparser
import filecmp
import os
import shutil
import time
import unittest
import uuid
from simvue import Run, Client
from simvue.sender import sender

import common



class TestRunOffline(unittest.TestCase):
    def test_basic_run(self):
        """
        Create a run, upload it & check that it exists
        """
        test_dir = common.create_config()

        os.chdir(test_dir)

        name = 'test-%s' % str(uuid.uuid4())
        run = Run('offline')
        run.init(name, folder=common.FOLDER)
        run.close()

        sender()

        client = Client()
        data = client.get_run(name)
        self.assertEqual(name, data['name'])

        runs = client.delete_runs(common.FOLDER)
        self.assertEqual(len(runs), 1)

if __name__ == '__main__':
    unittest.main()
