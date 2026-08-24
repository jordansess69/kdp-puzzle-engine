"""Etsy Open API v3 OAuth foundation (Phase A: read-only).

Implements only the building blocks needed to verify a connection:

- PKCE verifier/challenge generation (Etsy requires PKCE on every
  authorization flow request).
- Authorization URL construction against ``https://www.etsy.com/oauth/connect``.
- OAuth token response parsing and a refresh-request builder (structure only;
  wiring persistence is a later, separately approved phase).
- The ``x-api-key`` header builder.  Current Etsy documentation specifies
  ``x-api-key: <keystring>:<shared_secret>`` on every request; older guidance
  and tooling use the bare keystring.  The helper sends the documented
  ``keystring:shared_secret`` form when a shared secret is configured and the
  bare keystring otherwise.

Official references (verified August 2026):
- https://developer.etsy.com/documentation/essentials/authentication
- https://developer.etsy.com/documentation/reference

Scope policy for Phase A: request the MINIMUM read scope needed to verify the
account and shop identity, which is ``shops_r``.  Write scopes (``listings_w``,
``shops_w``, ``transactions_w``) and the destructive ``listings_d`` scope are
deliberately NOT requested here.  Scope changes require the user to
re-authorize, so keeping Phase A minimal keeps later phase upgrades clean.

Credential handling policy:
- Credentials arrive from environment variables or an injected provider.
- Nothing in this module writes tokens anywhere; secrets exist only in memory.
- All reprs are redacted so accidental logging cannot leak values.
"""

import base64
import hashlib
import secrets
import urllib.parse
from dataclasses import dataclass
from typing import Mapping, Optional, Tuple

from integrations.errors import PermanentError
from integrations.http import HttpRequest

ETSY_AUTHORIZE_URL = "https://www.etsy.com/oauth/connect"
ETSY_TOKEN_URL = "https://api.etsy.com/v3/public/oauth/token"

# Minimum scopes for read-only identity/shop verification (see docstring).
READ_ONLY_SCOPES: Tuple[str, ...] = ("shops_r",)

# Scopes required by the approved draft-automation phase.  Read access to
# listings enables truthful reconciliation and duplicate scans; write access
# is limited to CREATING drafts and uploading their files/images.  The
# destructive ``listings_d`` scope is deliberately never requested anywhere.
DRAFT_SCOPES: Tuple[str, ...] = ("shops_r", "listings_r", "listings_w")

# RFC 7636 / Etsy requirement: 43-128 chars from [A-Za-z0-9._~-].
_PKCE_VERIFIER_BYTES = 32  # -> 43-char url-safe base64 verifier


@dataclass(frozen=True)
class PkcePair:
    verifier: str
    challenge: str


@dataclass(frozen=True)
class TokenSet:
    """Parsed OAuth token payload.  Repr/str are always redacted."""

    access_token: str
    refresh_token: str = ""
    expires_in: int = 0
    token_type: str = "Bearer"
    scope: str = ""

    @property
    def has_refresh_token(self):
        return bool(self.refresh_token)

    def _redacted_repr(self):
        return (
            f"<EtsyTokenSet access=[REDACTED] refresh={'present' if self.refresh_token else 'absent'} "
            f"expires_in={self.expires_in} token_type={self.token_type!r} "
            f"scope={self.scope!r}>"
        )

    def __repr__(self):
        return self._redacted_repr()

    def __str__(self):
        return self._redacted_repr()


def pkce_challenge_from_verifier(verifier):
    """S256 code challenge: url-safe base64 of SHA-256(verifier), padding stripped."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def generate_pkce_pair(random_bytes=_PKCE_VERIFIER_BYTES):
    """Generate a fresh (verifier, challenge) pair using cryptographically secure randomness."""
    if not 16 <= int(random_bytes) <= 96:
        # Keep generated verifiers comfortably inside Etsy's 43-128 char window.
        raise ValueError("PKCE random_bytes must be between 16 and 96")
    verifier = secrets.token_urlsafe(int(random_bytes))
    return PkcePair(verifier=verifier, challenge=pkce_challenge_from_verifier(verifier))


def build_authorization_url(
    *,
    client_id,
    redirect_uri,
    code_challenge,
    state=None,
    scopes=READ_ONLY_SCOPES,
):
    """Build the Etsy authorization URL the user visits in their browser.

    ``redirect_uri`` must be the exact https callback registered on the Etsy
    app (Etsy enforces an exact, case-sensitive match and requires https).
    """
    if not client_id:
        raise PermanentError("Etsy authorization requires the app keystring (client_id)")
    if not str(redirect_uri).lower().startswith("https://"):
        # Fail before sending the user anywhere: Etsy would reject http anyway.
        raise PermanentError(
            "Etsy callback URLs must be HTTPS and match the app's registered callback"
        )
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": " ".join(scopes),
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    if state:
        params["state"] = state
    query = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    return f"{ETSY_AUTHORIZE_URL}?{query}"


def parse_token_response(payload: Mapping) -> TokenSet:
    """Parse the JSON body returned by the Etsy token endpoint.

    Raises PermanentError with a generic message (never echoing the payload,
    which contains live credentials) when the response shape is unusable.
    """
    if not isinstance(payload, Mapping):
        raise PermanentError("Unexpected Etsy token response shape")
    access_token = payload.get("access_token")
    if not isinstance(access_token, str) or not access_token.strip():
        raise PermanentError("Etsy token response did not include an access token")
    try:
        expires_in = int(payload.get("expires_in") or 0)
    except (TypeError, ValueError):
        expires_in = 0
    refresh_token = payload.get("refresh_token") or ""
    token_type = payload.get("token_type") or "Bearer"
    scope = payload.get("scope") or ""
    return TokenSet(
        access_token=access_token,
        refresh_token=str(refresh_token),
        expires_in=expires_in,
        token_type=str(token_type),
        scope=str(scope),
    )


def build_x_api_key_header(keystring, shared_secret=""):
    """Value for the mandatory ``x-api-key`` header (see module docstring)."""
    if shared_secret:
        return f"{keystring}:{shared_secret}"
    return keystring


def _token_request(method_specific_fields, extra_headers=None):
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    if extra_headers:
        headers.update(extra_headers)
    body = urllib.parse.urlencode(method_specific_fields).encode("utf-8")
    return HttpRequest(method="POST", url=ETSY_TOKEN_URL, headers=headers, body=body)


def build_authorization_code_request(
    *,
    client_id,
    authorization_code,
    code_verifier,
    redirect_uri=None,
):
    """POST exchanged for an access token after the user grants access.

    The body carries the authorization code and PKCE verifier - both
    short-lived but secret - so callers must never log request bodies.
    """
    fields = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "code": authorization_code,
        "code_verifier": code_verifier,
    }
    if redirect_uri:
        fields["redirect_uri"] = redirect_uri
    return _token_request(fields)


def build_refresh_request(*, client_id, refresh_token):
    """Structure-only refresh grant (Phase B wires storage + scheduling)."""
    fields = {
        "grant_type": "refresh_token",
        "client_id": client_id,
        "refresh_token": refresh_token,
    }
    return _token_request(fields)


def extract_state_and_code(callback_url) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Extract (state, code, error) from an OAuth redirect/callback URL."""
    parsed = urllib.parse.urlsplit(str(callback_url))
    query = urllib.parse.parse_qs(parsed.query)
    state = (query.get("state") or [None])[0]
    code = (query.get("code") or [None])[0]
    error = (query.get("error") or [None])[0]
    return state, code, error
