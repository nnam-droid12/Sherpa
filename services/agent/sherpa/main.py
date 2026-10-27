"""FastAPI entrypoint for the Sherpa agent service."""

import asyncio
import hmac
import json
import logging

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from sse_starlette.sse import EventSourceResponse

from sherpa import __version__
from sherpa.config import Settings, get_settings
from sherpa.logging import configure_logging
from sherpa.pipeline import STAGES, audit_job, spawn
from sherpa.store.artifacts import get_artifacts, sign
from sherpa.store.runs import get_store

settings = get_settings()
configure_logging(settings.log_level)
log = logging.getLogger("sherpa")

app = FastAPI(title="Sherpa Agent", version=__version__)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)


def require_api_key(
    x_sherpa_key: str | None = Header(default=None), s: Settings = Depends(get_settings)
) -> None:
    if s.api_key and x_sherpa_key != s.api_key:
        raise HTTPException(status_code=401, detail="invalid API key")


@app.get("/health")
@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True, "service": "sherpa-agent", "version": __version__, "paypal": "sandbox"}


@app.get("/api/config", dependencies=[Depends(require_api_key)])
def public_config(s: Settings = Depends(get_settings)) -> dict:
    return {
        "model": s.gemini_model,
        "computer_use_model": s.computer_use_model,
        "location": s.gcp_location,
        "paypal": "sandbox",
    }


@app.get("/api/demo-stores", dependencies=[Depends(require_api_key)])
def demo_stores(s: Settings = Depends(get_settings)) -> list[dict]:
    stores = [
        ("ember-oak", "Ember & Oak", "Outdoor gear, HTML/JS + Express", s.demo_ember_oak_url),
        ("lumen-bakehouse", "Lumen Bakehouse", "Preorder cakes, Next.js", s.demo_lumen_url),
    ]
    return [
        {
            "id": sid,
            "name": name,
            "tagline": tagline,
            "store_url": url,
            "repo": f"{s.demo_repo_owner}/sherpa-demo-{sid}",
        }
        for sid, name, tagline, url in stores
        if url
    ]


class NewRun(BaseModel):
    store_url: HttpUrl
    repo: str | None = None
    store_type: str = "auto"
    demo_store: str | None = None


@app.post("/api/runs", dependencies=[Depends(require_api_key)])
async def create_run(body: NewRun) -> dict:
    store = get_store()
    run = await store.create_run(
        {
            "store_url": str(body.store_url).rstrip("/"),
            "repo": body.repo or None,
            "store_type": body.store_type,
            "demo_store": body.demo_store,
        }
    )
    spawn(store, run["id"], "audit", lambda: audit_job(store, run))
    return run


@app.get("/api/runs", dependencies=[Depends(require_api_key)])
async def list_runs(limit: int = 30) -> list[dict]:
    return await get_store().list_runs(min(limit, 100))


@app.get("/api/runs/{run_id}", dependencies=[Depends(require_api_key)])
async def get_run(run_id: str) -> dict:
    run = await get_store().get_run(run_id)
    if not run:
        raise HTTPException(404, "run not found")
    return run


@app.get("/api/runs/{run_id}/events", dependencies=[Depends(require_api_key)])
async def stream_events(run_id: str, request: Request):
    store = get_store()
    queue = store.subscribe(run_id)

    async def gen():
        try:
            for ev in await store.list_events(run_id):
                yield {"event": "event", "data": json.dumps(ev, default=str)}
            run = await store.get_run(run_id)
            if run:
                yield {"event": "run", "data": json.dumps(run, default=str)}
            while not await request.is_disconnected():
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=15)
                except TimeoutError:
                    yield {"event": "ping", "data": "{}"}
                    continue
                payload = msg["event"] if msg["type"] == "event" else msg["run"]
                yield {"event": msg["type"], "data": json.dumps(payload, default=str)}
        finally:
            store.unsubscribe(run_id, queue)

    return EventSourceResponse(gen())


@app.get("/api/artifacts/{art_id:path}", dependencies=[Depends(require_api_key)])
async def get_artifact(art_id: str) -> Response:
    found = await get_artifacts().get(art_id)
    if not found:
        raise HTTPException(404, "artifact not found")
    data, content_type = found
    return Response(data, media_type=content_type, headers={"Cache-Control": "private, max-age=86400"})


@app.post("/api/runs/{run_id}/{stage}", dependencies=[Depends(require_api_key)])
async def start_stage(run_id: str, stage: str) -> dict:
    store = get_store()
    run = await store.get_run(run_id)
    if not run:
        raise HTTPException(404, "run not found")
    spec = STAGES.get(stage)
    if not spec:
        raise HTTPException(404, f"unknown stage {stage}")
    if str(run.get("status", "")).endswith(":running"):
        raise HTTPException(409, "another stage is still running")
    missing = [r for r in spec.requires if not run.get(r)]
    if missing:
        raise HTTPException(409, f"run {stage} after {', '.join(missing)}")
    spawn(store, run_id, spec.name, lambda: spec.job(store, run))
    return await store.update_run(run_id, status=f"{spec.name}:running", stage=spec.name)


@app.get("/public/artifacts/{art_id:path}")
async def public_artifact(art_id: str, sig: str) -> Response:
    if not hmac.compare_digest(sig, sign(art_id)):
        raise HTTPException(404, "artifact not found")
    found = await get_artifacts().get(art_id)
    if not found:
        raise HTTPException(404, "artifact not found")
    data, content_type = found
    return Response(data, media_type=content_type, headers={"Cache-Control": "public, max-age=604800"})
