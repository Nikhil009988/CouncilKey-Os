"""CouncilKey-Os Voting Strategies - Majority, Weighted, LLM Judge, Hermes Decides."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from council.config.loader import load as config_load
from council.llm.ollama import chat as ollama_chat

# Signals that a response should be voted down. Heuristic only - the LLM judge
# strategy performs a much deeper safety review.
DANGER_SIGNALS = (
    "danger",
    "rm -rf",
    "mkfs",
    "dd if=",
    "format ",
    "wipe ",
    "delete all",
    "erase ",
    "shutdown -h",
    "reboot",
    "install keylogger",
    "bypass login",
    "crack ",
)


@dataclass
class VoteResult:
    agent: str
    role: str
    response: str
    vote: str  # approve, reject, abstain
    confidence: float


def vote_for(response: str, status: str = "live") -> tuple[str, float]:
    """Heuristic vote + confidence for a single agent response."""
    lowered = (response or "").lower()
    vote = "reject" if any(sig in lowered for sig in DANGER_SIGNALS) else "approve"
    if "offline" in status or "mock" in status:
        confidence = 0.3
    elif "live" in status:
        confidence = 0.9
    else:
        confidence = 0.6
    return vote, confidence


class VotingStrategy:
    """Base voting strategy."""

    async def vote(self, prompt: str, responses: list[VoteResult], min_agreement: int = 2) -> dict[str, Any]:
        raise NotImplementedError


class MajorityVoting(VotingStrategy):
    """Simple majority - min_agreement approvals wins."""

    async def vote(self, prompt: str, responses: list[VoteResult], min_agreement: int = 2) -> dict[str, Any]:
        approve = sum(1 for r in responses if r.vote == "approve")
        consensus = approve >= min_agreement
        return {
            "strategy": "majority",
            "consensus_reached": consensus,
            "approve_count": approve,
            "total": len(responses),
            "min_agreement": min_agreement,
        }


class WeightedVoting(VotingStrategy):
    """Weighted by agent role weights from config."""

    async def vote(self, prompt: str, responses: list[VoteResult], min_agreement: int = 2) -> dict[str, Any]:
        config = config_load()
        weights = config.get("council", {}).get("agents", {})

        total_weight = 0.0
        approve_weight = 0.0

        for r in responses:
            weight = float(weights.get(r.agent, {}).get("weight", 1))
            total_weight += weight
            if r.vote == "approve":
                approve_weight += weight

        consensus = total_weight > 0 and approve_weight >= total_weight * 0.5
        return {
            "strategy": "weighted",
            "consensus_reached": consensus,
            "approve_weight": round(approve_weight, 2),
            "total_weight": round(total_weight, 2),
            "threshold": round(total_weight * 0.5, 2),
        }


class LLMJudgeVoting(VotingStrategy):
    """Use a local LLM to judge the best response and whether consensus is reached."""

    def __init__(self, judge_model: str | None = None):
        self.judge_model = judge_model or self._default_judge()

    @staticmethod
    def _default_judge() -> str:
        try:
            config = config_load()
            return str(config.get("council", {}).get("consensus", {}).get("judge_model", "qwen2.5:7b"))
        except Exception:
            return "qwen2.5:7b"

    async def vote(self, prompt: str, responses: list[VoteResult], min_agreement: int = 2) -> dict[str, Any]:
        responses_text = "\n\n".join(
            f"=== {r.agent} ({r.role}) ===\n{r.response}" for r in responses
        )

        judge_prompt = f"""You are an impartial judge evaluating a council of AI agents.

User asked: {prompt}

The agents responded:
{responses_text}

Your task:
1. Determine which response is best (most accurate, complete, safe, actionable)
2. Determine if the council should proceed (consensus) - majority agreement on safety/approach
3. Return JSON with: best_agent, consensus_reached, reasoning

Consider:
- Safety: Any dangerous commands or advice?
- Accuracy: Does the response correctly address the prompt?
- Completeness: Does it provide actionable steps?
- Consensus: Do at least {min_agreement} agents agree on the general approach?

Return ONLY valid JSON:
{{
  "best_agent": "agent-name",
  "consensus_reached": true/false,
  "reasoning": "brief explanation"
}}"""

        result = ollama_chat(self.judge_model, judge_prompt, "You are an impartial judge. Return only valid JSON.")

        if not result.get("ok"):
            return await MajorityVoting().vote(prompt, responses, min_agreement)

        try:
            judgment = json.loads(result.get("text", "{}"))
            return {
                "strategy": "llm_judge",
                "judge_model": self.judge_model,
                "consensus_reached": bool(judgment.get("consensus_reached", False)),
                "best_agent": judgment.get("best_agent"),
                "reasoning": judgment.get("reasoning", ""),
            }
        except Exception:
            return await MajorityVoting().vote(prompt, responses, min_agreement)


class HermesDecidesVoting(VotingStrategy):
    """Hermes (memory agent) makes the final decision."""

    async def vote(self, prompt: str, responses: list[VoteResult], min_agreement: int = 2) -> dict[str, Any]:
        hermes_response = next((r for r in responses if r.agent == "hermes"), None)

        if not hermes_response:
            return await MajorityVoting().vote(prompt, responses, min_agreement)

        other_approves = sum(1 for r in responses if r.agent != "hermes" and r.vote == "approve")
        consensus = hermes_response.vote == "approve" and other_approves >= 1

        return {
            "strategy": "hermes_decides",
            "consensus_reached": consensus,
            "hermes_vote": hermes_response.vote,
            "other_approves": other_approves,
            "best_agent": "hermes" if consensus else "none",
        }


_STRATEGIES = {
    "majority": MajorityVoting(),
    "weighted": WeightedVoting(),
    "llm_judge": LLMJudgeVoting(),
    "hermes_decides": HermesDecidesVoting(),
}


def get_voting_strategy(strategy: str, **kwargs) -> VotingStrategy:
    """Factory to get voting strategy by name (cached instances)."""
    if strategy == "llm_judge" and kwargs.get("judge_model"):
        return LLMJudgeVoting(kwargs["judge_model"])
    return _STRATEGIES.get(strategy, _STRATEGIES["majority"])


async def run_council_vote(
    prompt: str, agent_responses: list[dict], strategy: str = "majority", min_agreement: int = 2
) -> dict[str, Any]:
    """Run full council voting with the specified strategy."""
    votes: list[VoteResult] = []
    for r in agent_responses:
        vote, confidence = vote_for(r.get("response", ""), r.get("status", "live"))
        votes.append(
            VoteResult(
                agent=r.get("agent", ""),
                role=r.get("role", ""),
                response=r.get("response", ""),
                vote=vote,
                confidence=confidence,
            )
        )

    voting = get_voting_strategy(strategy)
    result = await voting.vote(prompt, votes, min_agreement)
    result["votes_detail"] = [
        {"agent": v.agent, "vote": v.vote, "confidence": v.confidence} for v in votes
    ]
    return result
