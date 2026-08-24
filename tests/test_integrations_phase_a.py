"""Phase A security and behaviour tests for the integrations foundation.

Everything runs offline through an injected mock transport - no test in this
file (or suite) ever contacts Etsy or any other host.

Covers the ten required Phase A proofs:
1. PKCE verifier/challenge validity (including the RFC 7636 Appendix B vector)
2. Secrets never appear in repr/error/log output
3. Auth failures classified correctly (and never retried)
4. Bounded retries on 429/5xx/network failures (honouring Retry-After)
5. Permanent 4xx errors are never retried
6. test_connection issues only whitelisted read-only GET requests
7. No Etsy write endpoint/capability exists through the Phase A adapter
8. Missing configuration yields a clean Not Connected result (no crash)
9. Registry resolves Etsy and safely ignores unknown platforms
10. Fully offline via mocked transport
"""

import pytest

from integrations.base import CapabilityFlags, ConnectionReport, PublishingIntegration
from integrations.errors import (
    AuthError,
    PermanentError,
    TransientError,
    redact_text,
)
from integrations.http import HttpRequest, HttpClient, HttpResponse
from integrations.etsy import auth as etsy_auth
from integrations.etsy.connection import (
    ALLOWED_READ_PATHS,
    ENV_ACCESS_TOKEN,
    ENV_API_KEYSTRING,
    EtsyCredentials,
    EtsyIntegration,
    PATH_ME,
    PATH_USER_SHOPS,
    ETSY_API_HOST,
)
from integrations.registry import available_keys, get_integration


class MockTransport:
    """Scripted offline transport recording every request it was asked to send."""

    def __init__(self, handler):
        self.handler = handler
        self.requests = []

    def send(self, request, timeout_seconds):
        self.requests.append((request, timeout_seconds))
        return self.handler(len(self.requests), request)


def _json_response(status_code, payload, headers=None):
    import json

    body = json.dumps(payload).encode("utf-8")
    return HttpResponse(status_code=status_code, headers=dict(headers or {}), body=body)


ME_PAYLOAD = {"user_id": 555001, "shop_id": None}
SHOPS_PAYLOAD = {
    "count": 1,
    "results": [
        {"shop_id": 98765432, "shop_name": "SladePuzzles", "url": "https://www.etsy.com/shop/SladePuzzles"}
    ],
}


def _etsy_handler(call_index, request):
    if request.url.endswith("/users/me"):
        return _json_response(200, ME_PAYLOAD)
    return _json_response(200, SHOPS_PAYLOAD)


def _make_client(handler=None, sensitive_values=(), **kwargs):
    transport = MockTransport(handler or _etsy_handler)
    slept = []
    client = HttpClient(
        transport=transport,
        sleep=slept.append,
        backoff_base_seconds=0.5,
        sensitive_values=sensitive_values,
        **kwargs,
    )
    return client, transport, slept


def _make_integration(handler=None, credentials=None, **client_kwargs):
    creds = credentials or EtsyCredentials(
        api_keystring="keystringABCDEF",
        shared_secret="sharedsecretABCDEF",
        access_token="555001.ACCESS_TOKEN_VALUE",
        refresh_token="555001.REFRESH_TOKEN_VALUE",
    )

    class StaticProvider:
        def load(self_inner):
            return creds

    client, transport, slept = _make_client(handler, **client_kwargs)
    integration = EtsyIntegration(credential_provider=StaticProvider(), http_client=client)
    return integration, transport, slept, creds


# ---------------------------------------------------------------------------
# 1. PKCE generation
# ---------------------------------------------------------------------------


class TestPkce:
    def test_generated_pair_is_valid_and_unique(self):
        pair = etsy_auth.generate_pkce_pair()
        assert len(pair.verifier) == 43
        allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._~-")
        assert set(pair.verifier) <= allowed
        assert pair.challenge == etsy_auth.pkce_challenge_from_verifier(pair.verifier)
        other = etsy_auth.generate_pkce_pair()
        assert pair.verifier != other.verifier
        assert pair.challenge != other.challenge

    def test_challenge_matches_rfc7636_appendix_b_vector(self):
        verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
        expected = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
        assert etsy_auth.pkce_challenge_from_verifier(verifier) == expected


# ---------------------------------------------------------------------------
# 2. Secret redaction
# ---------------------------------------------------------------------------


