"""Gemini on Gemini Enterprise Agent Platform (Vertex AI), authenticated with ADC."""

from __future__ import annotations

from functools import lru_cache

from google import genai
from google.genai import errors, types
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from sherpa.config import get_settings


@lru_cache
def get_client() -> genai.Client:
    s = get_settings()
    return genai.Client(vertexai=True, project=s.gcp_project, location=s.gcp_location)


def _retryable(exc: BaseException) -> bool:
    if isinstance(exc, errors.APIError):
        return exc.code in (408, 429, 500, 502, 503, 504)
    return isinstance(exc, (TimeoutError, ConnectionError))


@retry(reraise=True, stop=stop_after_attempt(4), wait=wait_exponential(multiplier=1, max=20), retry=retry_if_exception(_retryable))
async def generate(model: str, contents, config: types.GenerateContentConfig) -> types.GenerateContentResponse:
    return await get_client().aio.models.generate_content(model=model, contents=contents, config=config)
