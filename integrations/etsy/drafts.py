"""Etsy draft-listing API client (drafts ONLY — never activation).

Safety architecture:

- Every method builds its exact endpoint URL internally from validated
  positive-integer IDs.  No caller-supplied string ever becomes part of a
  path, so URL injection cannot happen.
- There is deliberately NO method that changes a listing's state, price,
  quantity after the fact, or deletes anything.  The only write operations in
  this module are: create a DRAFT listing, attach a digital file to it, and
  attach an image to it.  Publishing/activating stays a human action in
  Etsy Shop Manager.
- All requests flow through :class:`integrations.etsy.session.EtsySession`,
  which injects auth headers and performs at most one transparent token
  refresh.

Official endpoints (Etsy Open API v3, verified August 2026):
- POST /v3/application/shops/{shop_id}/listings          createDraftListing
- GET  /v3/application/shops/{shop_id}/listings?state=draft   draft scan
- GET  /v3/application/listings/{listing_id}             getListing (reconcile)
- GET  /v3/application/shops/{shop_id}/listings/{listing_id}/files
- GET  /v3/application/shops/{shop_id}/listings/{listing_id}/images
- POST /v3/application/shops/{shop_id}/listings/{listing_id}/files  uploadListingFile
- POST /v3/application/shops/{shop_id}/listings/{listing_id}/images uploadListingImage
- GET  /v3/application/seller-taxonomy/nodes             seller taxonomy
"""

from __future__ import annotations

import urllib.parse

from integrations.errors import PermanentError
from integrations.http import HttpRequest, build_multipart_body

ETSY_API_HOST = "https://openapi.etsy.com"

_IMAGE_MIME_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}


def _positive_int(value, name: str) -> int:
    """Validate an Etsy numeric ID before it may touch a request path."""
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise PermanentError(f"The Etsy {name} must be a number") from exc
    if parsed < 1:
        raise PermanentError(f"The Etsy {name} must be a positive number")
    return parsed


def image_content_type(filename: str) -> str:
    suffix = "." + str(filename).rsplit(".", 1)[-1].lower() if "." in str(filename) else ""
    if suffix not in _IMAGE_MIME_TYPES:
        raise PermanentError("Listing images must be a .jpg or .png file")
    return _IMAGE_MIME_TYPES[suffix]


class EtsyDraftClient:
    """Thin, exact-endpoint wrapper for the draft-only slice of Etsy's API."""

    def __init__(self, session):
        self._session = session

    # -- reads ---------------------------------------------------------------

    def get_me(self) -> dict:
        return self._session.send(HttpRequest(
            method="GET", url=f"{ETSY_API_HOST}/v3/application/users/me")).json()

    def get_user_shops(self, user_id) -> dict:
        user_id = _positive_int(user_id, "user id")
        return self._session.send(HttpRequest(
            method="GET",
            url=f"{ETSY_API_HOST}/v3/application/users/{user_id}/shops")).json()

    def get_seller_taxonomy_nodes(self) -> dict:
        return self._session.send(HttpRequest(
            method="GET",
            url=f"{ETSY_API_HOST}/v3/application/seller-taxonomy/nodes")).json()

    def get_listing(self, listing_id) -> dict:
        listing_id = _positive_int(listing_id, "listing id")
        return self._session.send(HttpRequest(
            method="GET",
            url=f"{ETSY_API_HOST}/v3/application/listings/{listing_id}")).json()

    def list_drafts(self, shop_id, limit: int = 100) -> dict:
        shop_id = _positive_int(shop_id, "shop id")
        limit = min(max(_positive_int(limit, "limit"), 1), 100)
        query = urllib.parse.urlencode({"state": "draft", "limit": limit})
        return self._session.send(HttpRequest(
            method="GET", url=f"{ETSY_API_HOST}/v3/application/shops/{shop_id}/listings?{query}")).json()

    def list_listing_files(self, shop_id, listing_id) -> dict:
        shop_id = _positive_int(shop_id, "shop id")
        listing_id = _positive_int(listing_id, "listing id")
        return self._session.send(HttpRequest(
            method="GET",
            url=f"{ETSY_API_HOST}/v3/application/shops/{shop_id}/listings/{listing_id}/files")).json()

    def list_listing_images(self, shop_id, listing_id) -> dict:
        shop_id = _positive_int(shop_id, "shop id")
        listing_id = _positive_int(listing_id, "listing id")
        return self._session.send(HttpRequest(
            method="GET",
            url=f"{ETSY_API_HOST}/v3/application/shops/{shop_id}/listings/{listing_id}/images")).json()

    # -- draft-only writes -----------------------------------------------------

    def create_draft_listing(self, shop_id, fields: dict) -> dict:
        """POST one new DRAFT listing; ``fields`` are form-encoded as documented."""
        shop_id = _positive_int(shop_id, "shop id")
        clean = {}
        for name, value in fields.items():
            if value is None:
                continue
            clean[str(name)] = str(value)
        body = urllib.parse.urlencode(clean).encode("utf-8")
        response = self._session.send(HttpRequest(
            method="POST",
            url=f"{ETSY_API_HOST}/v3/application/shops/{shop_id}/listings",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            body=body,
        ))
        return response.json()

    def upload_listing_file(self, shop_id, listing_id, filename: str, content: bytes) -> dict:
        """Attach ONE digital-download file (binary) to a listing."""
        shop_id = _positive_int(shop_id, "shop id")
        listing_id = _positive_int(listing_id, "listing id")
        body, content_type = build_multipart_body(
            fields={"name": filename},
            files=[("file", filename, content, "application/pdf")],
        )
        response = self._session.send(HttpRequest(
            method="POST",
            url=f"{ETSY_API_HOST}/v3/application/shops/{shop_id}/listings/{listing_id}/files",
            headers={"Content-Type": content_type},
            body=body,
        ))
        return response.json()

    def upload_listing_image(self, shop_id, listing_id, filename: str, content: bytes) -> dict:
        """Attach ONE listing image (.jpg/.png binary) to a listing."""
        shop_id = _positive_int(shop_id, "shop id")
        listing_id = _positive_int(listing_id, "listing id")
        mime = image_content_type(filename)
        body, content_type = build_multipart_body(
            files=[("image", filename, content, mime)],
        )
        response = self._session.send(HttpRequest(
            method="POST",
            url=f"{ETSY_API_HOST}/v3/application/shops/{shop_id}/listings/{listing_id}/images",
            headers={"Content-Type": content_type},
            body=body,
        ))
        return response.json()