class TestSecretHygiene:
    def test_redact_text_masks_known_values_bearer_and_assignments(self):
        text = (
            "Authorization: Bearer SECRETTOKEN12345 "
            "access_token=ANOTHERSECRET98765 shared_secret: SHORTY"
        )
        cleaned = redact_text(text, extra_secrets=("SHORTY",))
        assert "SECRETTOKEN12345" not in cleaned
        assert "ANOTHERSECRET98765" not in cleaned
        assert "SHORTY" not in cleaned
        assert "[REDACTED]" in cleaned

    def test_token_set_repr_never_leaks_values(self):
        token_set = etsy_auth.parse_token_response(
            {
                "access_token": "LIVEACCESSVALUE123456",
                "refresh_token": "LIVEREFRESHVALUE789012",
                "expires_in": 3600,
                "token_type": "Bearer",
                "scope": "shops_r",
            }
        )
        for rendered in (repr(token_set), str(token_set)):
            assert "LIVEACCESSVALUE123456" not in rendered
            assert "LIVEREFRESHVALUE789012" not in rendered
            assert "[REDACTED]" in rendered
            assert "present" in rendered

    def test_credentials_repr_only_shows_presence(self):
        creds = EtsyCredentials(
            api_keystring="VISIBLEKEYSTRING99",
            shared_secret="HUSHEDSECRET777",
            access_token="QUIETTOKEN555000",
            refresh_token="SLEEPYTOKEN444",
        )
        rendered = repr(creds)
        for secret in ("VISIBLEKEYSTRING99", "HUSHEDSECRET777", "QUIETTOKEN555000", "SLEEPYTOKEN444"):
            assert secret not in rendered
        assert rendered.count("set") == 4

    def test_http_error_text_is_sanitized_of_header_secrets(self):
        def deny_all(call_index, request):
            return HttpResponse(status_code=503, headers={}, body=b"")

        secret_token = "SUPERTOKENVALUE8888"
        client, transport, _ = _make_client(deny_all, sensitive_values=(secret_token,), max_retries=0)
        request = HttpRequest(
            method="GET",
            url="https://openapi.etsy.com/v3/application/users/me",
            headers={"Authorization": f"Bearer {secret_token}"},
        )
        with pytest.raises(TransientError) as excinfo:
            client.send(request)
        rendered = f"{excinfo.value} {repr(excinfo.value)}"
        assert secret_token not in rendered
        assert "[REDACTED]" in rendered


# ---------------------------------------------------------------------------
# 3-5. Error classification and bounded retries
# ---------------------------------------------------------------------------


class TestHttpClassificationAndRetries:
    def test_auth_error_not_retried(self):
        calls = {"n": 0}

        def unauthorized(call_index, request):
            calls["n"] += 1
            return HttpResponse(status_code=401, headers={}, body=b"")

        client, transport, _ = _make_client(unauthorized, max_retries=3)
        with pytest.raises(AuthError) as excinfo:
            client.send(HttpRequest(method="GET", url="https://openapi.etsy.com/v3/application/users/me"))
        assert excinfo.value.status_code == 401
        assert calls["n"] == 1

    def test_permanent_4xx_not_retried(self):
        calls = {"n": 0}

        def bad_request(call_index, request):
            calls["n"] += 1
            return HttpResponse(status_code=400, headers={}, body=b"")

        client, _, _ = _make_client(bad_request, max_retries=3)
        with pytest.raises(PermanentError):
            client.send(HttpRequest(method="GET", url="https://openapi.etsy.com/v3/application/users/me"))
        assert calls["n"] == 1

    def test_transient_retries_are_bounded_then_raise(self):
        calls = {"n": 0}

        def unavailable(call_index, request):
            calls["n"] += 1
            return HttpResponse(status_code=503, headers={}, body=b"")

        client, _, slept = _make_client(unavailable, max_retries=2)
        with pytest.raises(TransientError) as excinfo:
            client.send(HttpRequest(method="GET", url="https://openapi.etsy.com/v3/application/users/me"))
        assert calls["n"] == 3  # 1 initial attempt + 2 retries, then give up
        assert excinfo.value.status_code == 503
        assert len(slept) == 2

    def test_retry_eventually_succeeds_with_backoff(self):
        def flaky(call_index, request):
            if call_index <= 2:
                return HttpResponse(status_code=500, headers={}, body=b"")
            return _json_response(200, ME_PAYLOAD)

        client, _, slept = _make_client(flaky, max_retries=3)
        response = client.send(
            HttpRequest(method="GET", url="https://openapi.etsy.com/v3/application/users/me")
        )
        assert response.status_code == 200
        # Exponential backoff: 0.5 then 1.0 seconds (injected sleep, no real waiting).
        assert slept == [0.5, 1.0]

    def test_retry_after_header_is_respected_and_capped(self):
        def rate_limited_then_ok(call_index, request):
            if call_index == 1:
                return HttpResponse(status_code=429, headers={"Retry-After": "7"}, body=b"")
            return _json_response(200, ME_PAYLOAD)

        client, _, slept = _make_client(rate_limited_then_ok, max_retries=2)
        response = client.send(
            HttpRequest(method="GET", url="https://openapi.etsy.com/v3/application/users/me")
        )
        assert response.status_code == 200
        assert slept == [7.0]  # waited exactly what Etsy asked, once

    def test_non_https_urls_refused_before_transport(self):
        client, transport, _ = _make_client(_etsy_handler)
        with pytest.raises(PermanentError):
            client.send(
                HttpRequest(method="GET", url="http://openapi.etsy.com/v3/application/users/me")
            )
        assert transport.requests == []

    def test_network_failure_maps_to_transient_and_retries(self):
        def network_drops_once(call_index, request):
            if call_index == 1:
                raise TransientError("connection reset by peer")
            return _json_response(200, ME_PAYLOAD)

        client, _, slept = _make_client(network_drops_once, max_retries=2)
        response = client.send(
            HttpRequest(method="GET", url="https://openapi.etsy.com/v3/application/users/me")
        )
        assert response.status_code == 200
        assert slept == [0.5]


