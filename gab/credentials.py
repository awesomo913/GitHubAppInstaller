"""
Store GitHub PAT in the OS keyring (Windows Credential Manager, macOS Keychain, Linux Secret Service).
Migrate plaintext token from registry.json on first read, then clear it from disk.
"""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Any, Optional

_LOG = logging.getLogger("gab.credentials")
_warned_unsafe = False
_warn_lock = threading.Lock()

try:
    import keyring
except Exception:  # noqa: BLE001
    keyring = None  # type: ignore[assignment]

SERVICE = "com.githubappmanager.gh"
USERNAME = "github_api_token"
ENV_KEY = "GITHUB_APPMANAGER_TOKEN"


def _keyring_set(password: str) -> bool:
    if keyring is None:
        return False
    try:
        keyring.set_password(SERVICE, USERNAME, password)
        return True
    except Exception as e:  # noqa: BLE001
        _LOG.debug("keyring set failed: %s", e)
        return False


def _keyring_get() -> str:
    if keyring is None:
        return ""
    try:
        p = keyring.get_password(SERVICE, USERNAME)
        return p or ""
    except Exception as e:  # noqa: BLE001
        _LOG.debug("keyring get failed: %s", e)
        return ""


def _keyring_delete() -> None:
    if keyring is None:
        return
    try:
        keyring.delete_password(SERVICE, USERNAME)
    except Exception:  # noqa: BLE001
        pass


def _warn_insecure_file_once() -> None:
    global _warned_unsafe
    with _warn_lock:
        if _warned_unsafe:
            return
        _warned_unsafe = True
    _LOG.warning(
        "GitHub token is stored in registry.json (keyring unavailable). "
        "Install the 'keyring' package; on Windows, Credential Manager is used when available."
    )


class TokenStore:
    """
    Binds a registry file path. Token order: env GITHUB_APPMANAGER_TOKEN, keyring,
    then legacy field in settings (migrates to keyring when possible).
    """

    def __init__(self, registry_path: Path) -> None:
        self._path = registry_path
        self.dirty = False  # True if registry.json must be rewritten (cleared token field)

    def get(self, settings: dict[str, Any]) -> str:
        t = (os.environ.get(ENV_KEY) or "").strip()
        if t:
            return t

        t = _keyring_get().strip()
        if t:
            if (settings or {}).get("token"):
                settings["token"] = ""
                self.dirty = True
            return t

        s = (settings or {}).get("token") or ""
        s = s.strip() if isinstance(s, str) else ""
        if not s:
            return ""

        if _keyring_set(s):
            settings["token"] = ""
            self.dirty = True
        else:
            _warn_insecure_file_once()
        return s

    def set(self, settings: dict[str, Any], token: str) -> None:
        token = (token or "").strip()
        if token:
            if _keyring_set(token):
                settings["token"] = ""
            else:
                settings["token"] = token
                _warn_insecure_file_once()
        else:
            _keyring_delete()
            settings["token"] = ""
        self.dirty = True

    def mark_flushed(self) -> None:
        self.dirty = False
