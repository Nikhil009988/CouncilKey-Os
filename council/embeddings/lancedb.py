"""CouncilKey-Os LanceDB + embeddings helper."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

try:
    import lancedb  # type: ignore
    from lancedb import LanceDBConnection  # type: ignore
except Exception:  # pragma: no cover - optional
    lancedb = None  # type: ignore
    LanceDBConnection = None  # type: ignore

COUNCIL_HOME = Path(os.environ.get("COUNCIL_HOME", "/var/lib/council"))
LANE_DIR = COUNCIL_HOME / "lance"


def _ensure() -> None:
    if lancedb is None:
        raise RuntimeError("pip install lancedb")
    LANE_DIR.mkdir(parents=True, exist_ok=True)


def embed_text(text: str) -> list[float]:
    # Demo deterministic hash embedding for offline/no-internet use.
    h = hashlib.sha256(text.encode("utf-8", errors="ignore")).digest()
    vals = []
    for i in range(384):
        vals.append((h[i % len(h)] / 255.0) * 2 - 1)
    s = sum(vals)
    if s:
        vals = [v / s for v in vals]
    return vals


def add_documents(docs: list[str]) -> dict[str, object]:
    _ensure()
    if lancedb is None:
        return {"ok": False, "error": "lancedb not installed"}
    try:
        import pyarrow as pa
        db = lancedb.connect(str(LANE_DIR))
        if "council_knowledge" in db.list_tables():
            tbl = db.open_table("council_knowledge")
        else:
            schema = pa.schema([
                pa.field("vector", pa.list_(pa.float32(), 384)),
                pa.field("text", pa.string())
            ])
            tbl = db.create_table("council_knowledge", schema=schema)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    rows = [{"vector": embed_text(t), "text": t} for t in docs]
    try:
        tbl.add(rows)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "added": len(rows)}


def search(query: str, limit: int = 5) -> dict[str, object]:
    _ensure()
    if lancedb is None:
        return {"ok": False, "error": "lancedb not installed", "results": []}
    try:
        db = lancedb.connect(str(LANE_DIR))
        tbl = db.open_table("council_knowledge")
        qv = embed_text(query)
        res = tbl.search(qv).limit(limit).to_list()
        return {"ok": True, "results": [{"text": r.get("text"), "_distance": r.get("_distance")} for r in res]}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "results": []}
