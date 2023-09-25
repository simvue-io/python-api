import unittest
import uuid
from simvue import Run, Client

import common

class TestRunOffline(unittest.TestCase):
    def test_run_tags_update(self):
        """
        Check tags can be updated & retrieved
        """
        name = 'test-%s' % str(uuid.uuid4())
        tags = ['a1']
        run = Run()
        run.init(name, tags=tags, folder=common.FOLDER)

        if common.SIMVUE_API_VERSION:
            # With v2 server we specify full list of tags
            run.update_tags(['a1', 'b2'])
        else:
            # With v1 server only append is available (!)
            run.update_tags(['b2'])

        run.close()

        run_id = name
        if common.SIMVUE_API_VERSION:
            run_id = run.id

        tags.append('b2')

        client = Client()
        data = client.get_run(run_id, tags=True)
        self.assertEqual(tags, data['tags'])

        runs = client.delete_runs(common.FOLDER)
        self.assertEqual(len(runs), 1)

if __name__ == '__main__':
    unittest.main()
