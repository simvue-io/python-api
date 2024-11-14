import typing
import abc
from simvue.api.objects.base import SimvueObject, staging_check


class Storage(SimvueObject):
    def __init__(self, identifier: typing.Optional[str] = None, **kwargs) -> None:
        """Retrieve an alert from the Simvue server by identifier"""
        self._label = "storage"
        self._endpoint = self._label
        super().__init__(identifier, **kwargs)

    @abc.abstractclassmethod
    def new(cls, **_):
        pass

    @property
    @staging_check
    def name(self) -> str:
        """Retrieve the name for this storage"""
        return self._get_attribute("name")

    @name.setter
    def name(self, name: list[str]) -> None:
        """Set name assigned to this folder"""
        self._staging["name"] = name

    @property
    def type(self) -> str:
        """Retrieve the type of storage"""
        return self._get_attribute("type")

    @property
    @staging_check
    def default(self) -> bool:
        """Retrieve if this is the default storage for the user"""
        return self._get_attribute("default")

    @default.setter
    def default(self, is_default: bool) -> None:
        """Set this storage to be the default"""
        self._staging["default"] = is_default

    @property
    @staging_check
    def tenant_usable(self) -> bool:
        """Retrieve if this is usable by the current user tenant"""
        return self._get_attribute("tenant_usable")

    @tenant_usable.setter
    def tenant_usable(self, is_tenant_usable: bool) -> None:
        """Set this storage to be usable by the current user tenant"""
        self._staging["tenant_usable"] = is_tenant_usable

    @property
    def disable_check(self) -> bool:
        """Retrieve if checks are disabled for this storage"""
        return self._get_attribute("disable_check")
