"""Small standard-library HTTP abstraction shared by marketplace integrations.

Design rules for the integration foundation:

- HTTPS only: non-https URLs are refused before any bytes are sent.
- Explicit timeout on every request.
- Bounded retries for network failures, HTTP 429 and 5xx, honouring the
  server's ``Retry-After`` header when present (capped so a misbehaving host
  cannot stall the GUI thread plan).
- Failures are classified as AuthError / TransientError / PermanentError.
- Request summaries embedded in error messages are sanitized (sensitive
  header values masked, known secret values scrubbed).  Request/response
  bodies are never included in errors because they can carry authorization
  codes and PKCE verifiers.
- The transport is injectable so automated tests never touch the network.
"""

import json
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from typing import Mapping, Optional, Protocol

from integrations.errors import (
    AuthError,
    PermanentError,
    TransientError,
    is_sensitive_header,
    redact_text,
)

# Statuses that are worth a bounded retry.
_RETRY_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
# Credentials problems: never retried, the user must reconnect instead.
_AUTH_STATUS_CODES = frozenset({401, 403})
# Ceiling on Retry-After waits; protects the app from absurd server hints.
_MAX_RETRY_AFTER_SECONDS = 30.0


@dataclass(frozen=True)
class HttpRequest:
    method: str = "GET"
    url: str = ""
    headers: Mapping[str, str] = field(default_factory=dict)
    body: Optional[bytes] = None


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    headers: Mapping[str, str]
    body: bytes = b""

    def json(self):
        return json.loads(self.body.decode("utf-8"))


class Transport(Protocol):
    """Minimal transport interface; implementations raise TransientError on network-level failure."""

    def send(self, request: HttpRequest, timeout_seconds: float) -> HttpResponse: ...


