import unittest
import uuid
import shutil
from simvue import Run, Client
from simvue.sender import sender

import common

class TestRunOffline(unittest.TestCase):
    def test_run_offline_tags_update(self):
        """
        Check tags can be updated & retrieved
        """
        common.update_config()
        try:
            shutil.rmtree("./offline")
        except:
            pass

        name = 'test-%s' % str(uuid.uuid4())
        folder = '/test-%s' % str(uuid.uuid4())
        tags = ['a1']
        run = Run("offline")
        run.init(name, tags=tags, folder=folder)

        sender()

        run.update_tags(['a1', 'b2'])
        tags.append('b2')
        run.close()

        sender()

        client = Client()
        data = client.get_runs([f"name == {name}"])
        self.assertEqual(len(data), 1)
        self.assertEqual(name, data[0]["name"])
        self.assertEqual(tags, data[0]["tags"])

        runs = client.delete_runs(folder)
        self.assertEqual(len(runs), 1)

if __name__ == '__main__':
    unittest.main()
