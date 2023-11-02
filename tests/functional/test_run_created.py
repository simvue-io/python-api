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
        folder = '/test-%s' % str(uuid.uuid4())
        run_create = Run()
        run_create.init(name, folder=folder, running=False)

        run_id = name
        if common.SIMVUE_API_VERSION:
            run_id = run_create.id

        self.assertEqual(name, run_create.name)

        client = Client()
        data = client.get_run(run_id)

        self.assertEqual(data['status'], 'created')

        run_start = Run()
        run_start.reconnect(run_id)

        data = client.get_run(run_id)
        self.assertEqual(data['status'], 'running')

        run_start.close()

        runs = client.delete_runs(folder)
        self.assertEqual(len(runs), 1)

if __name__ == '__main__':
    unittest.main()
