import logging
from simvue import Simvue, Handler

run = Simvue()

run.init(tags=['logging'],
         description='Logging test')

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
sth = Handler(run)
logger.addHandler(sth)

logger.info("This is a Simvue logging test")

run.close()