# ---------------------------------------------------------------------------
# 6-8. Etsy read-only adapter behaviour
# ---------------------------------------------------------------------------


class TestEtsyConnection:
    def test_missing_configuration_is_clean_not_connected(self):
        class EmptyProvider:
            def load(self):
                return EtsyCredentials()

        integration = EtsyIntegration(credential_provider=EmptyProvider())
        report = integration.test_connection()
        assert isinstance(report, ConnectionReport)
        assert report.ok is True
        assert report.connected is False
        assert ENV_API_KEYSTRING in report.message
        assert ENV_ACCESS_TOKEN in report.message
        assert integration.is_configured() is False

    def test_happy_path_reports_connected_shop(self):
        integration, _, _, _ = _make_integration()
        assert integration.is_configured() is True
        report = integration.test_connection()
        assert report.platform == "etsy"
        assert report.ok is True
        assert report.connected is True
        assert report.user_id == 555001
        assert report.shop_id == 98765432
        assert report.shop_name == "SladePuzzles"
        assert "connected successfully" in report.message
        assert "SladePuzzles" in report.message

    def test_connection_issues_only_whitelisted_read_requests(self):
        integration, transport, _, _ = _make_integration()
        integration.test_connection()
        assert len(transport.requests) == 2
        for request, timeout in transport.requests:
            assert request.method == "GET"
            assert request.url.startswith(ETSY_API_HOST)
            path = request.url[len(ETSY_API_HOST):]
            assert any(
                path == template or path == template.format(user_id=555001)
                for template in ALLOWED_READ_PATHS
            )
            assert timeout > 0
        recorded_paths = [req.url[len(ETSY_API_HOST):] for req, _ in transport.requests]
        assert recorded_paths == [PATH_ME, PATH_USER_SHOPS.format(user_id=555001)]

    def test_auth_failure_returns_report_instead_of_raising(self):
        def always_unauthorized(call_index, request):
            return HttpResponse(status_code=401, headers={}, body=b"")

        integration, transport, _, _ = _make_integration(handler=always_unauthorized, max_retries=0)
        report = integration.test_connection()
        assert report.ok is True
        assert report.connected is False
        assert "rejected" in report.message.lower()

    def test_transient_outage_reports_ok_false_without_crashing(self):
        def dead_network(call_index, request):
            raise TransientError("connection reset by peer")

        integration, _, _, _ = _make_integration(handler=dead_network, max_retries=0)
        report = integration.test_connection()
        assert report.ok is False
        assert report.connected is False

    def test_guard_blocks_any_non_readonly_path_before_sending(self):
        integration, transport, _, creds = _make_integration()

        class PassThroughClient:
            def send(self_inner, request):
                transport.send(request, 1.0)
                return _json_response(200, {})

        headers = {
            "x-api-key": etsy_auth.build_x_api_key_header(creds.api_keystring, creds.shared_secret),
            "Authorization": f"Bearer {creds.access_token}",
        }
        with pytest.raises(PermanentError):
            integration._guarded_get(
                PassThroughClient(), "/v3/application/shops/98765432/listings", {}, headers
            )
        assert transport.requests == []


