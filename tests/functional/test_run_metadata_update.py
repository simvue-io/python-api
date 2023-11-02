import unittest
import uuid
from simvue import Run, Client

import common

class TestRunOffline(unittest.TestCase):
    def test_run_metadata_update(self):
        """
        Check metadata can be updated & retrieved
        """
        name = 'test-%s' % str(uuid.uuid4())
        folder = '/test-%s' % str(uuid.uuid4())
        metadata = {'a': 'string', 'b': 1, 'c': 2.5}
        run = Run()
        run.init(name, metadata=metadata, folder=folder)
        run.update_metadata({'b': 2})
        run.close()

        run_id = name
        if common.SIMVUE_API_VERSION:
            run_id = run.id

        metadata['b'] = 2

        client = Client()
        data = client.get_run(run_id, metadata=True)
        self.assertEqual(data['metadata'], metadata)

        runs = client.delete_runs(folder)
        self.assertEqual(len(runs), 1)

if __name__ == '__main__':
    unittest.main()
