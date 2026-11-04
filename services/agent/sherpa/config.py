"""Runtime configuration loaded from environment variables."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PAYPAL_SANDBOX_BASE = "https://api-m.sandbox.paypal.com"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = Field(default="local", alias="SHERPA_ENV")
    api_key: str = Field(default="", alias="SHERPA_API_KEY")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Gemini on Gemini Enterprise Agent Platform (Vertex AI), auth via ADC.
    gcp_project: str = Field(default="nixora-project", alias="GOOGLE_CLOUD_PROJECT")
    gcp_location: str = Field(default="global", alias="GOOGLE_CLOUD_LOCATION")
    gemini_model: str = Field(default="gemini-3.8-flash", alias="SHERPA_GEMINI_MODEL")
    computer_use_model: str = Field(default="gemini-3.8-flash", alias="SHERPA_COMPUTER_USE_MODEL")

    paypal_base_url: str = Field(default=PAYPAL_SANDBOX_BASE, alias="PAYPAL_BASE_URL")
    paypal_client_id: str = Field(default="", alias="PAYPAL_CLIENT_ID")
    paypal_client_secret: str = Field(default="", alias="PAYPAL_CLIENT_SECRET")
    paypal_webhook_id: str = Field(default="", alias="PAYPAL_WEBHOOK_ID")
    paypal_buyer_email: str = Field(default="", alias="PAYPAL_SANDBOX_BUYER_EMAIL")
    paypal_buyer_password: str = Field(default="", alias="PAYPAL_SANDBOX_BUYER_PASSWORD")

    kernel_api_key: str = Field(default="", alias="KERNEL_API_KEY")
    channel3_api_key: str = Field(default="", alias="CHANNEL3_API_KEY")
    github_token: str = Field(default="", alias="GITHUB_TOKEN")

    cors_origins: str = Field(default="*", alias="SHERPA_CORS_ORIGINS")
    firestore_db: str = Field(default="sherpa", alias="SHERPA_FIRESTORE_DB")
    gcp_region: str = Field(default="us-east1", alias="GCP_REGION")
    artifacts_bucket: str = Field(default="nixora-project-sherpa-artifacts", alias="SHERPA_ARTIFACTS_BUCKET")
    demo_ember_oak_url: str = Field(default="", alias="DEMO_EMBER_OAK_URL")
    demo_lumen_url: str = Field(default="", alias="DEMO_LUMEN_URL")
    demo_repo_owner: str = Field(default="nnam-droid12", alias="DEMO_REPO_OWNER")
    public_url: str = Field(default="http://localhost:8080", alias="SHERPA_PUBLIC_URL")
    demo_mode: bool = Field(default=True, alias="SHERPA_DEMO_MODE")
    runs_per_hour: int = Field(default=6, alias="SHERPA_RUNS_PER_HOUR")


class LiveModeError(RuntimeError):
    """Raised when configuration points at live PayPal instead of the sandbox."""


def assert_sandbox_only(settings: Settings) -> None:
    """Refuse to start if anything points at live PayPal."""
    base = settings.paypal_base_url.rstrip("/")
    if base != PAYPAL_SANDBOX_BASE:
        raise LiveModeError(f"PAYPAL_BASE_URL must be {PAYPAL_SANDBOX_BASE}, got {base!r}")
    # Live REST client ids start with "A" too, so the base URL is the real guard;
    # the env label is a second, explicit opt-out of live mode.
    if settings.env.lower() in {"live", "production-live"}:
        raise LiveModeError("Sherpa only runs against the PayPal sandbox")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    assert_sandbox_only(settings)
    return settings
