import time
import unittest
import uuid
from simvue import Run, Client

import common

class TestRunMetrics(unittest.TestCase):
    def test_run_metrics(self):
        """
        Try logging metrics and retrieving them
        """
        name = 'test-%s' % str(uuid.uuid4())
        run = Run()
        run.init(name, folder=common.FOLDER)
        run.log_metrics({'a': 1.0})
        run.log_metrics({'a': 1.2})

        run.log_metrics({'b': 2.0}, step=10, time=2.0)
        run.log_metrics({'b': 2.3}, step=11, time=3.0)

        run.close()

        time.sleep(5)

        client = Client()
        data_a = client.get_metrics(name, 'a', 'step')
        data_b = client.get_metrics(name, 'b', 'step')
        data_b_time = client.get_metrics(name, 'b', 'time')

        data_a_val = [[0, 1.0, name, 'a'], [1, 1.2, name, 'a']]
        data_b_val = [[10, 2.0, name, 'b'], [11, 2.3, name, 'b']]
        data_b_time_val = [[2.0, 2.0, name, 'b'], [3.0, 2.3, name, 'b']]

        self.assertEqual(data_a, data_a_val)
        self.assertEqual(data_b, data_b_val)
        self.assertEqual(data_b_time, data_b_time_val)

        runs = client.delete_runs(common.FOLDER)
        self.assertEqual(len(runs), 1)

if __name__ == '__main__':
    unittest.main()
