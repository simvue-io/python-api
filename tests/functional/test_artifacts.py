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
    def test_artifact_code(self):
        """
        Create a run & an artifact of type 'code' & check it can be downloaded
        """
        run = Run()
        run.init(common.RUNNAME1, folder=common.FOLDER)

        content = str(uuid.uuid4())
        with open(common.FILENAME1, 'w') as fh:
            fh.write(content)
        run.save(common.FILENAME1, 'code')

        run.close()

        shutil.rmtree('./test', ignore_errors=True)
        os.mkdir('./test')

        client = Client()
        client.get_artifact_as_file(common.RUNNAME1, common.FILENAME1, './test')

        self.assertTrue(filecmp.cmp(common.FILENAME1, './test/%s' % common.FILENAME1))

        runs = client.delete_runs(common.FOLDER)
        self.assertEqual(len(runs), 1)

        shutil.rmtree('./test', ignore_errors=True)
        os.remove(common.FILENAME1)

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

        shutil.rmtree('./test', ignore_errors=True)
        os.mkdir('./test')

        client = Client()
        client.get_artifact_as_file(common.RUNNAME2, common.FILENAME2, './test')

        self.assertTrue(filecmp.cmp(common.FILENAME2, './test/%s' % common.FILENAME2))

        runs = client.delete_runs(common.FOLDER)
        self.assertEqual(len(runs), 1)

        shutil.rmtree('./test', ignore_errors=True)
        os.remove(common.FILENAME2)

    def test_artifact_output(self):
        """
        Create a run & an artifact of type 'output' & check it can be downloaded
        """
        run = Run()
        run.init(common.RUNNAME3, folder=common.FOLDER)

        content = str(uuid.uuid4())
        with open(common.FILENAME3, 'w') as fh:
            fh.write(content)
        run.save(common.FILENAME3, 'output')

        run.close()

        shutil.rmtree('./test', ignore_errors=True)
        os.mkdir('./test')

        client = Client()
        client.get_artifact_as_file(common.RUNNAME3, common.FILENAME3, './test')

        self.assertTrue(filecmp.cmp(common.FILENAME3, './test/%s' % common.FILENAME3))

        runs = client.delete_runs(common.FOLDER)
        self.assertEqual(len(runs), 1)

        shutil.rmtree('./test', ignore_errors=True)
        os.remove(common.FILENAME3)

    def test_get_artifact_invalid_run(self):
        """
        Try to obtain a file from a run which doesn't exist
        """
        run = '%d-%s' % (time.time(), str(uuid.uuid4()))
        client = Client()
        with self.assertRaises(Exception) as context:
            client.get_artifact(run, str(uuid.uuid4()))
            
        self.assertTrue('Run does not exist' in str(context.exception))

if __name__ == '__main__':
    unittest.main()
