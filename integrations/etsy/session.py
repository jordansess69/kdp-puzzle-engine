"""Etsy OAuth session: secure storage, code exchange, refresh, auth headers.

This module is the bridge between Phase A's stateless OAuth builders and the
approved draft-automation phase:

- Credential persistence uses the Windows Credential Manager (see
  ``integrations.wincred``) as one JSON blob under "KDPuzzleEngine/Etsy".
  Environment variables keep priority when set, preserving every existing
  Phase A workflow unchanged.
- ``exchange_authorization_code`` and ``refresh_access_token`` execute the
  request builders from ``integrations.etsy.auth`` through the shared
  HttpClient, so retries, error classification, HTTPS enforcement and
  redaction all behave exactly like every other integration call.
- ``EtsySession`` injects the ``x-api-key`` + Bearer headers onto caller-built
  requests so token values never pass through client code, and performs at
  most ONE transparent refresh+retry when Etsy rejects an expired access
  token.  Rotated refresh tokens are handed back to the configured store so
  the next launch keeps working.
"""

from __future__ import annotations

import os
import time
from typing import Callable, Optional, Protocol

from integrations.errors import (
    AuthError,
    NotConfiguredError,
    PermanentError,
    redact_text,
)
from integrations.etsy.auth import (
    ETSY_TOKEN_URL,
    build_refresh_request,
    build_x_api_key_header,
    parse_token_response,
)
from integrations.etsy.connection import (
    ENV_API_KEYSTRING,
    ENV_ACCESS_TOKEN,
    ENV_REFRESH_TOKEN,
    ENV_SHARED_SECRET,
    EtsyCredentials,
)
from integrations.http import HttpClient, HttpRequest
from integrations import wincred

CREDENTIAL_PLATFORM = "Etsy"


class TokenStore(Protocol):
    """Persistence seam for credential blobs (Windows Credential Manager)."""

    def load(self) -> Optional[EtsyCredentials]: ...
    def save(self, credentials: EtsyCredentials) -> None: ...
    def forget(self) -> bool: ...


class WinCredTokenStore:
    """Stores credentials in the Windows Credential Manager; nothing on disk."""

    def load(self) -> Optional[EtsyCredentials]:
        payload = wincred.load_secret(CREDENTIAL_PLATFORM)
        if not payload:
            return None
        return deserialize_credentials(payload)

    def save(self, credentials: EtsyCredentials) -> None:
        wincred.store_secret(CREDENTIAL_PLATFORM, serialize_credentials(credentials))

    def forget(self) -> bool:
        return wincred.delete_secret(CREDENTIAL_PLATFORM)


def serialize_credentials(credentials: EtsyCredentials) -> dict:
    """JSON-safe dict containing only the non-empty fields."""
    return {
        key: value
        for key, value in {
            "api_keystring": credentials.api_keystring,
            "shared_secret": credentials.shared_secret,
            "access_token": credentials.access_token,
            "refresh_token": credentials.refresh_token,
        }.items()
        if value
    }


def deserialize_credentials(payload: dict) -> EtsyCredentials:
    """Rebuild credentials from a stored payload, ignoring unknown keys."""
    if not isinstance(payload, dict):
        raise PermanentError("Stored Etsy credentials have an unexpected shape")
    return EtsyCredentials(
        api_keystring=str(payload.get("api_keystring") or ""),
        shared_secret=str(payload.get("shared_secret") or ""),
        access_token=str(payload.get("access_token") or ""),
        refresh_token=str(payload.get("refresh_token") or ""),
    )


