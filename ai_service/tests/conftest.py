import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


@pytest.fixture(autouse=True)
def _set_internal_key(monkeypatch):
    monkeypatch.setattr(settings, "internal_api_key", "test-key")


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_headers():
    return {"X-Internal-Api-Key": "test-key"}
