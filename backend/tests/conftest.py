import os
import tempfile
from pathlib import Path

import pytest

_tmp = Path(tempfile.mkdtemp(prefix="fsp-career-test-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_tmp / 'test.db').as_posix()}"
os.environ["SEED_DEMO"] = "true"
os.environ["SEED_CANDIDATES"] = "80"
os.environ["EMAIL_DEV_MODE"] = "true"
os.environ["FSP_ENABLED"] = "false"


@pytest.fixture(autouse=True)
def _reset_login_limiter():
    """Лимит попыток входа (8 за 5 минут на e-mail) — общий для процесса: тесты не должны зависеть от того, сколько
    раз демо-аккаунты входили в предыдущих тестах."""
    from app.api.auth import _login_attempts

    _login_attempts.clear()
    yield


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


def login(client, email: str, password: str = "demo12345") -> dict:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
