import pydantic
import typing
from simvue.api.objects.base import SimvueObject, staging_check, write_only


class User(SimvueObject):
    @classmethod
    @pydantic.validate_call
    def new(
        cls,
        *,
        username: str,
        fullname: str,
        email: pydantic.EmailStr,
        manager: bool,
        admin: bool,
        readonly: bool,
        welcome: bool,
        tenant: str,
        enabled: bool = True,
        offline: bool = False,
    ) -> typing.Self:
        _user_info: dict[str, str | bool] = {
            "username": username,
            "fullname": fullname,
            "email": email,
            "manager": manager,
            "readonly": readonly,
            "welcome": welcome,
            "admin": admin,
            "enabled": enabled,
        }
        _user = User(user=_user_info, tenant=tenant, offline=offline)
        _user.offline_mode(offline)
        return _user  # type: ignore

    @property
    @staging_check
    def username(self) -> str:
        if self.id and self.id.startswith("offline_"):
            return self._get_attribute("user")["username"]
        return self._get_attribute("username")

    @username.setter
    @write_only
    @pydantic.validate_call
    def username(self, username: str) -> None:
        self._staging["username"] = username

    @property
    @staging_check
    def fullname(self) -> str:
        if self.id and self.id.startswith("offline_"):
            return self._get_attribute("user")["fullname"]
        return self._get_attribute("fullname")

    @fullname.setter
    @write_only
    @pydantic.validate_call
    def fullname(self, fullname: str) -> None:
        self._staging["fullname"] = fullname

    @property
    @staging_check
    def manager(self) -> bool:
        if self.id and self.id.startswith("offline_"):
            return self._get_attribute("user")["manager"]
        return self._get_attribute("manager")

    @manager.setter
    @write_only
    @pydantic.validate_call
    def manager(self, manager: bool) -> None:
        self._staging["manager"] = manager

    @property
    @staging_check
    def admin(self) -> bool:
        if self.id and self.id.startswith("offline_"):
            return self._get_attribute("user")["admin"]
        return self._get_attribute("admin")

    @admin.setter
    @write_only
    @pydantic.validate_call
    def admin(self, admin: bool) -> None:
        self._staging["admin"] = admin

    @property
    @staging_check
    def readonly(self) -> bool:
        if self.id and self.id.startswith("offline_"):
            return self._get_attribute("user")["readonly"]
        return self._get_attribute("readonly")

    @readonly.setter
    @write_only
    @pydantic.validate_call
    def readonly(self, readonly: bool) -> None:
        self._staging["readonly"] = readonly
