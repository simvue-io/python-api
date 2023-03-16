import configparser
import filecmp
import os
import shutil
import time
import unittest
import uuid
from simvue import Run, Client
from simvue.sender import sender

class TestArtifacts(unittest.TestCase):
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
