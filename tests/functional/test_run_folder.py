import unittest
import uuid
from simvue import Run, Client

import common

class TestRunFolder(unittest.TestCase):
    def test_run_folder(self):
        """
        Check specified folder of run
        """
        name = 'test-%s' % str(uuid.uuid4())
        run = Run()
        run.init(name, folder=common.FOLDER)
        run.close()

        run_id = name
        if common.SIMVUE_API_VERSION:
            run_id = run.id

        client = Client()
        data = client.get_run(run_id)
        self.assertEqual(data['folder'], common.FOLDER)

        runs = client.delete_runs(common.FOLDER)
        self.assertEqual(len(runs), 1)

if __name__ == '__main__':
    unittest.main()
