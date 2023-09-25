import unittest
import uuid
from simvue import Run, Client

import common

class TestRunContext(unittest.TestCase):
    def test_context_run(self):
        """
        Create a run using a context manager & check that it exists
        """
        name = 'test-%s' % str(uuid.uuid4())
        with Run() as run:
            run.init(name, folder=common.FOLDER)

            run_id = name
            if common.SIMVUE_API_VERSION:
                run_id = run.id

        client = Client()
        data = client.get_run(run_id)
        self.assertEqual(name, data['name'])

        runs = client.delete_runs(common.FOLDER)
        self.assertEqual(len(runs), 1)

if __name__ == '__main__':
    unittest.main()
