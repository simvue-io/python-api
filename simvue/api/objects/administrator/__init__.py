"""
Simvue Admin Objects
====================

These are Simvue objects only accessible to an administrator of
the server.

"""

from .tenant import Tenant as Tenant
from .user import User as User

__all__ = [
    "Tenant",
    "User",
]
