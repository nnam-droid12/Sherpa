import pytest
from fastapi.testclient import TestClient

from sherpa.config import LiveModeError, Settings, assert_sandbox_only
from sherpa.main import app


def test_healthz():
    res = TestClient(app).get("/healthz")
    assert res.status_code == 200
    assert res.json()["paypal"] == "sandbox"


def test_live_paypal_is_refused():
    s = Settings(PAYPAL_BASE_URL="https://api-m.paypal.com")
    with pytest.raises(LiveModeError):
        assert_sandbox_only(s)


def test_sandbox_is_allowed():
    assert_sandbox_only(Settings())
