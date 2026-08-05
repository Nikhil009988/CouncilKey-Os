#!/usr/bin/env python3
"""Ollama-compatible DEMO LLM server for sandbox/demo environments only.

This server speaks the same HTTP protocol as Ollama (/api/tags, /api/generate)
so CouncilKey-Os's real OllamaAgentClient code path can be exercised end to
end in environments where real model weights cannot be downloaded.

It does NOT contain a neural network - it returns deterministic, role-aware
replies so the 3 council agents visibly answer with distinct voices.

For real inference run genuine Ollama instead:
    councilkey llm install && councilkey llm pull
"""
from __future__ import annotations

import json
import sys
import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="CouncilKey-Os demo LLM (Ollama-compatible)")


@app.get("/api/tags")
def tags() -> JSONResponse:
    return JSONResponse({"models": [{"name": "demo-llm", "size": 1}]})


@app.post("/api/generate")
async def generate(request: Request) -> JSONResponse:
    body = json.loads(await request.body())
    system = body.get("system", "")
    prompt = (body.get("prompt") or "").strip()
    prompt_snippet = " ".join(prompt.split())[:80]

    if "memory and analysis" in system:
        voice = ("Hermes (analysis): I have reviewed this request. Key points, constraints and risks are "
                 "clear, and I recommend proceeding with the plan below. ")
    elif "action and execution" in system:
        voice = ("OpenClaw (execution): Concrete plan - step 1: prepare, step 2: execute, step 3: verify. "
                 "Each step has a clear deliverable and a rollback path. ")
    else:
        voice = ("Agent Zero (review): I checked the plan for safety and correctness. It is sound; "
                 "final answer follows. ")

    return JSONResponse(
        {
            "model": body.get("model", "demo-llm"),
            "response": f"{voice}\n\n[You asked: {prompt_snippet}]\n\n"
                        f"(demo LLM response at {time.strftime('%H:%M:%S')} - "
                        "install real Ollama + a model for genuine inference)",
            "done": True,
        }
    )


if __name__ == "__main__":
    import uvicorn

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 11434
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
