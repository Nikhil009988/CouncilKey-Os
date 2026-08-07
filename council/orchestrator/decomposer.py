"""Task decomposition - split complex prompts into focused subtasks.

Each subtask is executed by the agent whose role fits it best:
- Analysis & Research  -> Hermes (memory)
- Execution Plan       -> OpenClaw (action)
- Review & Polish      -> OpenCode (builder)

The three subtask outputs are then voted on as a council.
"""
from __future__ import annotations

import time
from typing import Any

from council.orchestrator.agents import build_default_clients
from council.orchestrator.voting import run_council_vote

SUBTASKS: list[dict[str, str]] = [
    {
        "id": "analysis",
        "title": "Analysis & Research",
        "agent": "hermes",
        "focus": "Analyze the request: goals, constraints, risks, and any missing information. Note relevant prior context.",
    },
    {
        "id": "execution",
        "title": "Execution Plan",
        "agent": "openclaw",
        "focus": "Produce a concrete, step-by-step action plan with specific commands or deliverables.",
    },
    {
        "id": "review",
        "title": "Review & Polish",
        "agent": "opencode",
        "focus": "Review the analysis and the plan for safety, correctness, and completeness. Write the final polished answer.",
    },
]


def decompose_prompt(prompt: str) -> list[dict[str, str]]:
    """Return the subtask list for a prompt (deterministic, role-based)."""
    return list(SUBTASKS)


async def run_decomposed(prompt: str, strategy: str = "majority", min_agreement: int = 2) -> dict[str, Any]:
    """Execute the decomposed pipeline: subtasks -> council vote -> synthesis."""
    clients = build_default_clients()
    subtasks: list[dict[str, Any]] = []

    for sub in SUBTASKS:
        client = clients.get(sub["agent"])
        if client is None:  # pragma: no cover - clients always present
            continue
        focused = f"[Subtask: {sub['title']}]\n{sub['focus']}\n\nOriginal request: {prompt}"
        result = await client.ask(focused)
        subtasks.append(
            {
                "id": sub["id"],
                "title": sub["title"],
                "agent": result.agent,
                "role": result.role,
                "response": result.response,
                "status": result.status,
                "latency": round(result.latency, 2),
            }
        )

    agent_responses = [
        {"agent": s["agent"], "role": s["role"], "response": s["response"], "status": s["status"]}
        for s in subtasks
    ]
    vote = await run_council_vote(prompt, agent_responses, strategy, min_agreement)
    votes = {v["agent"]: v["vote"] for v in vote.get("votes_detail", [])}
    approve = sum(1 for v in votes.values() if v == "approve")
    consensus = bool(vote.get("consensus_reached", approve >= min_agreement))

    final = "\n\n".join(f"## {s['title']} ({s['agent']})\n{s['response']}" for s in subtasks)
    header = "# Council Decision - Consensus ✅\n\n" if consensus else "# Council Decision - No Consensus ❌\n\n"

    return {
        "strategy": strategy,
        "mode": "decomposed",
        "subtasks": subtasks,
        "votes": votes,
        "approve_count": approve,
        "consensus_reached": consensus,
        "best_agent": vote.get("best_agent"),
        "final": header + final,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
