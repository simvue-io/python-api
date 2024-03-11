from .offline import Offline
from .remote import Remote


def Simvue(name, uuid, id, mode, suppress_errors=False):
    if mode == "offline":
        return Offline(name, uuid, id, suppress_errors)
    else:
        return Remote(name, uuid, id, suppress_errors)
