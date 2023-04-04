import random
import unittest
import uuid
from simvue import Run, Client
from simvue.sender import sender

import common

class TestRunMetadata(unittest.TestCase):
    def test_run_metadata(self):
        """
        Check metadata can be specified & retrieved
        """
        name = 'test-%s' % str(uuid.uuid4())
        metadata = {'a': 'string', 'b': random.random(), 'c': random.random()}
        run = Run()
        run.init(name, metadata=metadata, folder=common.FOLDER)
        run.close()

        client = Client()
        data = client.get_run(name, metadata=True)
        self.assertEqual(data['metadata'], metadata)

        runs = client.delete_runs(common.FOLDER)
        self.assertEqual(len(runs), 1)

if __name__ == '__main__':
    unittest.main()
