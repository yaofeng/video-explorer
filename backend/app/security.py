from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from . import config

LOCALHOST = {"127.0.0.1", "::1", "testclient"}


class IPWhitelistMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        whitelist = set(config.ip_whitelist())
        client_ip = request.client.host if request.client else ""
        if client_ip in LOCALHOST or client_ip in whitelist:
            return await call_next(request)
        return JSONResponse({"detail": "forbidden: ip not allowed"}, status_code=403)
