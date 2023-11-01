import unittest
import uuid
from simvue import Run

class TestRunMetrics(unittest.TestCase):
    def test_monitor_processes(self):
        with Run() as _run:
            _run.init(f"test_exec_monitor_{uuid.uuid4()}")
            _run.add_process("process_1", "echo", "Hello world!")
            _run.add_process("process_2", "bash", c="'return 1'")

if __name__ == '__main__':
    unittest.main()