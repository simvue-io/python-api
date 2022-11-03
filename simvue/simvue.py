from .remote import Remote
from .offline import Offline

def Simvue(name, offline=False, suppress_errors=False):
    if offline:
        return Offline(name, suppress_errors=False)
    else:
        return Remote(name, suppress_errors=False)
