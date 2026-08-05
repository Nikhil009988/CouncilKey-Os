"""CouncilKey-Os Dashboard."""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

try:
    from council.orchestrator.main import app as council_app
    _html = (Path(__file__).parent / "index.html").read_text(encoding="utf-8")
except Exception:
    council_app = None
    _html = "<html><body><h1>Council Dashboard</h1></body></html>"

app = FastAPI()
app.mount("/api", council_app or FastAPI())
