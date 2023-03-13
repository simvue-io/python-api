import configparser
import filecmp
import os
import shutil
import time
import unittest
import uuid
from simvue import Run, Client
from simvue.sender import sender

def update_config():
    """
    Rewrite offline cache into config file
    """
    config = configparser.ConfigParser()
    config.read('simvue.ini')
    token = config.get('server', 'token')
    url = config.get('server', 'url')

    current_pwd = os.getcwd()

    config['offline']['cache'] = '%s/offline' % os.getcwd()

    with open('simvue.ini', 'w') as configfile:
        config.write(configfile)

FOLDER = '/test-%s' % str(uuid.uuid4())
FILENAME1 = str(uuid.uuid4())
FILENAME2 = str(uuid.uuid4())
FILENAME3 = str(uuid.uuid4())
RUNNAME1 = 'test-%s' % str(uuid.uuid4())
RUNNAME2 = 'test-%s' % str(uuid.uuid4())
RUNNAME3 = 'test-%s' % str(uuid.uuid4())

class TestRunsBasic(unittest.TestCase):
    def test_basic_run(self):
        """
        Create a run & check that it exists
        """
        name = 'test-%s' % str(uuid.uuid4())
        run = Run()
        run.init(name, folder=FOLDER)
        run.close()
       
        client = Client()
        data = client.get_run(name)
        self.assertEqual(name, data['name'])

        runs = client.delete_runs(FOLDER)
        self.assertEqual(len(runs), 1)

    def test_context_run(self):
        """
        Create a run using a context manager & check that it exists
        """
        name = 'test-%s' % str(uuid.uuid4())
        with Run() as run:
            run.init(name, folder=FOLDER)

        client = Client()
        data = client.get_run(name)
        self.assertEqual(name, data['name'])

        runs = client.delete_runs(FOLDER)
        self.assertEqual(len(runs), 1)

    def test_run_tags(self):
        """
        Check tags can be specified & retrieved
        """
        name = 'test-%s' % str(uuid.uuid4())
        tags = ['a1', 'b2']
        run = Run()
        run.init(name, tags=tags, folder=FOLDER)
        run.close()

        client = Client()
        data = client.get_run(name, tags=True)
        self.assertEqual(tags, data['tags'])

        runs = client.delete_runs(FOLDER)
        self.assertEqual(len(runs), 1)

    def test_run_tags_update(self):
        """
        Check tags can be updated & retrieved
        """
        name = 'test-%s' % str(uuid.uuid4())
        tags = ['a1']
        run = Run()
        run.init(name, tags=tags, folder=FOLDER)
        run.update_tags(['b2'])
        run.close()

        tags.append('b2')

        client = Client()
        data = client.get_run(name, tags=True)
        self.assertEqual(tags, data['tags'])

        runs = client.delete_runs(FOLDER)
        self.assertEqual(len(runs), 1)

    def test_run_folder(self):
        """
        Check specified folder of run
        """
        name = 'test-%s' % str(uuid.uuid4())
        run = Run()
        run.init(name, folder=FOLDER)
        run.close()

        client = Client()
        data = client.get_run(name)
        self.assertEqual(data['folder'], FOLDER)

        runs = client.delete_runs(FOLDER)
        self.assertEqual(len(runs), 1)

    def test_run_metadata(self):
        """   
        Check metadata can be specified & retrieved
        """
        name = 'test-%s' % str(uuid.uuid4())
        metadata = {'a': 'string', 'b': 1, 'c': 2.5}
        run = Run()
        run.init(name, metadata=metadata, folder=FOLDER)
        run.close()    

        client = Client()
        data = client.get_run(name, metadata=True)
        self.assertEqual(data['metadata'], metadata)

        runs = client.delete_runs(FOLDER)
        self.assertEqual(len(runs), 1)

    def test_run_metadata_update(self):
        """
        Check metadata can be updated & retrieved
        """
        name = 'test-%s' % str(uuid.uuid4())
        metadata = {'a': 'string', 'b': 1, 'c': 2.5}
        run = Run()
        run.init(name, metadata=metadata, folder=FOLDER)
        run.update_metadata({'b': 2})
        run.close()

        metadata['b'] = 2

        client = Client()
        data = client.get_run(name, metadata=True)
        self.assertEqual(data['metadata'], metadata)

        runs = client.delete_runs(FOLDER)
        self.assertEqual(len(runs), 1)