def load_credentials(store: Optional[TokenStore] = None) -> EtsyCredentials:
    """Environment variables first (Phase A compatibility), then secure storage."""
    env = EtsyCredentials(
        api_keystring=os.environ.get(ENV_API_KEYSTRING, "").strip(),
        shared_secret=os.environ.get(ENV_SHARED_SECRET, "").strip(),
        access_token=os.environ.get(ENV_ACCESS_TOKEN, "").strip(),
        refresh_token=os.environ.get(ENV_REFRESH_TOKEN, "").strip(),
    )
    if env.api_keystring and env.access_token:
        return env
    active_store = store if store is not None else WinCredTokenStore()
    stored = active_store.load()
    if stored is None:
        return env
    # Merge so an env-provided app keystring can pair with stored tokens.
    return EtsyCredentials(
        api_keystring=env.api_keystring or stored.api_keystring,
        shared_secret=env.shared_secret or stored.shared_secret,
        access_token=env.access_token or stored.access_token,
        refresh_token=env.refresh_token or stored.refresh_token,
    )


def save_credentials(credentials: EtsyCredentials, store: Optional[TokenStore] = None) -> None:
    active_store = store if store is not None else WinCredTokenStore()
    active_store.save(credentials)


def forget_credentials(store: Optional[TokenStore] = None) -> bool:
    active_store = store if store is not None else WinCredTokenStore()
    return active_store.forget()


def _execute_token_request(request: HttpRequest, *, transport=None, sensitive_values=()):
    try:
        client = HttpClient(
            transport=transport,
            sensitive_values=sensitive_values,
        )
        response = client.send(request)
    except PermanentError as exc:
        # The OAuth token endpoint answers invalid grants (expired code or
        # revoked/expired refresh token) with HTTP 400 + an error payload.
        # For THIS endpoint that is a credentials problem, not an unfixable
        # request bug, so it must surface as AuthError ("reconnect").
        if getattr(exc, "status_code", None) == 400:
            raise AuthError(
                "Etsy rejected the token request; start the connection again."
            ) from exc
        raise
    try:
        payload = response.json()
    except Exception as exc:  # malformed body never leaks its contents
        raise PermanentError("Etsy returned an unreadable token response") from exc
    if isinstance(payload, dict) and payload.get("error"):
        # OAuth failures arrive as 200/400 with an "error" field; classify by status.
        message = redact_text(str(payload.get("error_description") or payload["error"]), sensitive_values)
        if response.status_code in (400, 401):
            raise AuthError(f"Etsy rejected the token request ({message}).", status_code=response.status_code)
        raise PermanentError(f"Etsy refused the token request ({message}).", status_code=response.status_code)
    return parse_token_response(payload)


def exchange_authorization_code(
    *,
    client_id: str,
    authorization_code: str,
    code_verifier: str,
    redirect_uri: str = "",
    transport=None,
):
    """Trade a one-time authorization code for a TokenSet (PKCE flow)."""
    from integrations.etsy.auth import build_authorization_code_request

    secrets = tuple(v for v in (authorization_code, code_verifier) if v and len(str(v)) >= 4)
    request = build_authorization_code_request(
        client_id=client_id,
        authorization_code=authorization_code,
        code_verifier=code_verifier,
        redirect_uri=redirect_uri or None,
    )
    return _execute_token_request(request, transport=transport, sensitive_values=secrets)


def refresh_access_token(*, client_id: str, refresh_token: str, transport=None):
    """Exchange a refresh token for a fresh TokenSet (Etsy rotates them)."""
    request = build_refresh_request(client_id=client_id, refresh_token=refresh_token)
    return _execute_token_request(
        request, transport=transport, sensitive_values=(refresh_token,)
    )


