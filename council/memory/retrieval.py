"""RAG-lite context retrieval - inject relevant prior knowledge into prompts."""
from __future__ import annotations

import re

from council.journal.analyzer import history
from council.knowledge.graph import search as graph_search

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall((text or "").lower()))


def _overlap(a: str, b: str) -> int:
    """Token overlap with prefix matching (optimize ~ optimization).

    Each pair of tokens (one from each side) counts once when they are
    equal or share a prefix of >= 4 chars - this catches word forms
    without needing a stemmer.
    """
    ta, tb = _tokens(a), _tokens(b)
    score = 0
    for x in ta:
        for y in tb:
            if x == y or (len(x) >= 4 and len(y) >= 4 and (x.startswith(y) or y.startswith(x))):
                score += 1
    return score


def retrieve_context(prompt: str, top_k: int = 3) -> str:
    """Collect the most relevant snippets from journal, knowledge graph and
    (optionally) the LanceDB vector store. Returns a formatted context block,
    or an empty string when nothing relevant is found."""
    pieces: list[tuple[int, str]] = []

    try:
        for entry in history(limit=30):
            score = _overlap(prompt, entry.get("prompt", ""))
            if score:
                final = (entry.get("final") or "")[:400].replace("\n", " ")
                pieces.append((score * 3, f"[journal {entry.get('file', '')}] {final}"))
    except Exception:
        pass

    try:
        graph = graph_search(prompt)
        for node in (graph.get("nodes") or [])[:top_k]:
            pieces.append((5, f"[knowledge] {node.get('label', '')} ({node.get('kind', 'concept')})"))
    except Exception:
        pass

    try:
        from council.embeddings.lancedb import search as lancedb_search

        result = lancedb_search(prompt, limit=top_k)
        if result.get("ok"):
            for row in result.get("results", []):
                text = (row.get("text") or "")[:400].replace("\n", " ")
                ov = _overlap(prompt, text)
                if ov:  # only include memory rows that share real terms
                    pieces.append((1 + ov, f"[memory] {text}"))
    except Exception:
        pass

    pieces.sort(key=lambda x: -x[0])
    return "\n".join(text for _, text in pieces[:top_k])
