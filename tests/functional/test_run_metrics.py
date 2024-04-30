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
        run.init(name, folder=folder, tags=["simvue_client_tests", "test_run_metrics"])
        run.log_metrics({'a': 1.0})
        run.log_metrics({'a': 1.2})

        run.log_metrics({'b': 2.0}, step=10, time=2.0)
        run.log_metrics({'b': 2.3}, step=11, time=3.0)

        run.close()

        time.sleep(5)

        client = Client()
        data_a = client.get_metric_values(
            metric_names=['a'],
            run_ids=[run.id],
            xaxis='step',
            aggregate=False,
            use_run_names=True
        )
        data_b = client.get_metric_values(
            metric_names=['b'],
            run_ids=[run.id],
            xaxis='step',
            aggregate=False,
            use_run_names=True
        )
        data_b_time = client.get_metric_values(
            metric_names=['b'],
            run_ids=[run.id],
            xaxis='time',
            aggregate=False,
            use_run_names=True
        )

        data_a_val = {'a': {(0, name): 1.0, (1, name): 1.2}}
        data_b_val = {'b': {(10, name): 2.0, (11, name): 2.3}}
        data_b_time_val = {'b': {(2.0, name): 2.0, (3.0, name): 2.3}}

        self.assertEqual(data_a, data_a_val)
        self.assertEqual(data_b, data_b_val)
        self.assertEqual(data_b_time, data_b_time_val)

        metrics_names = client.get_metrics_names(run.id)
        assert all(i in metrics_names for i in ['a', 'b'])

        runs = client.delete_runs(folder)
        self.assertEqual(len(runs), 1)

if __name__ == '__main__':
    unittest.main()
