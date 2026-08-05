"""CouncilKey-Os Browser - real fetch + text extraction.

A lightweight, dependency-light browser toolkit:
- `fetch()`  - retrieve a URL and extract readable text (no Selenium needed)
- `extract_text()` - HTML -> plain text via stdlib HTMLParser

Optionally integrates with Camofox (Firefox fork) if it is installed on the host.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any

import httpx

_SKIP_TAGS = {"script", "style", "noscript", "svg", "head", "template"}
_USER_AGENT = "CouncilKey-Os/1.1 (local agent browser; +https://github.com/Nikhil009988/CouncilKey-Os)"


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIP_TAGS:
            self._skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)


def extract_text(html: str, limit: int = 4000) -> str:
    """Strip HTML tags/scripts and return readable text (first `limit` chars)."""
    parser = _TextExtractor()
    try:
        parser.feed(html or "")
    except Exception:
        pass
    text = " ".join(p.strip() for p in parser.parts if p.strip())
    text = re.sub(r"\s+", " ", text)
    return text[:limit]


def fetch(url: str, timeout: float = 15.0) -> dict[str, Any]:
    """Fetch a URL and return metadata + readable text."""
    if not url or not re.match(r"^https?://", url):
        return {"ok": False, "error": "only http/https URLs are supported"}
    try:
        r = httpx.get(
            url,
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": _USER_AGENT, "Accept": "text/html,application/xhtml+xml,*/*"},
        )
        r.raise_for_status()
        m = re.search(r"<title[^>]*>(.*?)</title>", r.text, re.DOTALL | re.IGNORECASE)
        title = re.sub(r"\s+", " ", m.group(1)).strip()[:200] if m else ""
        return {
            "ok": True,
            "url": url,
            "final_url": str(r.url),
            "status": r.status_code,
            "title": title,
            "text": extract_text(r.text),
            "bytes": len(r.content),
            "content_type": r.headers.get("content-type", ""),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def camofox_tools() -> list[dict[str, str]]:
    """Tool descriptors for UI/agent documentation."""
    return [
        {
            "name": "camofox",
            "description": "Camofox browser with fingerprint spoofing, anti-detection, browser automation",
            "how": "Camofox is a Firefox fork with fingerprint spoofing for automation without detection",
        },
        {
            "name": "browser_navigate",
            "description": "Navigate browser to URL (lightweight mode uses HTTP fetch + text extraction)",
        },
        {
            "name": "browser_screenshot",
            "description": "Take screenshot of current browser or desktop for vision analysis",
        },
        {
            "name": "browser_fetch",
            "description": "Fetch a URL and extract readable text/title - implemented",
        },
        {
            "name": "browser_dom_annotate",
            "description": "Click page elements and turn into inspect/change/lift/review instructions",
        },
    ]


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) > 1:
        print(json.dumps(fetch(sys.argv[1]), indent=2))
    else:
        print(json.dumps(camofox_tools(), indent=2))
