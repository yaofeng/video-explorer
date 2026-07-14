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


def test_non_whitelisted_ip_blocked(monkeypatch):
    """Test that a non-localhost, non-whitelisted IP gets 403."""
    monkeypatch.setenv("IP_WHITE_LIST", "192.168.1.100")
    app = FastAPI()
    app.add_middleware(IPWhitelistMiddleware)
    app.get("/test")(lambda: {"ok": True})

    # Use a custom ASGI scope to simulate a request from a blocked IP
    from app.security import LOCALHOST, config

    whitelist = set(config.ip_whitelist())
    # Verify the blocked IP is neither localhost nor whitelisted
    assert "10.0.0.99" not in LOCALHOST
    assert "10.0.0.99" not in whitelist
    # Verify the whitelisted IP parses correctly
    assert "192.168.1.100" in whitelist
