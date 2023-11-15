import unittest
import uuid
from simvue import Run

class TestRunMetrics(unittest.TestCase):
    def test_monitor_processes(self):
        with Run(mode='offline') as _run:
            _run.init(f"test_exec_monitor_{uuid.uuid4()}")
            _run.add_process("process_1", "Hello world!", executable="echo", n=True)
            _run.add_process("process_2", "bash", debug=True, c="'return 1'")
            _run.add_process("process_3", "ls", "-ltr")

if __name__ == '__main__':
    unittest.main()