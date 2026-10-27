"""Deploy a PR branch as a tagged, no-traffic Cloud Run revision of the store service."""

from __future__ import annotations

import asyncio
import io
import logging
import shutil
import tarfile
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import google.auth
import google.auth.transport.requests
import httpx

from sherpa.config import get_settings
from sherpa.gitrepo import clone

log = logging.getLogger(__name__)

Emit = Callable[..., Awaitable[Any]]
SKIP = {".git", "node_modules", ".next"}


def _token() -> str:
    creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    creds.refresh(google.auth.transport.requests.Request())
    return creds.token


def _tarball(root: Path) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for p in sorted(root.rglob("*")):
            rel = p.relative_to(root)
            if set(rel.parts) & SKIP or not p.is_file():
                continue
            tar.add(p, arcname=rel.as_posix())
    return buf.getvalue()


async def _api(method: str, url: str, **kw: Any) -> dict[str, Any]:
    token = await asyncio.to_thread(_token)
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.request(method, url, headers={"Authorization": f"Bearer {token}"}, **kw)
    if r.status_code >= 400:
        raise RuntimeError(f"{method} {url.split('?')[0]} failed: {r.status_code} {r.text[:400]}")
    return r.json() if r.content else {}


async def deploy_preview(
    repo: str, branch: str, service: str, tag: str, emit: Emit, timeout_s: int = 1500
) -> str:
    s = get_settings()
    project, region = s.gcp_project, s.gcp_region
    sa = f"sherpa-runtime@{project}.iam.gserviceaccount.com"
    image = f"{region}-docker.pkg.dev/{project}/sherpa/{service}:{tag}-{int(time.time())}"

    await emit("log", message=f"Packaging {branch} for a preview build")
    root = await clone(repo, branch)
    try:
        data = await asyncio.to_thread(_tarball, root)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    obj = f"preview-sources/{service}/{tag}-{int(time.time())}.tgz"
    await _api(
        "POST",
        f"https://storage.googleapis.com/upload/storage/v1/b/{s.artifacts_bucket}/o",
        params={"uploadType": "media", "name": obj},
        content=data,
        headers={"Content-Type": "application/gzip"},
    )

    build = {
        "source": {"storageSource": {"bucket": s.artifacts_bucket, "object": obj}},
        "steps": [
            {"name": "gcr.io/cloud-builders/docker", "args": ["build", "-t", image, "."]},
            {"name": "gcr.io/cloud-builders/docker", "args": ["push", image]},
            {
                "name": "gcr.io/google.com/cloudsdktool/cloud-sdk:slim",
                "entrypoint": "gcloud",
                "args": [
                    "run",
                    "deploy",
                    service,
                    "--image",
                    image,
                    "--region",
                    region,
                    "--tag",
                    tag,
                    "--no-traffic",
                    "--quiet",
                ],
            },
        ],
        "images": [image],
        "serviceAccount": f"projects/{project}/serviceAccounts/{sa}",
        "options": {"logging": "CLOUD_LOGGING_ONLY"},
        "timeout": f"{timeout_s}s",
        "tags": ["sherpa-preview", service, tag],
    }
    op = await _api(
        "POST",
        f"https://cloudbuild.googleapis.com/v1/projects/{project}/locations/{region}/builds",
        json=build,
    )
    build_id = op["metadata"]["build"]["id"]
    await emit("log", message=f"Cloud Build {build_id} started")

    started = time.monotonic()
    status = "QUEUED"
    while time.monotonic() - started < timeout_s:
        await asyncio.sleep(8)
        info = await _api(
            "GET",
            f"https://cloudbuild.googleapis.com/v1/projects/{project}/locations/{region}/builds/{build_id}",
        )
        if info["status"] != status:
            status = info["status"]
            await emit("log", message=f"Preview build {status.lower()}")
        if status in {"SUCCESS", "FAILURE", "INTERNAL_ERROR", "TIMEOUT", "CANCELLED", "EXPIRED"}:
            break
    if status != "SUCCESS":
        raise RuntimeError(f"Preview build ended with status {status}")

    svc = await _api(
        "GET", f"https://run.googleapis.com/v2/projects/{project}/locations/{region}/services/{service}"
    )
    for t in svc.get("trafficStatuses", []):
        if t.get("tag") == tag and t.get("uri"):
            await emit("log", message=f"Preview live at {t['uri']}")
            return t["uri"]
    raise RuntimeError("Preview revision deployed but no tagged URL was returned")
