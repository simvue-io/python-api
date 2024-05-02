import typing

from .base import SimvueBaseClass
from .offline import Offline
from .remote import Remote


def Simvue(
    name: typing.Optional[str], uniq_id: str, mode: str, suppress_errors: bool = True
) -> SimvueBaseClass:
    if mode == "offline":
        return Offline(name, uniq_id, suppress_errors)
    else:
        return Remote(name, uniq_id, suppress_errors)
