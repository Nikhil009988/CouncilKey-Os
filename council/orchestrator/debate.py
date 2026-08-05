"""Iterative multi-round debate.

Round 1: every agent answers the prompt independently.
Rounds 2+: each agent sees a digest of the other agents' answers and may
revise its own (or reply CONFIRM). The debate stops early when all agents
converge (high similarity or explicit CONFIRM).

The final round is voted on with the standard voting strategies.
"""
from __future__ import annotations

import difflib
import time
from typing import Any

from council.orchestrator.agents import AgentResult, build_default_clients
from council.orchestrator.voting import run_council_vote

CONVERGENCE_THRESHOLD = 0.85


def _similar(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    return difflib.SequenceMatcher(None, a or "", b or "").ratio()


async def run_debate(
    prompt: str,
    rounds: int = 3,
    strategy: str = "majority",
    min_agreement: int = 2,
) -> dict[str, Any]:
    """Run a multi-round council debate and return the transcript + verdict."""
    rounds = max(2, min(int(rounds), 5))
    clients = build_default_clients()
    names = list(clients)

    # Round 1 - independent answers
    round_one = await _ask_all(clients, names, prompt)
    current: dict[str, AgentResult] = {r.agent: r for r in round_one}
    rounds_log: list[dict[str, Any]] = [
        {n: {"response": current[n].response, "status": current[n].status} for n in names}
    ]

    # Rounds 2+ - revise with awareness of the others
    for rnd in range(2, rounds + 1):
        digest = "\n".join(f"{n}: {current[n].response[:600]}" for n in names)
        revision_prompt = (
            f"{prompt}\n\n[Debate round {rnd} - what the other agents said:]\n{digest}\n\n"
            "Revise your answer based on their input, or reply 'CONFIRM' if you keep it unchanged."
        )
        revised = await _ask_all(clients, names, revision_prompt)
        updated = {r.agent: r for r in revised}
        rounds_log.append({n: {"response": updated[n].response, "status": updated[n].status} for n in names})

        scores = []
        for n in names:
            if "CONFIRM" in updated[n].response.upper():
                scores.append(1.0)
            else:
                scores.append(_similar(updated[n].response, current[n].response))
        current = updated
        if all(s >= CONVERGENCE_THRESHOLD for s in scores):
            break

    # Final vote on the last round
    agent_responses = [
        {"agent": n, "role": current[n].role, "response": current[n].response, "status": current[n].status}
        for n in names
    ]
    vote = await run_council_vote(prompt, agent_responses, strategy, min_agreement)
    votes = {v["agent"]: v["vote"] for v in vote.get("votes_detail", [])}
    approve = sum(1 for v in votes.values() if v == "approve")
    consensus = bool(vote.get("consensus_reached", approve >= min_agreement))

    final = "\n\n".join(
        f"## {n} ({current[n].role})\n{current[n].response}\n_Status: {current[n].status}_" for n in names
    )
    header = (
        f"# Council Decision - Consensus ✅ (after {len(rounds_log)} rounds)\n\n"
        if consensus
        else "# Council Decision - No Consensus ❌\n\n"
    )

    return {
        "strategy": strategy,
        "mode": "debate",
        "rounds": len(rounds_log),
        "max_rounds": rounds,
        "rounds_log": rounds_log,
        "votes": votes,
        "approve_count": approve,
        "consensus_reached": consensus,
        "best_agent": vote.get("best_agent"),
        "final": header + final,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }


async def _ask_all(clients: dict[str, Any], names: list[str], prompt: str) -> list[AgentResult]:
    import asyncio

    return list(await asyncio.gather(*[clients[n].ask(prompt) for n in names]))
