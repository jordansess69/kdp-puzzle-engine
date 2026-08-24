"""Windows Credential Manager storage for marketplace secrets.

Design rules (agreed for the Etsy Connection + Draft Automation batch):

- Dependency-free: uses ``ctypes`` against ``advapi32.dll`` (CredWriteW /
  CredReadW / CredDeleteW), so no third-party packages are introduced.
- Stores one generic credential per integration under a stable target name
  ("KDPuzzleEngine/<platform>"), persisted for the local machine user.
- Secrets live ONLY inside Windows' encrypted credential store; this module
  never writes plaintext secret files, never logs values, and its reprs are
  redacted.
- Every function is safe to import on any OS: the DLL is bound lazily and
  non-Windows platforms simply report "unavailable" instead of crashing
  (tests monkeypatch the module-level functions, they never touch the real
  store).
"""

from __future__ import annotations

import ctypes
import json
import sys
from dataclasses import dataclass
from typing import Optional

CRED_TYPE_GENERIC = 1
CRED_PERSIST_LOCAL_MACHINE = 0x2
_CRED_MAX_BLOB_SIZE = 5 * 512  # matches the documented CRED_MAX_CREDENTIAL_BLOB_SIZE

_ERROR_MESSAGES = {
    1168: "No credential is stored for this integration yet.",
    87: "Windows rejected the credential parameters.",
}


class WinCredError(Exception):
    """Raised when the Windows credential store refuses an operation."""

    def __init__(self, operation: str, error_code: int):
        self.operation = operation
        self.error_code = int(error_code)
        hint = _ERROR_MESSAGES.get(self.error_code, "")
        message = f"Windows Credential Manager failed during {operation} (error {self.error_code})."
        if hint:
            message += f" {hint}"
        super().__init__(message)


def credential_target(platform: str) -> str:
    """Stable target name, e.g. 'KDPuzzleEngine/Etsy'."""
    return f"KDPuzzleEngine/{str(platform).strip()}"


@dataclass(frozen=True)
class _CredBlob:
    user_name: str
    secret_bytes: bytes


def _advapi32():
    if sys.platform != "win32":
        return None
    try:
        return ctypes.WinDLL("advapi32", use_last_error=True)
    except OSError:
        return None


def _write_raw(target: str, user_name: str, secret_bytes: bytes) -> None:
    """ctypes binding for CredWriteW with a GENERIC, machine-persisted blob."""
    class CREDENTIAL(ctypes.Structure):
        _fields_ = [
            ("Flags", ctypes.c_uint32),
            ("Type", ctypes.c_uint32),
            ("TargetName", ctypes.c_wchar_p),
            ("Comment", ctypes.c_wchar_p),
            ("LastWritten", ctypes.c_uint64),
            ("CredentialBlobSize", ctypes.c_uint32),
            ("CredentialBlob", ctypes.POINTER(ctypes.c_byte)),
            ("Persist", ctypes.c_uint32),
            ("AttributeCount", ctypes.c_uint32),
            ("Attributes", ctypes.c_void_p),
            ("TargetAlias", ctypes.c_wchar_p),
            ("UserName", ctypes.c_wchar_p),
        ]

    if len(secret_bytes) > _CRED_MAX_BLOB_SIZE:
        raise WinCredError("store", 87)
    blob = (ctypes.c_byte * len(secret_bytes)).from_buffer_copy(secret_bytes or b"\x00")
    credential = CREDENTIAL()
    credential.Flags = 0
    credential.Type = CRED_TYPE_GENERIC
    credential.TargetName = target
    credential.Comment = "KDP Puzzle Engine marketplace connection"
    credential.CredentialBlobSize = len(secret_bytes)
    # Keep a reference alive for the duration of the call.
    credential.CredentialBlob = ctypes.cast(blob, ctypes.POINTER(ctypes.c_byte))
    credential.Persist = CRED_PERSIST_LOCAL_MACHINE
    credential.AttributeCount = 0
    credential.Attributes = None
    credential.TargetAlias = None
    credential.UserName = user_name or ""
    advapi32 = _advapi32()
    if advapi32 is None or not hasattr(advapi32, "CredWriteW"):
        raise WinCredError("store", 0)
    if not advapi32.CredWriteW(ctypes.byref(credential), 0):
        raise WinCredError("store", ctypes.get_last_error())


def _read_raw(target: str) -> Optional[_CredBlob]:
    """ctypes binding for CredReadW; returns None when nothing is stored."""

    class CREDENTIAL(ctypes.Structure):
        _fields_ = [
            ("Flags", ctypes.c_uint32),
            ("Type", ctypes.c_uint32),
            ("TargetName", ctypes.c_wchar_p),
            ("Comment", ctypes.c_wchar_p),
            ("LastWritten", ctypes.c_uint64),
            ("CredentialBlobSize", ctypes.c_uint32),
            ("CredentialBlob", ctypes.POINTER(ctypes.c_byte)),
            ("Persist", ctypes.c_uint32),
            ("AttributeCount", ctypes.c_uint32),
            ("Attributes", ctypes.c_void_p),
            ("TargetAlias", ctypes.c_wchar_p),
            ("UserName", ctypes.c_wchar_p),
        ]

    advapi32 = _advapi32()
    if advapi32 is None or not hasattr(advapi32, "CredReadW"):
        raise WinCredError("load", 0)
    pointer = ctypes.POINTER(CREDENTIAL)()
    if not advapi32.CredReadW(target, CRED_TYPE_GENERIC, 0, ctypes.byref(pointer)):
        error_code = ctypes.get_last_error()
        if error_code == 1168:  # ERROR_NOT_FOUND: absent credential is normal.
            return None
        raise WinCredError("load", error_code)
    try:
        entry = pointer.contents
        size = int(entry.CredentialBlobSize)
        blob = bytes(ctypes.string_at(entry.CredentialBlob, size)) if size else b""
        return _CredBlob(user_name=entry.UserName or "", secret_bytes=blob)
    finally:
        ctypes.windll.kernel32.LocalFree(pointer)


def _delete_raw(target: str) -> bool:
    """ctypes binding for CredDeleteW; True when something was deleted."""
    advapi32 = _advapi32()
    if advapi32 is None or not hasattr(advapi32, "CredDeleteW"):
        raise WinCredError("delete", 0)
    if advapi32.CredDeleteW(target, CRED_TYPE_GENERIC, 0):
        return True
    error_code = ctypes.get_last_error()
    if error_code == 1168:
        return False
    raise WinCredError("delete", error_code)


# Test seam: tests monkeypatch these three wrappers rather than raw ctypes,
# so the real Windows credential store is never touched by automation.
_write_impl = _write_raw
_read_impl = _read_raw
_delete_impl = _delete_raw


def store_secret(platform: str, payload: dict) -> None:
    """Store a JSON payload as one generic credential."""
    blob = json.dumps(payload, sort_keys=True).encode("utf-8")
    _write_impl(credential_target(platform), "KDPuzzleEngine", blob)


def load_secret(platform: str) -> Optional[dict]:
    """Return the stored JSON payload, or None when nothing is saved yet."""
    found = _read_impl(credential_target(platform))
    if found is None:
        return None
    try:
        parsed = json.loads(found.secret_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WinCredError("load", 87) from exc
    return parsed if isinstance(parsed, dict) else None


def delete_secret(platform: str) -> bool:
    """Forget stored credentials; False when there was nothing to delete."""
    return bool(_delete_impl(credential_target(platform)))


def is_available() -> bool:
    """True when this platform can use the Windows credential store."""
    return sys.platform == "win32" and _advapi32() is not None
