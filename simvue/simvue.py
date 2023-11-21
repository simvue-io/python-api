from .remote import Remote
from .offline import Offline

def Simvue(name, uuid, id, mode, suppress_errors=True):
    if mode == 'offline':
        return Offline(name, uuid, id, suppress_errors)
    else:
        return Remote(name, uuid, id, suppress_errors)
