import pydantic

try:
    from typing import Self
except ImportError:
    from typing_extensions import Self
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
    ) -> Self:
        _user_info: dict[str, str | bool] = {
            "username": username,
            "fullname": fullname,
            "email": email,
            "is_manager": manager,
            "is_readonly": readonly,
            "welcome": welcome,
            "is_admin": admin,
            "is_enabled": enabled,
        }
        _user = User(user=_user_info, tenant=tenant, offline=offline, _read_only=False)
        _user.offline_mode(offline)
        return _user  # type: ignore

    @classmethod
    def get(
        cls, *, count: int | None = None, offset: int | None = None, **kwargs
    ) -> dict[str, "User"]:
        # Currently no user filters
        kwargs.pop("filters", None)
        return super().get(count=count, offset=offset, **kwargs)

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
            return self._get_attribute("user")["is_manager"]
        return self._get_attribute("is_manager")

    @manager.setter
    @write_only
    @pydantic.validate_call
    def manager(self, is_manager: bool) -> None:
        self._staging["is_manager"] = is_manager

    @property
    @staging_check
    def admin(self) -> bool:
        if self.id and self.id.startswith("offline_"):
            return self._get_attribute("user")["is_admin"]
        return self._get_attribute("is_admin")

    @admin.setter
    @write_only
    @pydantic.validate_call
    def admin(self, is_admin: bool) -> None:
        self._staging["is_admin"] = is_admin

    @property
    def deleted(self) -> bool:
        if self.id and self.id.startswith("offline_"):
            return self._get_attribute("user")["is_deleted"]
        return self._get_attribute("is_deleted")

    @property
    @staging_check
    def readonly(self) -> bool:
        if self.id and self.id.startswith("offline_"):
            return self._get_attribute("user")["is_readonly"]
        return self._get_attribute("is_readonly")

    @readonly.setter
    @write_only
    @pydantic.validate_call
    def readonly(self, is_readonly: bool) -> None:
        self._staging["is_readonly"] = is_readonly

    @property
    @staging_check
    def enabled(self) -> bool:
        if self.id and self.id.startswith("offline_"):
            return self._get_attribute("user")["is_enabled"]
        return self._get_attribute("is_enabled")

    @enabled.setter
    @write_only
    @pydantic.validate_call
    def enabled(self, is_enabled: bool) -> None:
        self._staging["is_enabled"] = is_enabled
