import unittest
import uuid
import tempfile
import simvue
from simvue import Run
import os
import filecmp
import time
class TestRunProcess(unittest.TestCase):
    def test_processes_cwd(self):
        """Check that cwd argument works correctly in add_process.

        Create a temporary directory, and a python file inside that directory. Check that if only the file name
        is passed to add_process as the script, and the directory is specified as the cwd argument, that the process
        runs correctly and the script is uploaded as expected.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            with tempfile.NamedTemporaryFile(dir=temp_dir, suffix=".py") as temp_file:
                with open(temp_file.name, "w") as out_f:
                    out_f.writelines([
                        "import os\n",
                        "f = open('new_file.txt', 'w')\n",
                        "f.write('Test Line')\n",
                        "f.close()"
                    ])
                    import pdb; pdb.set_trace()
                    
                with Run() as run:
                    run.init(
                        name='test-%s' % str(uuid.uuid4()),
                        folder='/test-%s' % str(uuid.uuid4())
                    )
                    run_id = run._id
                    run.add_process(
                        identifier="sleep_10_process",
                        executable="python",
                        script=temp_file.name,
                        cwd=temp_dir
                    )
                    time.sleep(1)
                    run.save_file(os.path.join(temp_dir, "new_file.txt"), 'output')

                client = simvue.Client()

                # Check that the script was uploaded to the run correctly
                os.makedirs(os.path.join(temp_dir, "downloaded"))
                client.get_artifact_as_file(run_id, os.path.basename(temp_file.name), path=os.path.join(temp_dir, "downloaded"))
                assert filecmp.cmp(os.path.join(temp_dir, "downloaded", os.path.basename(temp_file.name)), temp_file.name)

                client.get_artifact_as_file(run_id, "new_file.txt", path=os.path.join(temp_dir, "downloaded"))
                new_file = open(os.path.join(temp_dir, "downloaded", "new_file.txt"), "r")
                assert new_file.read() == "Test Line"
                new_file.close()

if __name__ == '__main__':
    unittest.main()