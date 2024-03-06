import typing

from .remote import Remote
from .offline import Offline
from .base import SimvueBaseClass

if typing.TYPE_CHECKING:
    from simvue.config import SimvueConfiguration


def Simvue(
    name: str,
    uniq_id: str,
    mode: str,
    config: SimvueConfiguration,
    suppress_errors: bool = True
) -> SimvueBaseClass:
    if mode == "offline":
        return Offline(name, uniq_id, suppress_errors)
    else:
        return Remote(name, uniq_id, suppress_errors)
