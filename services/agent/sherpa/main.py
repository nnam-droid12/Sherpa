"""FastAPI entrypoint for the Sherpa agent service."""

import logging

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from sherpa import __version__
from sherpa.config import Settings, get_settings
from sherpa.logging import configure_logging

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