class TestNoWriteCapabilityExists:
    WRITE_STYLE_NAMES = (
        "create_draft",
        "createDraftListing",
        "upload_listing_file",
        "uploadListingFile",
        "upload_image",
        "upload_listing_image",
        "uploadListingImage",
        "activate",
        "activate_listing",
        "update_listing",
        "delete_listing",
        "publish",
        "publish_listing",
    )

    def test_adapter_exposes_no_write_methods_or_capabilities(self):
        integration, _, _, _ = _make_integration()
        for name in self.WRITE_STYLE_NAMES:
            assert not hasattr(integration, name), name
            assert getattr(type(integration), name, None) is None, name
        caps = integration.capabilities
        assert caps.can_test_connection is True
        assert caps.can_create_draft is False
        assert caps.can_upload_files is False
        assert caps.can_upload_images is False
        assert caps.can_activate is False
        assert caps.has_any_write_capability is False

    def test_base_contract_defines_no_write_methods(self):
        for name in TestNoWriteCapabilityExists.WRITE_STYLE_NAMES:
            assert getattr(PublishingIntegration, name, None) is None, name


# ---------------------------------------------------------------------------
# 9. Registry
# ---------------------------------------------------------------------------


class TestRegistry:
    def test_registry_resolves_etsy_case_insensitively(self):
        for key in ("etsy", "Etsy", " ETSY "):
            integration = get_integration(key)
            assert isinstance(integration, EtsyIntegration)
            assert integration.key == "etsy"

    def test_unknown_platform_returns_none(self):
        assert get_integration("amazon") is None
        assert get_integration("") is None
        assert get_integration(None) is None

    def test_available_keys_lists_etsy_only(self):
        assert available_keys() == ("etsy",)


# ---------------------------------------------------------------------------
# OAuth URL/request builders (foundation completeness)
# ---------------------------------------------------------------------------


class TestOAuthBuilders:
    def test_authorization_url_contains_minimal_scopes_and_s256(self):
        pair = etsy_auth.generate_pkce_pair()
        url = etsy_auth.build_authorization_url(
            client_id="keystringABCDEF",
            redirect_uri="https://example.com/callback",
            code_challenge=pair.challenge,
            state="st@te-1",
        )
        assert url.startswith("https://www.etsy.com/oauth/connect?")
        assert "response_type=code" in url
        assert "client_id=keystringABCDEF" in url
        assert "scope=shops_r" in url
        assert "listings_w" not in url
        assert "listings_d" not in url
        assert "code_challenge_method=S256" in url
        assert "state=st%40te-1" in url

    def test_authorization_url_refuses_http_redirect_uri(self):
        pair = etsy_auth.generate_pkce_pair()
        with pytest.raises(PermanentError):
            etsy_auth.build_authorization_url(
                client_id="keystringABCDEF",
                redirect_uri="http://example.com/callback",
                code_challenge=pair.challenge,
            )

    def test_read_only_scope_list_has_no_write_or_delete_scopes(self):
        assert set(etsy_auth.READ_ONLY_SCOPES) == {"shops_r"}

    def test_token_request_builder_shape(self):
        request = etsy_auth.build_refresh_request(
            client_id="keystringABCDEF", refresh_token="REFRESHVALUE123456"
        )
        assert request.method == "POST"
        assert request.url == etsy_auth.ETSY_TOKEN_URL
        assert request.headers["Content-Type"] == "application/x-www-form-urlencoded"
        body = request.body.decode("utf-8")
        assert "grant_type=refresh_token" in body
        assert "REFRESHVALUE123456" in body  # present in body, never in logs/errors

    def test_extract_state_and_code_from_callback(self):
        state, code, error = etsy_auth.extract_state_and_code(
            "https://example.com/cb?code=abc123&state=xyz"
        )
        assert (state, code, error) == ("xyz", "abc123", None)
        state, code, error = etsy_auth.extract_state_and_code(
            "https://example.com/cb?error=access_denied&error_description=nope"
        )
        assert (state, code, error) == (None, None, "access_denied")
