import typing
from .base import SimvueObject


class Metrics(SimvueObject):
    def __init__(
        self,
        run_identifier: typing.Optional[str] = None,
        read_only: bool = False,
        **kwargs,
    ) -> None:
        super().__init__(run_identifier, read_only, **kwargs)

    @property
    def url(self) -> str:
        return f"{self._base_url}/{self._url_path}"
