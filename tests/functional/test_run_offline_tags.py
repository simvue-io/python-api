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

class TestRunOfflineTags(unittest.TestCase):
    def test_run_tags(self):
        """
        Create a run with tags, upload it & check that it exists
        """
        common.update_config()
        try:
            shutil.rmtree('./offline')
        except:
            pass

        name = 'test-%s' % str(uuid.uuid4())
        tags = ['a1', 'b2']
        run = Run('offline')
        run.init(name, tags=tags, folder=common.FOLDER)
        run.close()

        sender()

        client = Client()
        data = client.get_run(name, tags=True)
        self.assertEqual(name, data['name'])
        self.assertEqual(tags, data['tags'])

        runs = client.delete_runs(common.FOLDER)
        self.assertEqual(len(runs), 1)

if __name__ == '__main__':
    unittest.main()
