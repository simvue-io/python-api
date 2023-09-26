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
        folder = '/test-%s' % str(uuid.uuid4())
        run = Run()
        run.init(name, folder=folder)
        run.log_metrics({'a': 1.0})
        run.log_metrics({'a': 1.2})

        run.log_metrics({'b': 2.0}, step=10, time=2.0)
        run.log_metrics({'b': 2.3}, step=11, time=3.0)

        run.close()

        run_id = name
        if common.SIMVUE_API_VERSION:
            run_id = run.id

        time.sleep(5)

        client = Client()
        data_a = client.get_metrics(run_id, 'a', 'step')
        data_b = client.get_metrics(run_id, 'b', 'step')
        data_b_time = client.get_metrics(run_id, 'b', 'time')

        data_a_val = [[0, 1.0, name, 'a'], [1, 1.2, name, 'a']]
        data_b_val = [[10, 2.0, name, 'b'], [11, 2.3, name, 'b']]
        data_b_time_val = [[2.0, 2.0, name, 'b'], [3.0, 2.3, name, 'b']]

        self.assertEqual(data_a, data_a_val)
        self.assertEqual(data_b, data_b_val)
        self.assertEqual(data_b_time, data_b_time_val)

        metrics_names = client.get_metrics_names(run_id)
        self.assertEqual(metrics_names, ['a', 'b'])

        runs = client.delete_runs(folder)
        self.assertEqual(len(runs), 1)

if __name__ == '__main__':
    unittest.main()
