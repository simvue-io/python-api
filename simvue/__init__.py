"""Simvue Python API.

For interacting with Simvue servers, this includes both a user facing API
for quick and easy scraping of simulation data, and a lower level API for
a finer grained interface.

"""

from simvue.client import Client as Client
from simvue.handler import Handler as Handler
from simvue.models import RunInput as RunInput
from simvue.run import Run as Run
