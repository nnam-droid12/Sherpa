"""Run and event persistence in Firestore, plus in-process fan-out for SSE streams."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections import defaultdict
from typing import Any

from sherpa.config import get_settings

log = logging.getLogger(__name__)


class RunStore:
    """Persists runs/events. Falls back to memory when Firestore is unavailable (tests, local)."""

    def __init__(self, use_firestore: bool | None = None) -> None:
        settings = get_settings()
        self._db = None
        if use_firestore if use_firestore is not None else settings.env != "test":
            try:
                from google.cloud import firestore

                self._db = firestore.AsyncClient(project=settings.gcp_project, database=settings.firestore_db)
            except Exception:
                log.warning("Firestore unavailable; using in-memory store", exc_info=True)
        self._runs: dict[str, dict[str, Any]] = {}
        self._events: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)

    # --- runs -------------------------------------------------------------
    async def create_run(self, data: dict[str, Any]) -> dict[str, Any]:
        run_id = uuid.uuid4().hex[:12]
        now = time.time()
        run = {"id": run_id, "status": "queued", "created_at": now, "updated_at": now, **data}
        self._runs[run_id] = run
        if self._db:
            await self._db.collection("runs").document(run_id).set(run)
        return run

    async def update_run(self, run_id: str, **fields: Any) -> dict[str, Any]:
        fields["updated_at"] = time.time()
        run = self._runs.setdefault(run_id, {"id": run_id})
        run.update(fields)
        if self._db:
            await self._db.collection("runs").document(run_id).set(fields, merge=True)
        await self._publish(run_id, {"type": "run", "run": run})
        return run

    async def get_run(self, run_id: str) -> dict[str, Any] | None:
        if run_id in self._runs:
            return self._runs[run_id]
        if self._db:
            snap = await self._db.collection("runs").document(run_id).get()
            if snap.exists:
                return snap.to_dict()
        return None

    async def list_runs(self, limit: int = 30) -> list[dict[str, Any]]:
        if self._db:
            from google.cloud import firestore

            query = self._db.collection("runs").order_by("created_at", direction=firestore.Query.DESCENDING)
            return [d.to_dict() async for d in query.limit(limit).stream()]
        return sorted(self._runs.values(), key=lambda r: r["created_at"], reverse=True)[:limit]

    # --- events -----------------------------------------------------------
    async def add_event(self, run_id: str, kind: str, **data: Any) -> dict[str, Any]:
        events = self._events[run_id]
        event = {"run_id": run_id, "seq": len(events), "ts": time.time(), "kind": kind, **data}
        events.append(event)
        if self._db:
            stored = {k: v for k, v in event.items() if k != "screenshot_b64"}
            doc_id = f"{run_id}-{event['seq']:05d}"
            try:
                await self._db.collection("events").document(doc_id).set(stored)
            except Exception:
                log.warning("event persist failed", exc_info=True)
        await self._publish(run_id, {"type": "event", "event": event})
        return event

    async def list_events(self, run_id: str) -> list[dict[str, Any]]:
        if self._events.get(run_id):
            return self._events[run_id]
        if self._db:
            query = self._db.collection("events").where("run_id", "==", run_id).order_by("seq")
            return [d.to_dict() async for d in query.stream()]
        return []

    # --- streaming --------------------------------------------------------
    def subscribe(self, run_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._subscribers[run_id].add(queue)
        return queue

    def unsubscribe(self, run_id: str, queue: asyncio.Queue) -> None:
        self._subscribers[run_id].discard(queue)

    async def _publish(self, run_id: str, message: dict[str, Any]) -> None:
        for queue in list(self._subscribers.get(run_id, ())):
            if not queue.full():
                queue.put_nowait(message)


_store: RunStore | None = None


def get_store() -> RunStore:
    global _store
    if _store is None:
        _store = RunStore()
    return _store
