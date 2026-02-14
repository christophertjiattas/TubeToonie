from __future__ import annotations

from dataclasses import dataclass
import os
import platform


SERVICE_NAME = "tubetoonie"
USERNAME_KEY = "tonie_username"
PASSWORD_KEY = "tonie_password"


@dataclass(frozen=True)
class TonieCredentials:
    username: str
    password: str


def _getenv(name: str) -> str:
    return os.getenv(name, "").strip()


def _is_supported_os() -> bool:
    # We can still run elsewhere, but the request explicitly targets macOS + Windows.
    system = platform.system().lower()
    return system in {"darwin", "windows"}


def _import_keyring():
    try:
        import keyring  # type: ignore

        return keyring
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "Secure credential storage requires the 'keyring' package. "
            "Install it with: .venv/bin/python -m pip install keyring"
        ) from exc


def supports_secure_store() -> bool:
    if not _is_supported_os():
        return False

    try:
        _import_keyring()
        return True
    except ModuleNotFoundError:
        return False


def get_tonie_credentials_from_env() -> TonieCredentials | None:
    username = _getenv("TONIE_USERNAME")
    password = _getenv("TONIE_PASSWORD")
    if not username or not password:
        return None
    return TonieCredentials(username=username, password=password)


def get_tonie_credentials_from_keyring() -> TonieCredentials | None:
    if not _is_supported_os():
        return None

    keyring = _import_keyring()

    username = keyring.get_password(SERVICE_NAME, USERNAME_KEY)
    password = keyring.get_password(SERVICE_NAME, PASSWORD_KEY)

    if not username or not password:
        return None

    return TonieCredentials(username=str(username), password=str(password))


def get_tonie_credentials() -> TonieCredentials | None:
    """Resolve Tonie credentials.

    Order:
    1) Environment variables
    2) OS secure store (macOS Keychain / Windows Credential Manager)

    Streamlit may also pass explicit credentials separately; this function is the
    non-UI default.
    """

    return get_tonie_credentials_from_env() or get_tonie_credentials_from_keyring()


def set_tonie_credentials_in_keyring(creds: TonieCredentials) -> None:
    if not _is_supported_os():
        raise OSError("Secure storage is only supported on macOS and Windows for this app.")

    keyring = _import_keyring()

    keyring.set_password(SERVICE_NAME, USERNAME_KEY, creds.username)
    keyring.set_password(SERVICE_NAME, PASSWORD_KEY, creds.password)


def delete_tonie_credentials_from_keyring() -> None:
    if not _is_supported_os():
        return

    keyring = _import_keyring()

    # Delete best-effort.
    try:
        keyring.delete_password(SERVICE_NAME, USERNAME_KEY)
    except Exception:
        pass

    try:
        keyring.delete_password(SERVICE_NAME, PASSWORD_KEY)
    except Exception:
        pass
