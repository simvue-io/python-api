"""Simvue Admin Objects.

These are Simvue objects only accessible to an administrator of
the server.

"""

from .tenant import Tenant
from .user import User

__all__ = [
    "Tenant",
    "User",
]
