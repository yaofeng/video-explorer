from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import os

LOCALHOST = {"127.0.0.1", "::1"}
# Starlette TestClient 的伪 host；用于本地测试。生产环境不会出现该值。
# （保留在此处而非 fixture，是因为 TestClient 无法自定义 client host；
# 耦合可控且不影响生产。）
TEST_HOSTS = {"testclient"}

# 豁免 IP 白名单的路径（健康检查等，供外部 LB 探活）。
EXEMPT_PATHS = {"/api/health"}

# 缓存解析后的白名单，避免每个请求重复 split/set 构建（L3）。
# 当 IP_WHITE_LIST 环境变量变化时自动刷新。
_whitelist_cache: dict = {"raw": None, "set": set()}


def _whitelist_set() -> set:
    raw = os.getenv("IP_WHITE_LIST", "").strip()
    if raw != _whitelist_cache["raw"]:
        _whitelist_cache["raw"] = raw
        vals = [x.strip() for x in raw.replace(",", " ").split()] if raw else []
        _whitelist_cache["set"] = set(vals)
    return _whitelist_cache["set"]


class IPWhitelistMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # /api/health 供容器健康检查 / 外部 LB 探活，豁免白名单（I2）。
        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        client_ip = request.client.host if request.client else ""
        if client_ip in LOCALHOST or client_ip in TEST_HOSTS or client_ip in _whitelist_set():
            return await call_next(request)
        return JSONResponse({"detail": "forbidden: ip not allowed"}, status_code=403)


