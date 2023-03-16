import configparser
import filecmp
import os
import shutil
import time
import unittest
import uuid
from simvue import Run, Client
from simvue.sender import sender

class TestRunFolder(unittest.TestCase):
    def test_run_folder_metadata_find(self):
        """
        Create a run & folder with metadata, find it then delete it
        """
        name = 'test-%s' % str(uuid.uuid4())
        folder = '/tests/%s' % str(uuid.uuid4())
        run = Run()
        run.init(name, folder=folder)
        run.set_folder_details(path=folder, metadata={'atest': 5.0})
        run.close()

        client = Client()
        data = client.get_folders(['atest == 5.0'])
        found = False
        for item in data:
            if item['path'] == folder:
                found = True
        self.assertTrue(found)

        runs = client.delete_folder(folder, runs=True)

        client = Client()
        with self.assertRaises(Exception) as context:
            client.get_folder(folder)

        self.assertTrue('Folder does not exist' in str(context.exception))

if __name__ == '__main__':
    unittest.main()
