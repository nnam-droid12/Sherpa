"""Screenshot and report storage in Cloud Storage, served back through the agent API."""

from __future__ import annotations

import asyncio
import logging
import uuid

from sherpa.config import get_settings

log = logging.getLogger(__name__)


class Artifacts:
    def __init__(self) -> None:
        s = get_settings()
        self._bucket = None
        self._mem: dict[str, tuple[bytes, str]] = {}
        if s.env != "test" and s.artifacts_bucket:
            try:
                from google.cloud import storage

                self._bucket = storage.Client(project=s.gcp_project).bucket(s.artifacts_bucket)
            except Exception:
                log.warning("Cloud Storage unavailable; keeping artifacts in memory", exc_info=True)

    async def put(self, run_id: str, data: bytes, content_type: str = "image/jpeg", ext: str = "jpg") -> str:
        art_id = f"{run_id}/{uuid.uuid4().hex[:10]}.{ext}"
        self._mem[art_id] = (data, content_type)
        if len(self._mem) > 400:
            self._mem.pop(next(iter(self._mem)))
        if self._bucket is not None:
            blob = self._bucket.blob(art_id)
            try:
                await asyncio.to_thread(blob.upload_from_string, data, content_type=content_type)
            except Exception:
                log.warning("artifact upload failed", exc_info=True)
        return art_id

    async def get(self, art_id: str) -> tuple[bytes, str] | None:
        if art_id in self._mem:
            return self._mem[art_id]
        if self._bucket is None:
            return None
        blob = self._bucket.blob(art_id)
        try:
            data = await asyncio.to_thread(blob.download_as_bytes)
        except Exception:
            return None
        return data, blob.content_type or "image/jpeg"


_artifacts: Artifacts | None = None


def get_artifacts() -> Artifacts:
    global _artifacts
    if _artifacts is None:
        _artifacts = Artifacts()
    return _artifacts
