import unittest
import uuid
from simvue import Run, Client

import common

class TestRunOffline(unittest.TestCase):
    def test_context_run(self):
        """
        Create a run using a context manager & check that it exists
        """
        name = 'test-%s' % str(uuid.uuid4())
        with Run() as run:
            run.init(name, folder=common.FOLDER)

        client = Client()
        data = client.get_run(name)
        self.assertEqual(name, data['name'])

        runs = client.delete_runs(common.FOLDER)
        self.assertEqual(len(runs), 1)

if __name__ == '__main__':
    unittest.main()
