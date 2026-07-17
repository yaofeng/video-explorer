import asyncio
from fastapi import FastAPI
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.security import IPWhitelistMiddleware, _whitelist_cache


def _make_request(host: str, path: str = "/test") -> Request:
    """构造一个指定 client host 的 Request（TestClient 无法自定义 host）。"""
    return Request({
        "type": "http",
        "method": "GET",
        "path": path,
        "headers": [],
        "query_string": b"",
        "client": (host, 12345),
    })


async def _ok(request):
    return JSONResponse({"ok": True})


def _dispatch(host: str, path: str = "/test"):
    """用真实中间件实例驱动一次 dispatch，返回响应。"""
    app = FastAPI()
    mw = IPWhitelistMiddleware(app)
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(mw.dispatch(_make_request(host, path), _ok))
    finally:
        loop.close()


def _invalidate_whitelist_cache():
    _whitelist_cache["raw"] = None


def test_localhost_allowed(monkeypatch):
    monkeypatch.setenv("IP_WHITE_LIST", "")
    _invalidate_whitelist_cache()
    resp = _dispatch("127.0.0.1")
    assert resp.status_code == 200


def test_whitelist_enforcement(monkeypatch):
    monkeypatch.setenv("IP_WHITE_LIST", "192.168.1.100")
    _invalidate_whitelist_cache()
    # 白名单内的 IP 放行
    resp = _dispatch("192.168.1.100")
    assert resp.status_code == 200


def test_non_whitelisted_ip_blocked(monkeypatch):
    """非 localhost、非白名单的 IP 应返回 403（真正驱动 dispatch，覆盖 403 分支）。"""
    monkeypatch.setenv("IP_WHITE_LIST", "192.168.1.100")
    _invalidate_whitelist_cache()
    resp = _dispatch("10.0.0.99")
    assert resp.status_code == 403
    assert b"forbidden" in resp.body


def test_health_exempt_from_whitelist(monkeypatch):
    """/api/health 豁免白名单（I2）：即使来自非白名单 IP 也放行。"""
    monkeypatch.setenv("IP_WHITE_LIST", "192.168.1.100")
    _invalidate_whitelist_cache()
    resp = _dispatch("10.0.0.99", path="/api/health")
    assert resp.status_code == 200


def test_x_forwarded_for_extracts_real_ip(monkeypatch):
    """经过可信代理时，X-Forwarded-For 的第一个 IP 作为真实客户端 IP。"""
    monkeypatch.setenv("IP_WHITE_LIST", "203.0.113.50")
    monkeypatch.setenv("FORWARDED_ALLOW_IPS", "10.0.0.1")  # 信任的代理
    _invalidate_whitelist_cache()

    # 重新加载 main 以应用新的 FORWARDED_ALLOW_IPS
    import importlib
    from app import main as main_module
    importlib.reload(main_module)
    from app.main import app
    from fastapi.testclient import TestClient

    client = TestClient(app)
    # 直连代理 IP 10.0.0.1，真实客户端 203.0.113.50
    resp = client.get("/api/config", headers={
        "X-Forwarded-For": "203.0.113.50",
    })
    # 真实 IP 在白名单中 → 放行
    assert resp.status_code == 200

    # 清理：恢复默认 FORWARDED_ALLOW_IPS
    monkeypatch.setenv("FORWARDED_ALLOW_IPS", "127.0.0.1")
    importlib.reload(main_module)
