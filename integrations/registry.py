"""Lookup table connecting marketplace keys to adapter factories.

Kept deliberately tiny: future Hub code calls :func:`get_integration` without
special-casing Etsy.  Unknown keys return ``None`` (rather than raising) so
callers can degrade gracefully to the manual Level 1/2 workflows that already
work today.  Only platforms with real, reviewed adapters are registered.

Universal Publishing Foundation additions (backwards compatible):

- Registration is now an explicit dict (:data:`_FACTORIES`); adding a future
  integration means one entry here plus its own package - no dynamic module
  scanning, no magic imports.
- :func:`integration_metadata` / :func:`get_integration_info` expose static
  discovery metadata for a future GUI (key, display name, api vs export-only
  vs manual, active/planned).  This list intentionally covers channels that
  have NO adapter yet so the UI can show truthful "Export Only"/"Not
  Connected" rows; it is metadata only and never instantiates anything.
- :func:`available_keys` still reports ONLY keys with working adapters.
"""

from typing import Optional

from integrations.base import PublishingIntegration


# Explicit registry: registry key -> factory. No scanning, no magic imports.
_FACTORIES = {}


def register_integration(key: str, factory):
    """Explicitly register an adapter factory under *key* (idempotent)."""
    normalized = _normalize(key)
    if not normalized:
        raise ValueError("An integration key is required.")
    _FACTORIES[normalized] = factory


def unregister_integration(key: str) -> bool:
    """Remove a registration; mainly for tests."""
    return _FACTORIES.pop(_normalize(key), None) is not None


def _normalize(key) -> str:
    return (str(key or "")).strip().lower()


def get_integration(key, **kwargs) -> Optional[PublishingIntegration]:
    """Return the adapter for *key*, or None when no integration exists.

    Keyword arguments are forwarded to the adapter factory so callers (and
    tests) can inject credential providers and HTTP transports.
    """
    normalized = _normalize(key)
    factory = _FACTORIES.get(normalized)
    if factory is None:
        return None
    return factory(**kwargs)


def available_keys():
    """Keys with a registered, working adapter, in stable order."""
    ordered = ("etsy",)
    extras = tuple(k for k in sorted(_FACTORIES) if k not in ordered)
    return ordered + extras


# ---------------------------------------------------------------------------
# Discovery metadata for a future GUI (static facts only; nothing instantiated)
# ---------------------------------------------------------------------------

_MODE_API = "api"
_MODE_EXPORT_ONLY = "export_only"
_MODE_MANUAL = "manual"

_STATUS_ACTIVE = "active"        # working adapter exists today
_STATUS_PLANNED = "planned"      # manual workflow only; adapter may come later

_INTEGRATION_INFO = (
    {"key": "etsy", "display_name": "Etsy", "mode": _MODE_API,
     "requires_connection": True, "status": _STATUS_ACTIVE},
    {"key": "amazon", "display_name": "Amazon KDP", "mode": _MODE_EXPORT_ONLY,
     "requires_connection": False, "status": _STATUS_PLANNED},
    {"key": "ingram", "display_name": "IngramSpark", "mode": _MODE_EXPORT_ONLY,
     "requires_connection": False, "status": _STATUS_PLANNED},
    {"key": "website", "display_name": "Direct Website", "mode": _MODE_MANUAL,
     "requires_connection": False, "status": _STATUS_PLANNED},
    {"key": "lulu", "display_name": "Lulu Direct", "mode": _MODE_EXPORT_ONLY,
     "requires_connection": False, "status": _STATUS_PLANNED},
    {"key": "bookvault", "display_name": "BookVault", "mode": _MODE_EXPORT_ONLY,
     "requires_connection": False, "status": _STATUS_PLANNED},
    {"key": "barnes_noble", "display_name": "Barnes & Noble", "mode": _MODE_EXPORT_ONLY,
     "requires_connection": False, "status": _STATUS_PLANNED},
)


def integration_metadata() -> list[dict]:
    """Fresh copies of the discovery rows, in canonical marketplace order."""
    return [dict(entry) for entry in _INTEGRATION_INFO]


def get_integration_info(key) -> Optional[dict]:
    """Discovery row for one key (works with or without an installed adapter)."""
    normalized = _normalize(key)
    for entry in _INTEGRATION_INFO:
        if entry["key"] == normalized:
            return dict(entry)
    return None


def _register_builtin_integrations():
    """Wire the built-in adapters. Kept in one place for review clarity."""
    from integrations.etsy.connection import create_etsy_integration

    register_integration("etsy", create_etsy_integration)


_register_builtin_integrations()
