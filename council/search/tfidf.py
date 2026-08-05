"""Pure-Python TF-IDF full-text search over journal + shared documents.

No external dependencies: tokenization, IDF weights and cosine-style scoring
are implemented with the standard library. Index is persisted as JSON under
COUNCIL_HOME/search/tfidf-index.json.
"""
from __future__ import annotations

import json
import math
import os
import re
import time
from pathlib import Path

INDEX_PATH = Path(os.environ.get("COUNCIL_HOME", "/var/lib/council")) / "search" / "tfidf-index.json"
_TOKEN_RE = re.compile(r"[a-z0-9]+")
MAX_DOC_CHARS = 20_000
MAX_DOCS = 400


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall((text or "").lower())


def _collect_docs() -> list[dict]:
    home = Path(os.environ.get("COUNCIL_HOME", "/var/lib/council"))
    docs: list[dict] = []
    for root in (home / "journal", home / "shared"):
        if not root.exists():
            continue
        for p in sorted(root.rglob("*.md")):
            if len(docs) >= MAX_DOCS:
                break
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")[:MAX_DOC_CHARS]
            except Exception:
                continue
            if not text.strip():
                continue
            rel = str(p.relative_to(home))
            docs.append(
                {
                    "file": rel,
                    "title": p.name,
                    "preview": " ".join(text.split())[:300],
                    "tokens": sorted(set(tokenize(text))),
                }
            )
        if len(docs) >= MAX_DOCS:
            break
    return docs


def build_index() -> dict:
    docs = _collect_docs()
    df: dict[str, int] = {}
    for d in docs:
        for t in set(d["tokens"]):
            df[t] = df.get(t, 0) + 1
    idf = {t: math.log(1.0 + len(docs) / (1.0 + count)) for t, count in df.items()}
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(
        json.dumps(
            {"built_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "doc_count": len(docs), "idf": idf, "docs": docs},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return {"ok": True, "doc_count": len(docs), "terms": len(idf), "path": str(INDEX_PATH)}


def _load_index() -> dict | None:
    if not INDEX_PATH.exists():
        return None
    try:
        return json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None


def search(query: str, top_k: int = 10) -> dict:
    """Search the index. Returns ranked docs with scores and previews."""
    index = _load_index()
    if index is None:
        return {"ok": False, "error": "index not built yet - POST /api/search/index", "results": []}
    q_tokens = set(tokenize(query))
    if not q_tokens:
        return {"ok": True, "query": query, "results": [], "total": 0}
    idf = index.get("idf", {})
    scored: list[dict] = []
    for d in index.get("docs", []):
        overlap = q_tokens & set(d.get("tokens", []))
        if not overlap:
            continue
        score = sum(idf.get(t, 0.0) for t in overlap) + 0.01 * len(overlap)
        scored.append(
            {
                "file": d.get("file", ""),
                "title": d.get("title", ""),
                "score": round(score, 4),
                "preview": d.get("preview", ""),
            }
        )
    scored.sort(key=lambda x: -x["score"])
    return {"ok": True, "query": query, "results": scored[: max(1, min(top_k, 50))], "total": len(scored)}
