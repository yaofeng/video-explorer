from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.security import IPWhitelistMiddleware


def test_localhost_allowed(monkeypatch):
    monkeypatch.setenv("IP_WHITE_LIST", "")
    app = FastAPI()
    app.add_middleware(IPWhitelistMiddleware)
    app.get("/test")(lambda: {"ok": True})
    client = TestClient(app)
    resp = client.get("/test")
    assert resp.status_code == 200
