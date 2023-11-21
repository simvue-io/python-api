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

class TestRunOfflineContextManager(unittest.TestCase):
    def test_context_run(self):
        """
        Create a run using a context manager, upload it & check that it exists
        """
        test_dir = common.create_config()

        os.chdir(test_dir)

        name = 'test-%s' % str(uuid.uuid4())
        with Run('offline') as run:
            run.init(name, folder=common.FOLDER)

        sender()

        client = Client()
        data = client.get_run(name)
        self.assertEqual(name, data['name'])

        runs = client.delete_runs(common.FOLDER)
        self.assertEqual(len(runs), 1)

if __name__ == '__main__':
    unittest.main()
