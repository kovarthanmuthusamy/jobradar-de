"""Adapter contract plus the shared HTTP fetcher.

Design rule for the whole project: discovery is deterministic code. Adapters
fetch public ATS feeds, send conditional headers (ETag / If-Modified-Since)
so an unchanged board costs a single 304, and parse into RawJob records.
No LLM and no browser is ever involved at this layer.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

from app.config import settings

_TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "ref"}


def canonicalize_url(url: str) -> str:
    """Stable dedupe key form: lowercase host, no tracking params, no trailing slash."""
    parts = urlsplit(url.strip())
    query = urlencode([(k, v) for k, v in parse_qsl(parts.query) if k not in _TRACKING_PARAMS])
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, query, ""))


_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def html_to_text(html: str) -> str:
    """Crude but deterministic HTML -> plain text for storage and later rule scoring."""
    text = _TAG_RE.sub(" ", html or "")
    for entity, char in (("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">")):
        text = text.replace(entity, char)
    return _WS_RE.sub(" ", text).strip()


@dataclass
class RawJob:
    external_id: str
    title: str
    apply_url: str
    location_text: str | None = None
    city: str | None = None
    country: str | None = None
    remote: bool = False
    employment_type: str | None = None
    description_text: str = ""
    posted_at: datetime | None = None


@dataclass
class FetchResult:
    status_code: int
    content: bytes = b""
    etag: str | None = None
    last_modified: str | None = None


def http_fetch(url: str, etag: str | None, last_modified: str | None) -> FetchResult:
    """One conditional GET. trust_env=False: a broken proxy env must never kill a run."""
    headers = {
        "User-Agent": settings.ingest_user_agent,
        "Accept": "application/json, text/xml, */*",
    }
    if etag:
        headers["If-None-Match"] = etag
    if last_modified:
        headers["If-Modified-Since"] = last_modified
    with httpx.Client(
        timeout=settings.http_timeout_seconds, trust_env=False, follow_redirects=True
    ) as client:
        resp = client.get(url, headers=headers)
    return FetchResult(
        status_code=resp.status_code,
        content=resp.content if resp.status_code == 200 else b"",
        etag=resp.headers.get("ETag"),
        last_modified=resp.headers.get("Last-Modified"),
    )


class BaseAdapter:
    """One adapter per ATS. Subclasses set `name` and implement feed_url + parse."""

    name: str = "base"

    def feed_url(self, board_id: str, override: str | None = None) -> str:
        raise NotImplementedError

    def parse(self, content: bytes) -> list[RawJob]:
        raise NotImplementedError

    def parse_board(self, content: bytes, board_id: str) -> list[RawJob]:
        """Parse with board context (some ATS feeds need it to build apply URLs)."""
        return self.parse(content)

    def fetch_jobs(
        self,
        board_id: str,
        override: str | None = None,
        etag: str | None = None,
        last_modified: str | None = None,
        fetcher=http_fetch,
    ) -> tuple[list[RawJob] | None, FetchResult]:
        """Returns (jobs, fetch). jobs is None when the feed answered 304 (unchanged)."""
        result = fetcher(self.feed_url(board_id, override), etag, last_modified)
        if result.status_code == 304:
            return None, result
        if result.status_code != 200:
            raise RuntimeError(f"{self.name} feed returned HTTP {result.status_code}")
        return self.parse_board(result.content, board_id), result