class TestArtifacts(unittest.TestCase):
    def test_artifact_code(self):
        """
        Create a run & an artifact of type 'code' & check it can be downloaded
        """
        run = Run()
        run.init(RUNNAME1, folder=FOLDER)

        content = str(uuid.uuid4())
        with open(FILENAME1, 'w') as fh:
            fh.write(content)
        run.save(FILENAME1, 'code')

        run.close()

        shutil.rmtree('./test', ignore_errors=True)
        os.mkdir('./test')

        client = Client()
        client.get_artifact_as_file(RUNNAME1, FILENAME1, './test')

        self.assertTrue(filecmp.cmp(FILENAME1, './test/%s' % FILENAME1))

        runs = client.delete_runs(FOLDER)
        self.assertEqual(len(runs), 1)

    def test_artifact_input(self):
        """
        Create a run & an artifact of type 'input' & check it can be downloaded
        """
        run = Run()
        run.init(RUNNAME2, folder=FOLDER)

        content = str(uuid.uuid4())
        with open(FILENAME2, 'w') as fh:
            fh.write(content)
        run.save(FILENAME2, 'input')

        run.close()

        shutil.rmtree('./test', ignore_errors=True)
        os.mkdir('./test')

        client = Client()
        client.get_artifact_as_file(RUNNAME2, FILENAME2, './test')

        self.assertTrue(filecmp.cmp(FILENAME2, './test/%s' % FILENAME2))

        runs = client.delete_runs(FOLDER)
        self.assertEqual(len(runs), 1)

    def test_artifact_output(self):
        """
        Create a run & an artifact of type 'output' & check it can be downloaded
        """
        run = Run()
        run.init(RUNNAME3, folder=FOLDER)

        content = str(uuid.uuid4())
        with open(FILENAME3, 'w') as fh:
            fh.write(content)
        run.save(FILENAME3, 'output')

        run.close()

        shutil.rmtree('./test', ignore_errors=True)
        os.mkdir('./test')

        client = Client()
        client.get_artifact_as_file(RUNNAME3, FILENAME3, './test')

        self.assertTrue(filecmp.cmp(FILENAME3, './test/%s' % FILENAME3))

        runs = client.delete_runs(FOLDER)
        self.assertEqual(len(runs), 1)

    def test_get_artifact_invalid_run(self):
        """
        Try to obtain a file from a run which doesn't exist
        """
        run = '%d-%s' % (time.time(), str(uuid.uuid4()))
        client = Client()
        with self.assertRaises(Exception) as context:
            client.get_artifact(run, str(uuid.uuid4()))
            
        self.assertTrue('Run does not exist' in str(context.exception))

class TestRunsOffline(unittest.TestCase):
    def test_basic_run(self):
        """
        Create a run, upload it & check that it exists
        """
        update_config()
        try:
            shutil.rmtree('./offline')
        except:
            pass

        name = 'test-%s' % str(uuid.uuid4())
        run = Run('offline')
        run.init(name, folder=FOLDER)
        run.close()

        sender()

        client = Client()
        data = client.get_run(name)
        self.assertEqual(name, data['name'])

        runs = client.delete_runs(FOLDER)
        self.assertEqual(len(runs), 1)

    def test_run_tags(self):
        """
        Create a run with tags, upload it & check that it exists
        """
        update_config()
        try:
            shutil.rmtree('./offline')
        except:
            pass

        name = 'test-%s' % str(uuid.uuid4())
        tags = ['a1', 'b2']
        run = Run('offline')
        run.init(name, tags=tags, folder=FOLDER)
        run.close()

        sender()

        client = Client()
        data = client.get_run(name, tags=True)
        self.assertEqual(name, data['name'])
        self.assertEqual(tags, data['tags'])

        runs = client.delete_runs(FOLDER)
        self.assertEqual(len(runs), 1)

    def test_run_metadata(self):
        """
        Create a run with metadata, upload it & check that it exists
        """
        update_config()
        try:
            shutil.rmtree('./offline')
        except:
            pass

        name = 'test-%s' % str(uuid.uuid4())
        metadata = {'a': 'string', 'b': 1, 'c': 2.5}
        run = Run('offline')
        run.init(name, metadata=metadata, folder=FOLDER)
        run.close()

        sender()

        client = Client()
        data = client.get_run(name, metadata=True)
        self.assertEqual(name, data['name'])
        self.assertEqual(data['metadata'], metadata)

        runs = client.delete_runs(FOLDER)
        self.assertEqual(len(runs), 1)

    def test_context_run(self):
        """
        Create a run using a context manager, upload it & check that it exists
        """
        update_config()
        try:
            shutil.rmtree('./offline')
        except:
            pass

        name = 'test-%s' % str(uuid.uuid4())
        with Run('offline') as run:
            run.init(name, folder=FOLDER)

        sender()

        client = Client()
        data = client.get_run(name)
        self.assertEqual(name, data['name'])

        runs = client.delete_runs(FOLDER)
        self.assertEqual(len(runs), 1)

if __name__ == '__main__':
    unittest.main()
