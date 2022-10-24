import logging

class Handler(logging.Handler):
    """
    Class for handling logging to Simvue
    """
    def __init__(self, client):
        logging.Handler.__init__(self)
        self._client = client

    def emit(self, record):
        if 'simvue.' in record.name:
            return

        msg = self.format(record)

        try:
            self._client.log_event(msg)
        except Exception:
            logging.Handler.handleError(self, record)

    def flush(self):
        pass

    def close(self):
        pass
