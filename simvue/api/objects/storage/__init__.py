"""Simvue Storage.

Contains classes for interacting with Simvue storage objects,
the storage types are split into classes to ensure correct
inputs are provided and the relevant properties are made available.

"""

from .fetch import Storage
from .file import FileStorage
from .s3 import S3Storage

__all__ = ["FileStorage", "S3Storage", "Storage"]
