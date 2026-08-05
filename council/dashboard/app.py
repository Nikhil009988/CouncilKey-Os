"""CouncilKey-Os Dashboard app - thin alias over the council orchestrator.

Serving `council.dashboard.app:app` and `council.orchestrator.main:app` now
behave identically (previously the /api sub-app mount produced broken
/api/api/... routes).
"""
from __future__ import annotations

from fastapi import FastAPI

try:
    from council.orchestrator.main import app as council_app

    app: FastAPI = council_app
except Exception:  # pragma: no cover - fallback so uvicorn can still boot
    app = FastAPI(title="CouncilKey-Os Dashboard (degraded)")
