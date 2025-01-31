"""
Simvue Users
============

Contains a class for remotely connecting to Simvue users, or defining
a new user given relevant arguments.

"""

import pydantic

try:
    from typing import Self
except ImportError:
    from typing_extensions import Self
from simvue.api.objects.base import SimvueObject, staging_check, write_only


class User(SimvueObject):
    """Class for interacting with a user instance on the server."""

    @classmethod
    @pydantic.validate_call
    def new(
        cls,
        *,
        username: str,
        fullname: str,
        email: pydantic.EmailStr,
        is_manager: bool,
        is_admin: bool,
        is_readonly: bool,
        welcome: bool,
        tenant: str,
        enabled: bool = True,
        offline: bool = False,
        **_,
    ) -> Self:
        """Create a new user on the Simvue server.

        Requires administrator privileges.

        Parameters
        ----------
        username: str
            the username for this user
        fullname: str
            the full name for this user
        email: str
            the email for this user
        is_manager : bool
            assign the manager role to this user
        is_admin : bool
            assign the administrator role to this user
        is_readonly : bool
            given only read access to this user
        welcome : bool
            display welcome message to user
        tenant : str
            the tenant under which to assign this user
        enabled: bool, optional
            whether to enable the user on creation, default is True
        offline: bool, optional
            create in offline mode, default is False.

        Returns
        -------
        User
            a user instance with staged changes

        """
        _user_info: dict[str, str | bool] = {
            "username": username,
            "fullname": fullname,
            "email": email,
            "is_manager": is_manager,
            "is_readonly": is_readonly,
            "welcome": welcome,
            "is_admin": is_admin,
            "is_enabled": enabled,
        }
        _user = User(
            user=_user_info,
            tenant=tenant,
            offline=offline,
            _read_only=False,
            _offline=offline,
        )
        _user._staging |= _user_info
        return _user

    @classmethod
    def get(
        cls, *, count: int | None = None, offset: int | None = None, **kwargs
    ) -> dict[str, "User"]:
        """Retrieve users from the Simvue server.

        Parameters
        ----------
        count : int, optional
            limit the number of results, default is no limit.
        offset : int, optional
            start index for results, default is 0.

        Yields
        ------
        User
            user instance representing user on server
        """
        # Currently no user filters
        kwargs.pop("filters", None)
        return super().get(count=count, offset=offset, **kwargs)

    @property
    @staging_check
    def username(self) -> str:
        """Retrieve the username for the user"""
        if self.id and self.id.startswith("offline_"):
            return self._get_attribute("user")["username"]
        return self._get_attribute("username")

    @username.setter
    @write_only
    @pydantic.validate_call
    def username(self, username: str) -> None:
        """Set the username for the user"""
        self._staging["username"] = username

    @property
    @staging_check
    def fullname(self) -> str:
        """Retrieve the full name for the user"""
        if self.id and self.id.startswith("offline_"):
            return self._get_attribute("user")["fullname"]
        return self._get_attribute("fullname")

    @fullname.setter
    @write_only
    @pydantic.validate_call
    def fullname(self, fullname: str) -> None:
        """Set the full name for the user"""
        self._staging["fullname"] = fullname

    @property
    @staging_check
    def is_manager(self) -> bool:
        """Retrieve if the user has manager privileges"""
        if self.id and self.id.startswith("offline_"):
            return self._get_attribute("user")["is_manager"]
        return self._get_attribute("is_manager")

    @is_manager.setter
    @write_only
    @pydantic.validate_call
    def is_manager(self, is_manager: bool) -> None:
        """Set if the user has manager privileges"""
        self._staging["is_manager"] = is_manager

    @property
    @staging_check
    def is_admin(self) -> bool:
        """Retrieve if the user has admin privileges"""
        if self.id and self.id.startswith("offline_"):
            return self._get_attribute("user")["is_admin"]
        return self._get_attribute("is_admin")

    @is_admin.setter
    @write_only
    @pydantic.validate_call
    def is_admin(self, is_admin: bool) -> None:
        """Set if the user has admin privileges"""
        self._staging["is_admin"] = is_admin

    @property
    def deleted(self) -> bool:
        """Retrieve if the user is pending deletion"""
        if self.id and self.id.startswith("offline_"):
            return self._get_attribute("user")["is_deleted"]
        return self._get_attribute("is_deleted")

    @property
    @staging_check
    def is_readonly(self) -> bool:
        """Retrieve if the user has read-only access"""
        if self.id and self.id.startswith("offline_"):
            return self._get_attribute("user")["is_readonly"]
        return self._get_attribute("is_readonly")

    @is_readonly.setter
    @write_only
    @pydantic.validate_call
    def is_readonly(self, is_readonly: bool) -> None:
        """Set if the user has read-only access"""
        self._staging["is_readonly"] = is_readonly

    @property
    @staging_check
    def enabled(self) -> bool:
        """Retrieve if the user is enabled"""
        if self.id and self.id.startswith("offline_"):
            return self._get_attribute("user")["is_enabled"]
        return self._get_attribute("is_enabled")

    @enabled.setter
    @write_only
    @pydantic.validate_call
    def enabled(self, is_enabled: bool) -> None:
        """Set if the user is enabled"""
        self._staging["is_enabled"] = is_enabled

    @property
    @staging_check
    def email(self) -> str:
        """Retrieve the user email"""
        if self.id and self.id.startswith("offline_"):
            return self._get_attribute("user")["email"]
        return self._get_attribute("email")

    @email.setter
    @write_only
    @pydantic.validate_call
    def email(self, email: str) -> None:
        """Set the user email"""
        self._staging["email"] = email
