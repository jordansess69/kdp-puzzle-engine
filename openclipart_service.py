"""Small, dependency-free client for the CC0 OpenClipart Hugging Face dataset.

The service searches the public dataset API and downloads only an image the
publisher explicitly selects. It never downloads the 22 GB dataset locally.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from html import unescape
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode, quote_plus
from urllib.request import Request, urlopen


DATASET = "nyuuzyou/openclipart"
API = "https://datasets-server.huggingface.co/search"
USER_AGENT = "Slade-Puzzles-Word-Search-Creator/2.4"
REVIEW_TAGS = {"clipart_issue", "pd_issue", "need-review", "trademark", "logo", "celebrity"}


def _request(url: str, timeout: int = 12) -> bytes:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json,image/*"})
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.read()
    except Exception as primary_error:
        # Some Windows Python builds can fail TLS negotiation through a local
        # proxy even when Windows networking itself works. Use Windows' native
        # web client as a narrow, transparent fallback for these public URLs.
        if not url.lower().startswith("https://"):
            raise primary_error
        handle, temporary_name = tempfile.mkstemp(prefix="slade_openclipart_", suffix=".download")
        os.close(handle)
        temporary = Path(temporary_name)
        try:
            command = "Invoke-WebRequest -UseBasicParsing -Uri '" + url.replace("'", "''") + "' -OutFile '" + str(temporary).replace("'", "''") + "'"
            try:
                result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command], capture_output=True, timeout=timeout + 8)
            except Exception:
                raise primary_error
            if result.returncode or not temporary.exists() or not temporary.stat().st_size:
                raise primary_error
            return temporary.read_bytes()
        finally:
            temporary.unlink(missing_ok=True)


def _safe(item: dict) -> bool:
    tags = {str(tag).lower().replace(" ", "_") for tag in item.get("tags", []) if isinstance(tag, str)}
    title = str(item.get("title", "")).lower()
    return not (tags & REVIEW_TAGS or any(token in title for token in (" logo", "trademark", "celebrity")))


def search_openclipart(query: str, limit: int = 18) -> list[dict[str, object]]:
    """Return compact, review-safe candidate records from the public API."""
    query = " ".join(query.split())[:120]
    if not query:
        return []
    params = {"dataset": DATASET, "config": "default", "split": "train", "query": query, "offset": 0, "length": min(max(limit * 2, 20), 100)}
    try:
        payload = json.loads(_request(f"{API}?{urlencode(params)}").decode("utf-8"))
    except Exception:
        # The dataset viewer can occasionally return 500 during a heavy global
        # index refresh. The source site remains the same CC0 collection, so a
        # compact site-search fallback keeps cover creation moving.
        return _search_openclipart_site(query, limit)
    choices: list[dict[str, object]] = []
    for wrapped in payload.get("rows", []):
        row = wrapped.get("row", wrapped) if isinstance(wrapped, dict) else {}
        if not isinstance(row, dict) or not _safe(row):
            continue
        urls = row.get("image_urls") or {}
        if not isinstance(urls, dict):
            continue
        png = urls.get("png_large") or urls.get("png_medium") or urls.get("png_small")
        if not isinstance(png, str) or not png.startswith("https://"):
            continue
        choices.append({
            "title": str(row.get("title") or "Untitled clipart"),
            "artist_name": str(row.get("artist_name") or "OpenClipart contributor"),
            "page_url": str(row.get("page_url") or ""),
            "png_url": png,
            "thumbnail_url": str(row.get("thumbnail_url") or urls.get("png_small") or png),
            "svg_url": str(urls.get("svg") or ""),
            "tags": [str(tag) for tag in row.get("tags", [])[:12]],
            "license": "CC0-1.0",
        })
        if len(choices) >= limit:
            break
    return choices


def _search_openclipart_site(query: str, limit: int) -> list[dict[str, object]]:
    html = _request(f"https://openclipart.org/search/?query={quote_plus(query)}", timeout=12).decode("utf-8", errors="replace")
    matches = re.findall(r'href=["\'](/detail/(\d+)/([^"\']+))["\']', html, flags=re.IGNORECASE)
    choices: list[dict[str, object]] = []
    seen: set[str] = set()
    for page_path, identifier, slug in matches:
        if identifier in seen:
            continue
        seen.add(identifier)
        title = unescape(slug.replace("-", " ")).strip().title()
        candidate = {"title": title, "tags": []}
        if not _safe(candidate):
            continue
        choices.append({
            "title": title, "artist_name": "OpenClipart contributor", "page_url": f"https://openclipart.org{page_path}",
            "png_url": f"https://openclipart.org/image/2000px/{identifier}", "thumbnail_url": f"https://openclipart.org/image/400px/{identifier}",
            "svg_url": "", "tags": [], "license": "CC0-1.0",
        })
        if len(choices) >= limit:
            break
    return choices


def fetch_thumbnail(url: str) -> bytes:
    return _request(url, timeout=10)


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")[:56] or "openclipart"


def _asset_id(page_url: str) -> str:
    match = re.search(r"/(\d+)/", page_url)
    return match.group(1) if match else "asset"


def download_openclipart(choice: dict[str, object], assets_root: Path) -> tuple[Path, dict[str, object]]:
    """Cache the chosen PNG and append a persistent CC0/source record."""
    folder = assets_root / "openclipart"
    folder.mkdir(parents=True, exist_ok=True)
    filename = f"{_asset_id(str(choice.get('page_url', '')))}_{_slug(str(choice.get('title', 'openclipart')))}.png"
    target = folder / filename
    if not target.exists():
        target.write_bytes(_request(str(choice["png_url"]), timeout=45))
    record = {
        "local_file": str(target), "title": str(choice.get("title") or "Untitled clipart"),
        "artist_name": str(choice.get("artist_name") or "OpenClipart contributor"),
        "page_url": str(choice.get("page_url") or ""), "png_url": str(choice.get("png_url") or ""),
        "svg_url": str(choice.get("svg_url") or ""), "tags": list(choice.get("tags") or []),
        "license": "CC0-1.0 Public Domain Dedication", "source_dataset": DATASET,
        "selected_at": datetime.now().isoformat(timespec="seconds"),
    }
    manifest = folder / "selected_assets.json"
    try:
        entries = json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else []
    except json.JSONDecodeError:
        entries = []
    if not isinstance(entries, list):
        entries = []
    entries = [item for item in entries if isinstance(item, dict) and item.get("local_file") != str(target)]
    entries.insert(0, record)
    manifest.write_text(json.dumps(entries[:500], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return target, record


def asset_record(path: Path, assets_root: Path) -> dict[str, object] | None:
    manifest = assets_root / "openclipart" / "selected_assets.json"
    try:
        entries = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    for entry in entries if isinstance(entries, list) else []:
        if isinstance(entry, dict) and Path(str(entry.get("local_file", ""))) == path:
            return entry
    return None
