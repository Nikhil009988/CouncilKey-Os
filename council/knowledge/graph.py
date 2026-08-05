"""CouncilKey-Os Knowledge Graph (JSON store with dedupe + search)."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

GRAPH_PATH = Path(os.environ.get("COUNCIL_HOME", "/var/lib/council")) / "shared" / "knowledge-graph.json"


def _load() -> dict[str, Any]:
    if GRAPH_PATH.exists():
        try:
            return json.loads(GRAPH_PATH.read_text())
        except Exception:
            return {"nodes": [], "edges": []}
    return {"nodes": [], "edges": []}


def _save(graph: dict[str, Any]) -> None:
    GRAPH_PATH.parent.mkdir(parents=True, exist_ok=True)
    GRAPH_PATH.write_text(json.dumps(graph, ensure_ascii=False, indent=2))


def add_node(node_id: str, label: str, kind: str = "concept") -> dict[str, Any]:
    """Add a node, skipping if the id already exists."""
    graph = _load()
    nodes = graph.setdefault("nodes", [])
    if not any(n.get("id") == node_id for n in nodes):
        nodes.append({"id": node_id, "label": label, "kind": kind})
        _save(graph)
    return graph


def add_edge(source: str, target: str, relation: str = "related") -> dict[str, Any]:
    """Add an edge, skipping duplicate (source, target, relation) triples."""
    graph = _load()
    edges = graph.setdefault("edges", [])
    if not any(
        e.get("source") == source and e.get("target") == target and e.get("relation") == relation
        for e in edges
    ):
        edges.append({"source": source, "target": target, "relation": relation})
        _save(graph)
    return graph


def search(query: str) -> dict[str, Any]:
    """Search nodes by label/id substring."""
    graph = _load()
    q = (query or "").lower().strip()
    if not q:
        return {"query": query, "nodes": []}
    nodes = [
        n
        for n in graph.get("nodes", [])
        if q in str(n.get("label", "")).lower() or q in str(n.get("id", "")).lower()
    ]
    return {"query": query, "count": len(nodes), "nodes": nodes}
