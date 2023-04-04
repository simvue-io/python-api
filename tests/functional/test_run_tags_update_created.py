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
        tags = ['a1']
        run = Run()
        run.init(name, tags=tags, folder=common.FOLDER, running=False)
        run.update_tags(['b2'])

        tags.append('b2')

        client = Client()
        data = client.get_run(name, tags=True)
        self.assertEqual(tags, data['tags'])

        runs = client.delete_runs(common.FOLDER)
        self.assertEqual(len(runs), 1)

if __name__ == '__main__':
    unittest.main()