class EtsySession:
    """Authenticated request pipeline shared by every Etsy write/read client.

    - Headers are injected here so callers cannot accidentally omit or log them.
    - On a 401/403 the session refreshes ONCE and retries once; anything else
      propagates the classified error untouched.
    """

    def __init__(
        self,
        credentials_provider: Callable[[], EtsyCredentials],
        *,
        transport=None,
        token_store: Optional[TokenStore] = None,
        sleep=time.sleep,
    ):
        self._provider = credentials_provider
        self._transport = transport
        self._token_store = token_store
        self._sleep = sleep
        self._cached: Optional[EtsyCredentials] = None

    # -- credential plumbing -------------------------------------------------

    def credentials(self) -> EtsyCredentials:
        if self._cached is None:
            self._cached = self._provider()
        if not self._cached.api_keystring:
            raise NotConfiguredError(
                "No Etsy app keystring is stored yet. Use Marketplace connections to connect the account first."
            )
        if not self._cached.access_token and not self._cached.refresh_token:
            raise NotConfiguredError(
                "No Etsy access token is stored yet. Use Marketplace connections to connect the account first."
            )
        return self._cached

    def _store_tokens(self, tokens) -> None:
        current = self.credentials()
        updated = EtsyCredentials(
            api_keystring=current.api_keystring,
            shared_secret=current.shared_secret,
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token or current.refresh_token,
        )
        self._cached = updated
        if self._token_store is not None:
            self._token_store.save(updated)

    def ensure_fresh_token(self) -> None:
        """Refresh proactively when only a refresh token is available."""
        creds = self.credentials()
        if creds.access_token:
            return
        if not creds.refresh_token:
            raise NotConfiguredError(
                "The stored Etsy connection has no usable token. Reconnect the account."
            )
        tokens = refresh_access_token(
            client_id=creds.api_keystring,
            refresh_token=creds.refresh_token,
            transport=self._transport,
        )
        self._store_tokens(tokens)

    # -- request pipeline ------------------------------------------------------

    def send(self, request: HttpRequest, *, retry_on_auth_failure: bool = True):
        """Send *request* with injected auth headers and one refresh-retry."""
        creds = self.credentials()
        if not creds.access_token:
            self.ensure_fresh_token()
            creds = self.credentials()
        attempt = HttpRequest(
            method=request.method,
            url=request.url,
            body=request.body,
            headers={
                **dict(request.headers),
                "x-api-key": build_x_api_key_header(creds.api_keystring, creds.shared_secret),
                "Authorization": f"Bearer {creds.access_token}",
                "Accept": "application/json",
            },
        )
        client = HttpClient(
            transport=self._transport,
            sleep=self._sleep,
            sensitive_values=(
                creds.access_token,
                creds.refresh_token,
                *([creds.api_keystring] if len(creds.api_keystring) >= 4 else []),
                *([creds.shared_secret] if creds.shared_secret else []),
            ),
        )
        try:
            return client.send(attempt)
        except AuthError as exc:
            if not retry_on_auth_failure or not creds.refresh_token:
                raise AuthError(
                    f"{exc.message} Reconnect the Etsy account from Marketplace connections."
                ) from exc
            tokens = refresh_access_token(
                client_id=creds.api_keystring,
                refresh_token=creds.refresh_token,
                transport=self._transport,
            )
            self._store_tokens(tokens)
            refreshed = HttpRequest(
                method=attempt.method,
                url=attempt.url,
                body=attempt.body,
                headers={
                    **{k: v for k, v in attempt.headers.items()
                       if k.lower() not in ("authorization", "x-api-key")},
                    "x-api-key": build_x_api_key_header(
                        self._cached.api_keystring, self._cached.shared_secret
                    ),
                    "Authorization": f"Bearer {self._cached.access_token}",
                    "Accept": "application/json",
                },
            )
            return HttpClient(
                transport=self._transport,
                sleep=self._sleep,
                sensitive_values=(self._cached.access_token, self._cached.refresh_token),
            ).send(refreshed)


__all__ = [
    "CREDENTIAL_PLATFORM",
    "ETSY_TOKEN_URL",
    "EtsySession",
    "TokenStore",
    "WinCredTokenStore",
    "deserialize_credentials",
    "exchange_authorization_code",
    "forget_credentials",
    "load_credentials",
    "refresh_access_token",
    "save_credentials",
    "serialize_credentials",
]
