"""In-process async task queue with priorities.

The queue stores tasks in memory, runs them one at a time through registered
async handlers, and tracks status/result/error. Used by the /api/tasks
endpoints and the background scheduler.
"""
from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any, Callable, Coroutine

Handler = Callable[[dict[str, Any]], Coroutine[Any, Any, Any]]


class TaskQueue:
    def __init__(self) -> None:
        self._tasks: dict[str, dict[str, Any]] = {}
        self._handlers: dict[str, Handler] = {}
        self._worker_task: asyncio.Task | None = None
        self._stopped = False
        self.processed = 0

    # ------------------------------------------------------------------ api
    def register_handler(self, kind: str, handler: Handler) -> None:
        self._handlers[kind] = handler

    async def enqueue(self, kind: str, payload: dict[str, Any], priority: int = 5) -> str:
        task_id = uuid.uuid4().hex[:12]
        self._tasks[task_id] = {
            "id": task_id,
            "kind": kind,
            "payload": payload,
            "priority": max(0, min(9, int(priority))),
            "status": "queued",
            "created_at": time.time(),
            "started_at": None,
            "finished_at": None,
            "result": None,
            "error": None,
        }
        return task_id

    async def get(self, task_id: str) -> dict[str, Any] | None:
        task = self._tasks.get(task_id)
        return task

    async def list(self, limit: int = 50) -> list[dict[str, Any]]:
        tasks = sorted(self._tasks.values(), key=lambda t: -t["created_at"])
        return tasks[: max(1, min(limit, 200))]

    async def cancel(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if task and task["status"] == "queued":
            task["status"] = "cancelled"
            task["finished_at"] = time.time()
            return True
        return False

    def stats(self) -> dict[str, int]:
        counts = {"queued": 0, "running": 0, "done": 0, "failed": 0, "cancelled": 0}
        for t in self._tasks.values():
            counts[t["status"]] = counts.get(t["status"], 0) + 1
        counts["total"] = len(self._tasks)
        counts["processed"] = self.processed
        return counts

    # ---------------------------------------------------------------- worker
    async def run(self) -> None:
        while not self._stopped:
            ready = [t for t in self._tasks.values() if t["status"] == "queued"]
            if not ready:
                await asyncio.sleep(0.4)
                continue
            ready.sort(key=lambda t: (-t["priority"], t["created_at"]))
            task = ready[0]
            handler = self._handlers.get(task["kind"])
            task["status"] = "running"
            task["started_at"] = time.time()
            if handler is None:
                task["status"] = "failed"
                task["error"] = f"no handler registered for kind {task['kind']!r}"
                task["finished_at"] = time.time()
                continue
            try:
                task["result"] = await handler(task["payload"])
                task["status"] = "done"
            except Exception as exc:
                task["error"] = str(exc)
                task["status"] = "failed"
            finally:
                task["finished_at"] = time.time()
                self.processed += 1

    def start(self) -> None:
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self.run())

    async def stop(self) -> None:
        self._stopped = True
        if self._worker_task:
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
