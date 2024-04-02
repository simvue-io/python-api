import typing

from .base import SimvueBaseClass
from .offline import Offline
from .remote import Remote

if typing.TYPE_CHECKING:
    from simvue.config import SimvueConfiguration


def Simvue(
    name: str,
    uniq_id: str,
    mode: str,
    config: "SimvueConfiguration",
    suppress_errors: bool = True,
) -> SimvueBaseClass:
    if mode == "offline":
        return Offline(name, uniq_id, suppress_errors)
    else:
        return Remote(name, uniq_id, config, suppress_errors)
