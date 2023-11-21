import random
import unittest
import uuid
import os
from simvue import Run, Client
from simvue.sender import sender

import common

class TestRunMetadata(unittest.TestCase):
    def test_run_metadata(self):
        """
        Check metadata can be specified & retrieved
        """
        test_dir = next(common.create_config())

        os.chdir(test_dir)
        name = 'test-%s' % str(uuid.uuid4())
        folder = '/test-%s' % str(uuid.uuid4())
        metadata = {'a': 'string', 'b': random.random(), 'c': random.random()}
        run = Run(mode='offline')
        run.init(name, metadata=metadata, folder=folder)
        run.close()

        run_id = name
        if common.SIMVUE_API_VERSION:
            run_id = run.id

        client = Client()
        data = client.get_run(run_id, metadata=True)
        self.assertEqual(data['metadata'], metadata)

        runs = client.delete_runs(folder)
        self.assertEqual(len(runs), 1)

if __name__ == '__main__':
    unittest.main()
