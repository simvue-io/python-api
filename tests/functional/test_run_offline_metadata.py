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

class TestRunOfflineMetadata(unittest.TestCase):
    def test_run_metadata(self):
        """
        Create a run with metadata, upload it & check that it exists
        """
        test_dir = common.create_config()

        os.chdir(test_dir)

        name = 'test-%s' % str(uuid.uuid4())
        metadata = {'a': 'string', 'b': 1, 'c': 2.5}
        run = Run('offline')
        run.init(name, metadata=metadata, folder=common.FOLDER)
        run.close()

        sender()

        client = Client()
        data = client.get_run(name, metadata=True)
        self.assertEqual(name, data['name'])
        self.assertEqual(data['metadata'], metadata)

        runs = client.delete_runs(common.FOLDER)
        self.assertEqual(len(runs), 1)

if __name__ == '__main__':
    unittest.main()
