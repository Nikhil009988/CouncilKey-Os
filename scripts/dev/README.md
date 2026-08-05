# Dev / test utilities

These are **development-only** tools. They are NOT part of the product and
are not used by setup, start, or the dashboard.

## `llm-demo-server.py` - Ollama-compatible demo server

Implements the Ollama HTTP protocol (`/api/tags`, `/api/generate`) with
deterministic, role-aware replies. Its only purpose is to exercise
CouncilKey-Os's real Ollama client code path in sandboxes/CI where real
model weights cannot be downloaded. It contains **no neural network**.

For real inference use genuine Ollama instead:

```bash
councilkey llm install    # install Ollama (winget on Windows)
councilkey llm pull       # download qwen2.5:3b (~1.9GB)
```
