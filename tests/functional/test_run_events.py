import time
import unittest
import uuid
from simvue import Run, Client

import common

class TestRunEvents(unittest.TestCase):
    def test_run_events(self):
        """
        Try logging events and retrieving them
        """
        name = 'test-%s' % str(uuid.uuid4())
        folder = '/test-%s' % str(uuid.uuid4())
        run = Run()
        run.init(name, folder=folder)

        run.log_event('test-event-1', timestamp='2022-01-03 16:42:30.849617')
        run.log_event('test-event-2', timestamp='2022-01-03 16:42:31.849617')

        run.close()

        run_id = name
        if common.SIMVUE_API_VERSION:
            run_id = run.id

        time.sleep(5)

        client = Client()
        data = client.get_events(run_id)

        data_compare = [{'timestamp': '2022-01-03 16:42:30.849617', 'message': 'test-event-1'},
                        {'timestamp': '2022-01-03 16:42:31.849617', 'message': 'test-event-2'}]

        self.assertEqual(data, data_compare)

        runs = client.delete_runs(folder)
        self.assertEqual(len(runs), 1)

if __name__ == '__main__':
    unittest.main()
