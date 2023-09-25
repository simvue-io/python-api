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

class TestArtifacts(unittest.TestCase):
    def test_artifact_input(self):
        """
        Create a run & an artifact of type 'input' & check it can be downloaded
        """
        run = Run()
        run.init(common.RUNNAME2, folder=common.FOLDER)

        content = str(uuid.uuid4())
        with open(common.FILENAME2, 'w') as fh:
            fh.write(content)
        run.save(common.FILENAME2, 'input')

        run.close()

        run_id = common.RUNNAME2
        if common.SIMVUE_API_VERSION:
            run_id = run.id

        shutil.rmtree('./test', ignore_errors=True)
        os.mkdir('./test')

        client = Client()
        client.get_artifact_as_file(run_id, common.FILENAME2, './test')

        self.assertTrue(filecmp.cmp(common.FILENAME2, './test/%s' % common.FILENAME2))

        runs = client.delete_runs(common.FOLDER)
        self.assertEqual(len(runs), 1)

        shutil.rmtree('./test', ignore_errors=True)
        os.remove(common.FILENAME2)

if __name__ == '__main__':
    unittest.main()
