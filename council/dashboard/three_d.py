"""3D dashboard app - importable alias.

The source lives in `council/dashboard/3d/dashboard_3d.py`, but a package
named `3d` cannot be imported with normal Python syntax. This module makes
it importable as `council.dashboard.three_d` and is what the main server
uses to serve the 3D page at `/3d`.
"""
from __future__ import annotations

from importlib import import_module

_mod = import_module("council.dashboard.3d.dashboard_3d")
create_app_3d = _mod.create_app_3d

# module-level app so `uvicorn council.dashboard.three_d:app` works directly
app = create_app_3d()

__all__ = ["app", "create_app_3d"]
