from .remote import Remote
from .offline import Offline

def Simvue(name, uuid, mode, suppress_errors=False):
    if mode == 'offline':
        return Offline(name, uuid, suppress_errors=False)
    else:
        return Remote(name, uuid, suppress_errors=False)
