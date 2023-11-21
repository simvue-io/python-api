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
        folder = '/test-%s' % str(uuid.uuid4())
        run = Run()
        run.init(name, folder=folder)
        run.close()

        client = Client()
        data = client.get_run(run.id)
        self.assertEqual(data['folder'], folder)

        runs = client.delete_runs(folder)
        self.assertEqual(len(runs), 1)

if __name__ == '__main__':
    unittest.main()
