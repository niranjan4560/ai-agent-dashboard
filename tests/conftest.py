import os
import sys
from pathlib import Path

import pytest

# Tests only ever touch TEST_DATABASE_URL (default: a throwaway SQLite file),
# never the DATABASE_URL from .env — tables are dropped between tests.
_db_file = Path(__file__).parent / "test.db"
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", f"sqlite:///{_db_file}")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production-use-0123456789")
os.environ.setdefault("CHAT_RATE_LIMIT_PER_MINUTE", "100")
for key in ("GEMINI_API_KEY", "OPENWEATHER_API_KEY", "NEWS_API_KEY", "GITHUB_USERNAME", "GITHUB_TOKEN"):
    os.environ[key] = ""

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402
from database import Base, engine  # noqa: E402


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    main._chat_calls.clear()
    with TestClient(main.app) as c:   # runs lifespan → creates tables
        yield c
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def mock_http(monkeypatch):
    """Route every httpx.AsyncClient request in main.py through `handler`."""
    def install(handler):
        real = httpx.AsyncClient

        def factory(*args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(handler)
            return real(*args, **kwargs)

        monkeypatch.setattr(main.httpx, "AsyncClient", factory)
    return install


def register_and_login(client, username="alice", email="alice@example.com", password="s3cret-pass"):
    r = client.post("/register", json={"username": username, "email": email, "password": password})
    assert r.status_code == 200, r.text
    r = client.post("/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture()
def auth(client):
    return register_and_login(client)
