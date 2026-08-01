"""API key storage backed by the operating system credential vault."""

from __future__ import annotations

from typing import Protocol


class SecretStoreError(RuntimeError):
    """The system credential vault is unavailable."""


class SecretStore(Protocol):
    def get(self, name: str) -> str | None: ...

    def set(self, name: str, value: str) -> None: ...

    def delete(self, name: str) -> None: ...


class KeyringSecretStore:
    """Store secrets in macOS Keychain or Windows Credential Locker."""

    def __init__(self, service_name: str = "zhiming-life") -> None:
        self.service_name = service_name

    @staticmethod
    def _keyring():
        try:
            import keyring
        except ImportError as exc:  # pragma: no cover - desktop package supplies it
            raise SecretStoreError("系统密钥存储组件未安装") from exc
        return keyring

    def get(self, name: str) -> str | None:
        return self._keyring().get_password(self.service_name, name)

    def set(self, name: str, value: str) -> None:
        self._keyring().set_password(self.service_name, name, value)

    def delete(self, name: str) -> None:
        keyring = self._keyring()
        try:
            keyring.delete_password(self.service_name, name)
        except keyring.errors.PasswordDeleteError:
            return


class MemorySecretStore:
    """Small in-memory implementation used by tests and previews."""

    def __init__(self, initial: dict[str, str] | None = None) -> None:
        self._values = dict(initial or {})

    def get(self, name: str) -> str | None:
        return self._values.get(name)

    def set(self, name: str, value: str) -> None:
        self._values[name] = value

    def delete(self, name: str) -> None:
        self._values.pop(name, None)
