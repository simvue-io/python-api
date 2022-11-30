from .remote import Remote
from .offline import Offline

def Simvue(name, mode, suppress_errors=False):
    if mode == 'offline':
        return Offline(name, suppress_errors=False)
    else:
        return Remote(name, suppress_errors=False)
