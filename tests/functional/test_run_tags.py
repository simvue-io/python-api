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
    def test_run_tags(self):
        """
        Check tags can be specified & retrieved
        """
        name = 'test-%s' % str(uuid.uuid4())
        tags = ['a1', 'b2']
        run = Run()
        run.init(name, tags=tags, folder=common.FOLDER)
        run.close()

        client = Client()
        data = client.get_run(name, tags=True)
        self.assertEqual(tags, data['tags'])

        runs = client.delete_runs(common.FOLDER)
        self.assertEqual(len(runs), 1)

if __name__ == '__main__':
    unittest.main()
