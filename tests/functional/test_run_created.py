import unittest
import uuid
from simvue import Run, Client

import common

class TestRunCreated(unittest.TestCase):
    def test_basic_run(self):
        """
        Create a run in the created state, then reconnect to it
        """
        name = 'test-%s' % str(uuid.uuid4())
        run_create = Run()
        run_create.init(name, folder=common.FOLDER, running=False)
        uid = run_create.uid

        self.assertEqual(name, run_create.name)

        client = Client()
        data = client.get_run(name)

        self.assertEqual(data['status'], 'created')

        run_start = Run()
        run_start.reconnect(name, uid)

        data = client.get_run(name)
        self.assertEqual(data['status'], 'running')

        run_start.close()

if __name__ == '__main__':
    unittest.main()
