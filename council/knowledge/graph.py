"""CouncilKey-Os Knowledge Graph."""
from __future__ import annotations

import json
import os
from pathlib import Path

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
    graph = _load()
    graph.setdefault("nodes", [])
    graph["nodes"].append({"id": node_id, "label": label, "kind": kind})
    _save(graph)
    return graph


def add_edge(source: str, target: str, relation: str = "related") -> dict[str, Any]:
    graph = _load()
    graph.setdefault("edges", [])
    graph["edges"].append({"source": source, "target": target, "relation": relation})
    _save(graph)
    return graph
