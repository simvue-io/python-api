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
    def test_run_offline_metadata_update(self):
        """
        Check metadata can be updated & retrieved
        """
        common.update_config()
        try:
            shutil.rmtree('./offline')
        except:
            pass

        name = 'test-%s' % str(uuid.uuid4())
        metadata = {'a': 'string', 'b': 1, 'c': 2.5}
        run = Run('offline')
        run.init(name, metadata=metadata, folder=common.FOLDER)

        sender()

        run.update_metadata({'b': 2})
        run.close()

        sender()

        metadata['b'] = 2

        client = Client()
        data = client.get_run(name, metadata=True)
        self.assertEqual(data['metadata'], metadata)

        runs = client.delete_runs(common.FOLDER)
        self.assertEqual(len(runs), 1)

if __name__ == '__main__':
    unittest.main()