class UrllibTransport:
    """Standard-library transport used in production."""

    def send(self, request, timeout_seconds):
        # Defence in depth: HttpClient refuses non-https URLs before this runs.
        if not request.url.lower().startswith("https://"):
            raise PermanentError(
                f"Refused to send non-HTTPS request to {request.url.split('?')[0]}"
            )
        req = urllib.request.Request(
            request.url,
            data=request.body,
            headers=dict(request.headers),
            method=request.method,
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
                return HttpResponse(
                    status_code=int(resp.status),
                    headers=dict(resp.headers.items()),
                    body=resp.read(),
                )
        except urllib.error.HTTPError as exc:
            # HTTPError carries a valid response (status + body); classify later.
            body = b""
            try:
                body = exc.read()
            except Exception:  # noqa: BLE001 - best-effort body read
                pass
            try:
                headers = dict(exc.headers.items())
            except Exception:  # noqa: BLE001
                headers = {}
            return HttpResponse(status_code=int(exc.code), headers=headers, body=body)
        except (urllib.error.URLError, OSError) as exc:
            # URLError, socket.timeout, TimeoutError and ssl.SSLError all land here.
            reason = getattr(exc, "reason", exc)
            raise TransientError(
                f"Network failure contacting marketplace host: {reason}"
            ) from exc


def _describe_request(request, sensitive_values):
    """Sanitized one-line summary safe for exception text and logs."""
    parts = [f"{request.method} {request.url.split('?')[0]}"]
    for name in sorted(request.headers):
        if is_sensitive_header(name):
            parts.append(f"{name}: {_MASK_PLACEHOLDER}")
        else:
            parts.append(f"{name}: {redact_text(request.headers[name], sensitive_values)}")
    summary = "; ".join(parts)
    return redact_text(summary, sensitive_values)


_MASK_PLACEHOLDER = "[REDACTED]"


class HttpClient:
    """Bounded-retry JSON/HTTP client with strict error classification."""

    def __init__(
        self,
        *,
        transport=None,
        timeout_seconds=15.0,
        max_retries=2,
        backoff_base_seconds=0.5,
        sleep=time.sleep,
        sensitive_values=(),
    ):
        self._transport = transport if transport is not None else UrllibTransport()
        self._timeout_seconds = float(timeout_seconds)
        self._max_retries = max(0, int(max_retries))
        self._backoff_base = max(0.0, float(backoff_base_seconds))
        self._sleep = sleep
        self._sensitive = tuple(sensitive_values)

    @property
    def max_attempts(self):
        return self._max_retries + 1

    def send(self, request):
        """Send *request* with bounded retries. Returns an HttpResponse.

        Raises AuthError (401/403), PermanentError (other 4xx, non-https) or
        TransientError (network trouble / retries exhausted).
        """
        if not request.url.lower().startswith("https://"):
            raise PermanentError(
                "Integration requests must use HTTPS "
                f"(refused: {request.method} {request.url.split('?')[0]})"
            )
        summary = _describe_request(request, self._sensitive)
        total_attempts = self.max_attempts
        delay = None
        for attempt in range(total_attempts):
            if delay is not None:
                self._sleep(delay)
            try:
                response = self._transport.send(request, self._timeout_seconds)
            except TransientError as exc:
                if attempt >= total_attempts - 1:
                    raise TransientError(
                        f"{exc.message} (gave up after {attempt + 1} attempt(s); last request: {summary})",
                        status_code=getattr(exc, "status_code", None),
                    ) from exc
                delay = self._backoff_base * (2 ** attempt)
                continue
            if 200 <= response.status_code < 300:
                return response
            if response.status_code in _AUTH_STATUS_CODES:
                raise AuthError(
                    f"Marketplace rejected the credentials (HTTP {response.status_code}); reconnect the account. Last request: {summary}",
                    status_code=response.status_code,
                )
            if response.status_code in _RETRY_STATUS_CODES:
                if attempt >= total_attempts - 1:
                    raise TransientError(
                        f"Marketplace temporarily unavailable (HTTP {response.status_code}) after {attempt + 1} attempt(s). Last request: {summary}",
                        status_code=response.status_code,
                    )
                retry_after = _parse_retry_after(response.headers.get("Retry-After"))
                if retry_after is not None:
                    delay = retry_after
                else:
                    delay = self._backoff_base * (2 ** attempt)
                continue
            raise PermanentError(
                f"Marketplace rejected the request as unfixable (HTTP {response.status_code}). Last request: {summary}",
                status_code=response.status_code,
            )
        # Defensive: loop above always returns or raises.
        raise TransientError(f"Retry loop exited unexpectedly. Last request: {summary}")

    def get_json(self, url, *, headers=None):
        """Convenience wrapper returning parsed JSON for a simple GET."""
        request = HttpRequest(method="GET", url=url, headers=dict(headers or {}))
        return self.send(request).json()


def _parse_retry_after(raw_value):
    if raw_value is None:
        return None
    try:
        seconds = float(str(raw_value).strip())
    except (TypeError, ValueError):
        return None
    if seconds < 0:
        return None
    return min(seconds, _MAX_RETRY_AFTER_SECONDS)


def build_multipart_body(fields=None, files=None):
    """Encode a multipart/form-data body with the standard library only.

    ``fields`` maps plain text field names to string values.  ``files`` is a
    list of ``(field_name, filename, content_bytes, content_type)`` tuples for
    binary parts (digital download files, listing images).  Returns
    ``(body_bytes, content_type_header)``; the caller must send exactly the
    returned Content-Type so the boundary matches.

    Used by the Etsy draft client for uploadListingFile / uploadListingImage.
    A fresh random boundary is used per call; bodies are never logged by the
    HTTP layer because error summaries carry URLs and headers only.
    """
    boundary = f"----KDPPuzzleEngine{uuid.uuid4().hex}"
    lines = []
    for name, value in sorted((fields or {}).items()):
        lines.extend(
            (
                f"--{boundary}",
                f'Content-Disposition: form-data; name="{name}"',
                "",
                str(value),
            )
        )
    body_parts = []
    for line in lines:
        body_parts.append(line.encode("utf-8"))
        body_parts.append(b"\r\n")
    for field_name, filename, content, content_type in files or ():
        body_parts.extend(
            (
                f"--{boundary}\r\n".encode("utf-8"),
                (
                    f'Content-Disposition: form-data; name="{field_name}"; '
                    f'filename="{filename}"\r\n'
                ).encode("utf-8"),
                f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"),
                bytes(content),
                b"\r\n",
            )
        )
    body_parts.append(f"--{boundary}--\r\n".encode("utf-8"))
    body = b"".join(body_parts)
    return body, f"multipart/form-data; boundary={boundary}"
