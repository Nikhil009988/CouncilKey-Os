"""CouncilKey-Os Voting Strategies - Majority, Weighted, LLM Judge, Hermes Decides."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Callable
from council.llm.ollama import chat as ollama_chat
from council.llm.manager import available as llm_available
from council.config.loader import load as config_load


@dataclass
class VoteResult:
    agent: str
    role: str
    response: str
    vote: str  # approve, reject, abstain
    confidence: float


class VotingStrategy:
    """Base voting strategy."""
    
    async def vote(self, prompt: str, responses: list[VoteResult], min_agreement: int = 2) -> dict[str, Any]:
        raise NotImplementedError


class MajorityVoting(VotingStrategy):
    """Simple majority - 2/3 approve wins."""
    
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
        
        total_weight = 0
        approve_weight = 0
        
        for r in responses:
            weight = weights.get(r.agent, {}).get("weight", 1)
            total_weight += weight
            if r.vote == "approve":
                approve_weight += weight
        
        consensus = approve_weight >= (total_weight * 0.5)  # >50% weighted
        return {
            "strategy": "weighted",
            "consensus_reached": consensus,
            "approve_weight": approve_weight,
            "total_weight": total_weight,
            "threshold": total_weight * 0.5,
        }


class LLMJudgeVoting(VotingStrategy):
    """Use an LLM to judge the best response and whether consensus reached."""
    
    def __init__(self, judge_model: str | None = None):
        self.judge_model = judge_model or "qwen2.5:7b"
    
    async def vote(self, prompt: str, responses: list[VoteResult], min_agreement: int = 2) -> dict[str, Any]:
        # Build judging prompt
        responses_text = "\n\n".join(
            f"=== {r.agent} ({r.role}) ===\n{r.response}"
            for r in responses
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
- Consensus: Do at least 2 agents agree on the general approach?

Return ONLY valid JSON:
{{
  "best_agent": "agent-name",
  "consensus_reached": true/false,
  "reasoning": "brief explanation"
}}"""
        
        result = ollama_chat(self.judge_model, judge_prompt, 
                           "You are an impartial judge. Return only valid JSON.")
        
        if not result.get("ok"):
            # Fallback to majority
            fallback = MajorityVoting()
            return await fallback.vote(prompt, responses, min_agreement)
        
        try:
            import json
            judgment = json.loads(result.get("text", "{}"))
            return {
                "strategy": "llm_judge",
                "judge_model": self.judge_model,
                "consensus_reached": judgment.get("consensus_reached", False),
                "best_agent": judgment.get("best_agent"),
                "reasoning": judgment.get("reasoning", ""),
            }
        except Exception:
            fallback = MajorityVoting()
            return await fallback.vote(prompt, responses, min_agreement)


class HermesDecidesVoting(VotingStrategy):
    """Hermes (memory agent) makes the final decision."""
    
    async def vote(self, prompt: str, responses: list[VoteResult], min_agreement: int = 2) -> dict[str, Any]:
        hermes_response = next((r for r in responses if r.agent == "hermes"), None)
        
        if not hermes_response:
            fallback = MajorityVoting()
            return await fallback.vote(prompt, responses, min_agreement)
        
        # Hermes decides based on its response
        # If Hermes approves and at least one other agrees, consensus
        other_approves = sum(1 for r in responses if r.agent != "hermes" and r.vote == "approve")
        consensus = hermes_response.vote == "approve" and other_approves >= 1
        
        return {
            "strategy": "hermes_decides",
            "consensus_reached": consensus,
            "hermes_vote": hermes_response.vote,
            "other_approves": other_approves,
            "best_agent": "hermes" if consensus else "none",
        }


def get_voting_strategy(strategy: str, **kwargs) -> VotingStrategy:
    """Factory to get voting strategy by name."""
    strategies = {
        "majority": MajorityVoting(),
        "weighted": WeightedVoting(),
        "llm_judge": LLMJudgeVoting(kwargs.get("judge_model")),
        "hermes_decides": HermesDecidesVoting(),
    }
    return strategies.get(strategy, MajorityVoting())


async def run_council_vote(prompt: str, agent_responses: list[dict], strategy: str = "majority", min_agreement: int = 2) -> dict[str, Any]:
    """Run full council voting with specified strategy."""
    # Convert to VoteResult objects
    votes = []
    for r in agent_responses:
        # Simple heuristic: if "danger" in response -> reject, else approve
        vote = "reject" if "danger" in r.get("response", "").lower() else "approve"
        votes.append(VoteResult(
            agent=r.get("agent", ""),
            role=r.get("role", ""),
            response=r.get("response", ""),
            vote=vote,
            confidence=0.8
        ))
    
    voting = get_voting_strategy(strategy)
    return await voting.vote(prompt, votes, min_agreement)