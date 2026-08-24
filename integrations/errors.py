"""Shared error taxonomy for marketplace integrations.

Every integration surfaces failures as one of four classes so callers can
decide between retrying (TransientError), asking the user to reconnect
(AuthError), reporting a fixable request problem (PermanentError), or walking
the user through setup (NotConfiguredError).

Security rule: exception messages must always be safe to show in the GUI and
in logs.  Anything derived from raw responses or requests passes through
:func:`redact_text` before it reaches an exception.  Secrets must never be
embedded in error text in the first place, but the redaction helpers are the
second line of defence.
"""

import re

_MASK = "[REDACTED]"

# Bearer tokens pasted verbatim into debug strings ("Bearer 12345678.AbCd...").
_BEARER_PATTERN = re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]{8,}")

# Key=value / key: value assignments for well-known secret field names, e.g.
# "access_token: 12345678.AbCd..." appearing in a dumped payload.
_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)\b("
    r"access_token|refresh_token|shared_secret|client_secret|code_verifier|legacy_token"
    r")(['\"]?\s*[:=]\s*)['\"]?[A-Za-z0-9._~+/=-]{8,}"
)

# Header names whose values must never appear in logs or error summaries.
SENSITIVE_HEADER_HINTS = (
    "authorization",
    "token",
    "secret",
    "key",
    "password",
    "cookie",
)


def redact_text(text, extra_secrets=(), mask=_MASK):
    """Return *text* with known secret values and token patterns masked.

    ``extra_secrets`` are concrete credential values the caller knows about
    (bearer tokens, shared secrets, PKCE verifiers).  Values shorter than 4
    characters are ignored to avoid mangling ordinary words.
    """
    result = str(text)
    for secret in extra_secrets:
        if secret and len(str(secret)) >= 4:
            result = result.replace(str(secret), mask)
    result = _BEARER_PATTERN.sub("Bearer " + mask, result)
    result = _ASSIGNMENT_PATTERN.sub(lambda m: m.group(1) + m.group(2) + mask, result)
    return result


def is_sensitive_header(name):
    """True when a header's value must never be echoed into logs/errors."""
    lowered = str(name).lower()
    return any(hint in lowered for hint in SENSITIVE_HEADER_HINTS)


class IntegrationError(Exception):
    """Base class for all integration failures; ``message`` is pre-sanitized."""

    def __init__(self, message, *, status_code=None):
        self.message = str(message)
        self.status_code = status_code
        super().__init__(self.message)

    def __str__(self):
        return self.message


class AuthError(IntegrationError):
    """Remote rejected or expired credentials; the user should reconnect."""


class TransientError(IntegrationError):
    """Network trouble, 429 or 5xx that may succeed after a bounded retry."""


class PermanentError(IntegrationError):
    """The request itself is unfixable (other 4xx); retrying will not help."""


class NotConfiguredError(IntegrationError):
    """Required credentials/configuration are missing entirely."""


class UnsupportedCapabilityError(IntegrationError):
    """The adapter was asked to do something it never advertised support for.

    Raised ONLY by the opt-in universal contract (integrations.foundation);
    the Phase A read-only surface and the committed Etsy draft automation
    keep their exact existing shapes.  Unsupported operations must fail
    loudly like this - never silently no-op - so the GUI can trust that a
    returned result means something really happened.
    """
