#!/usr/bin/env python3
"""Ollama-compatible + OpenAI-compatible DEMO server for sandbox testing only.

Speaks both:
- Ollama protocol: /api/tags, /api/generate
- OpenAI-compatible: /v1/chat/completions, /v1/models

So CouncilKey-Os's real provider client code paths can be exercised end to
end in environments where real model weights / APIs cannot be reached.

It does NOT contain a neural network - it returns deterministic, role-aware
replies so the three council agents visibly answer with distinct voices.

For real inference use a real provider instead:
    councilkey setup   (OpenAI / Anthropic / Gemini / OpenRouter)
"""
from __future__ import annotations

import json
import sys
import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="CouncilKey-Os demo AI server (Ollama + OpenAI compatible)")


# ------------------------------------------------------------ ollama protocol
@app.get("/api/tags")
def tags() -> JSONResponse:
    return JSONResponse({"models": [{"name": "demo-llm", "size": 1}]})


@app.post("/api/generate")
async def generate(request: Request) -> JSONResponse:
    body = json.loads(await request.body())
    system = body.get("system", "")
    prompt = (body.get("prompt") or "").strip()
    return JSONResponse(
        {
            "model": body.get("model", "demo-llm"),
            "response": _role_reply(system, prompt, "ollama"),
            "done": True,
        }
    )


# ------------------------------------------------------- openai-compatible api
@app.get("/v1/models")
def models() -> JSONResponse:
    return JSONResponse({"object": "list", "data": [{"id": "demo-model", "object": "model"}]})


@app.post("/v1/chat/completions")
async def chat_completions(request: Request) -> JSONResponse:
    body = json.loads(await request.body())
    messages = body.get("messages", [])
    system = next((m.get("content", "") for m in messages if m.get("role") == "system"), "")
    user = next((m.get("content", "") for m in messages if m.get("role") == "user"), "")
    return JSONResponse(
        {
            "id": "demo-chat",
            "object": "chat.completion",
            "model": body.get("model", "demo-model"),
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": _role_reply(system, user, "provider")},
                    "finish_reason": "stop",
                }
            ],
        }
    )


def _role_reply(system: str, prompt: str, via: str) -> str:
    prompt_snippet = " ".join(prompt.split())[:80]
    if "memory and analysis" in system:
        voice = ("Hermes (analysis): I have reviewed this request. Key points, constraints and risks are "
                 "clear, and I recommend proceeding with the plan below. ")
    elif "action and execution" in system:
        voice = ("OpenClaw (execution): Concrete plan - step 1: prepare, step 2: execute, step 3: verify. "
                 "Each step has a clear deliverable and a rollback path. ")
    elif "builder and review" in system or "builder & review" in system:
        voice = ("Agent Zero (review): I checked the plan for safety and correctness. It is sound; "
                 "final answer follows. ")
    else:
        voice = "Demo assistant: "
    return (
        f"{voice}\n\n[You asked: {prompt_snippet}]\n\n"
        f"(demo server reply via {via} at {time.strftime('%H:%M:%S')} - "
        "configure a real provider with 'councilkey setup' for genuine answers)"
    )


if __name__ == "__main__":
    import uvicorn

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 11434
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
