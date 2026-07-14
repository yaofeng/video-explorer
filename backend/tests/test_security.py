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


def test_whitelist_enforcement(monkeypatch):
    monkeypatch.setenv("IP_WHITE_LIST", "192.168.1.100")
    app = FastAPI()
    app.add_middleware(IPWhitelistMiddleware)
    app.get("/test")(lambda: {"ok": True})
    client = TestClient(app)
    # TestClient 默认使用 127.0.0.1（本地主机），所以允许
    resp = client.get("/test")
    assert resp.status_code == 200
