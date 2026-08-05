"""Audit trail - JSONL request log with per-agent timing + aggregation."""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any

AUDIT_DIR = Path(os.environ.get("COUNCIL_HOME", "/var/lib/council")) / "audit"
_lock = threading.Lock()


def _month_path(ts: float | None = None) -> Path:
    stamp = time.strftime("%Y%m", time.localtime(ts)) if ts else time.strftime("%Y%m")
    return AUDIT_DIR / f"council-{stamp}.jsonl"


def record(entry: dict[str, Any]) -> None:
    """Append one audit record (thread-safe)."""
    entry = dict(entry)
    entry.setdefault("ts", time.time())
    try:
        with _lock:
            AUDIT_DIR.mkdir(parents=True, exist_ok=True)
            path = _month_path(entry["ts"])
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass  # audit must never break the request path


def _read_all(limit: int | None = None) -> list[dict]:
    if not AUDIT_DIR.exists():
        return []
    entries: list[dict] = []
    for path in sorted(AUDIT_DIR.glob("council-*.jsonl"), reverse=True):
        try:
            for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
                try:
                    entries.append(json.loads(line))
                except Exception:
                    continue
        except Exception:
            continue
        if limit and len(entries) >= limit:
            break
    return entries[-limit:] if limit else entries


def recent(limit: int = 50) -> list[dict]:
    return _read_all(limit=max(1, min(limit, 500)))


def stats() -> dict:
    """Aggregate: totals, consensus rate, latency, per-agent + per-strategy."""
    entries = _read_all()
    total = len(entries)
    if total == 0:
        return {"total": 0, "consensus_rate": None, "avg_duration_ms": 0, "by_strategy": {}, "by_agent": {}}

    consensus = sum(1 for e in entries if e.get("consensus"))
    durations = [e.get("duration_ms", 0) for e in entries if isinstance(e.get("duration_ms"), (int, float))]
    avg_duration = round(sum(durations) / len(durations), 1) if durations else 0

    by_strategy: dict[str, dict] = {}
    by_agent: dict[str, dict] = {}
    for e in entries:
        strat = e.get("strategy", "unknown")
        s = by_strategy.setdefault(strat, {"count": 0, "consensus": 0})
        s["count"] += 1
        s["consensus"] += 1 if e.get("consensus") else 0
        for a in e.get("agents", []):
            name = a.get("agent", "?")
            slot = by_agent.setdefault(name, {"asked": 0, "live": 0, "mock": 0, "latency_ms": []})
            slot["asked"] += 1
            status = str(a.get("status", ""))
            if "live" in status:
                slot["live"] += 1
            elif "mock" in status or "offline" in status:
                slot["mock"] += 1
            if isinstance(a.get("latency"), (int, float)):
                slot["latency_ms"].append(a["latency"] * 1000)
    for name, slot in by_agent.items():
        lat = slot.pop("latency_ms")
        slot["avg_latency_ms"] = round(sum(lat) / len(lat), 1) if lat else 0

    return {
        "total": total,
        "consensus_rate": round(consensus / total, 3),
        "avg_duration_ms": avg_duration,
        "by_strategy": by_strategy,
        "by_agent": by_agent,
    }
