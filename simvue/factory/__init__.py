from .remote import Remote
from .offline import Offline
from .base import SimvueBaseClass


def Simvue(
    name: str,
    uniq_id: str,
    mode: str,
    suppress_errors: bool = True
) -> SimvueBaseClass:
    if mode == "offline":
        return Offline(name, uniq_id, suppress_errors)
    else:
        return Remote(name, uniq_id, suppress_errors)
