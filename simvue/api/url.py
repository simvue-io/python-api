"""
URL Library
===========

Module contains classes for easier handling of URLs.

"""

try:
    from typing import Self
except ImportError:
    from typing_extensions import Self
import urllib.parse
import copy

import pydantic


class URL:
    """URL class for ease of construction and use of server endpoints."""

    @pydantic.validate_call
    def __init__(self, url: str) -> None:
        """Initialise a url from string form"""
        url = url[:-1] if url.endswith("/") else url

        _url = urllib.parse.urlparse(url)
        self._scheme: str = _url.scheme
        self._path: str = _url.path
        self._host: str | None = _url.hostname
        self._port: int | None = _url.port
        self._fragment: str = _url.fragment

    def __truediv__(self, other: str) -> Self:
        """Define URL extension through use of '/'"""
        _new = copy.deepcopy(self)
        _new /= other
        return _new

    def __repr__(self) -> str:
        """Representation of URL"""
        _out_str = f"{self.__class__.__module__}.{self.__class__.__qualname__}"
        return f"{_out_str}(url={self.__str__()!r})"

    @pydantic.validate_call
    def __itruediv__(self, other: str) -> Self:
        """Define URL extension through use of '/'"""
        other = other[1:] if other.startswith("/") else other
        other = other[:-1] if other.endswith("/") else other

        self._path = f"{self._path}/{other}" if other else self._path
        return self

    @property
    def scheme(self) -> str:
        return self._scheme

    @property
    def path(self) -> str:
        return self._path

    @property
    def hostname(self) -> str | None:
        return self._host

    @property
    def fragment(self) -> str:
        return self._fragment

    @property
    def port(self) -> int | None:
        return self._port

    def __str__(self) -> str:
        """Construct string form of the URL"""
        _out_str: str = ""
        if self.scheme:
            _out_str += f"{self.scheme}://"
        if self.hostname:
            _out_str += self.hostname
        if self.port:
            _out_str += f":{self.port}"
        if self.path:
            _out_str += self.path
        if self.fragment:
            _out_str += self.fragment
        return _out_str
