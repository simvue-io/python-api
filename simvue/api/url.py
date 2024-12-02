import typing
import urllib.parse
import copy


class URL:
    def __init__(self, url: str) -> None:
        if url.endswith("/"):
            url = url[:-1]

        _url = urllib.parse.urlparse(url)
        self._scheme: str = _url.scheme
        self._path: str = _url.path
        self._host: str | None = _url.hostname
        self._port: int | None = _url.port
        self._fragment: str = _url.fragment

    def __truediv__(self, other: str) -> typing.Self:
        _new = copy.deepcopy(self)
        _new /= other
        return _new

    def __itruediv__(self, other: str) -> typing.Self:
        if other.startswith("/"):
            other = other[1:]
        if other.endswith("/"):
            other = other[:-1]
        self._path = f"{self._path}/{other}"
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
