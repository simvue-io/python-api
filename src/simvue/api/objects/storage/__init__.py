"""
Simvue Storage
==============

Contains classes for interacting with Simvue storage objects,
the storage types are split into classes to ensure correct
inputs are provided and the relevant properties are made available.

"""

from .file import FileStorage as FileStorage
from .s3 import S3Storage as S3Storage
from .fetch import Storage as Storage
