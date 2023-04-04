import configparser
import filecmp
import os
import shutil
import time
import unittest
import uuid
from simvue import Run, Client
from simvue.sender import sender

import common

class TestArtifactsCreated(unittest.TestCase):
    def test_artifact_input_created(self):
        """
        Create a run & an artifact of type 'input' & check it can be downloaded
        for runs in the created state
        """
        run = Run()
        run.init(common.RUNNAME2, folder=common.FOLDER, running=False)

        content = str(uuid.uuid4())
        with open(common.FILENAME2, 'w') as fh:
            fh.write(content)
        run.save(common.FILENAME2, 'input')

        shutil.rmtree('./test', ignore_errors=True)
        os.mkdir('./test')

        client = Client()
        client.get_artifact_as_file(common.RUNNAME2, common.FILENAME2, './test')

        self.assertTrue(filecmp.cmp(common.FILENAME2, './test/%s' % common.FILENAME2))

        runs = client.delete_runs(common.FOLDER)
        self.assertEqual(len(runs), 1)

        shutil.rmtree('./test', ignore_errors=True)
        os.remove(common.FILENAME2)

if __name__ == '__main__':
    unittest.main()
