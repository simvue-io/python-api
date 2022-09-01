import logging
from simtrack import Simtrack, SimtrackHandler

run = Simtrack()

run.init(tags=['logging'],
         description='Logging test')

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
sth = SimtrackHandler(run)
logger.addHandler(sth)

logger.info("This is a SimTrack logging test")

run.close()
