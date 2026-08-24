"""Lookup table connecting marketplace keys to adapter factories.

Kept deliberately tiny: future Hub code calls :func:`get_integration` without
special-casing Etsy.  Unknown keys return ``None`` (rather than raising) so
callers can degrade gracefully to the manual Level 1/2 workflows that already
work today.  Only platforms with real, reviewed adapters are registered.
"""

from typing import Optional

from integrations.base import PublishingIntegration


def get_integration(key, **kwargs) -> Optional[PublishingIntegration]:
    """Return the adapter for *key*, or None when no integration exists.

    Keyword arguments are forwarded to the adapter factory so callers (and
    tests) can inject credential providers and HTTP transports.
    """
    normalized = (key or "").strip().lower()
    if normalized == "etsy":
        from integrations.etsy.connection import create_etsy_integration

        return create_etsy_integration(**kwargs)
    return None


def available_keys():
    """Keys with a registered Phase A adapter, in stable order."""
    return ("etsy",)
