import unittest
import uuid
from simvue import Run, Client

import common

class TestRunUpdateTagsCreated(unittest.TestCase):
    def test_run_tags_update_created(self):
        """
        Check tags can be updated & retrieved for a run in the 
        created state
        """
        name = 'test-%s' % str(uuid.uuid4())
        folder = '/test-%s' % str(uuid.uuid4())
        tags = ['a1']
        run = Run()
        run.init(name, tags=tags, folder=folder, running=False)

        run.update_tags(['a1', 'b2'])
        tags.append('b2')

        client = Client()
        data = client.get_run(run.id)
        self.assertEqual(tags, data['tags'])

        runs = client.delete_runs(folder)
        self.assertEqual(len(runs), 1)

if __name__ == '__main__':
    unittest.main()
