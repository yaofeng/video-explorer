from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
from contextlib import asynccontextmanager
from . import config
from .security import IPWhitelistMiddleware
from .routes import config as config_routes, dirs, videos, scan, parse_rules
from .logging_setup import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动
    config.data_path()  # 确保目录存在
    yield
    # 关闭


app = FastAPI(lifespan=lifespan)

# 中间件
app.add_middleware(IPWhitelistMiddleware)

# 日志
setup_logging(config.data_path() / "logs")

# API 路由
app.include_router(config_routes.router, prefix="/api")
app.include_router(dirs.router, prefix="/api")
app.include_router(videos.router, prefix="/api")
app.include_router(scan.router, prefix="/api")
app.include_router(parse_rules.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok"}


# 静态文件（前端）
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    static_root = static_dir.resolve()

    @app.get("/")
    def root():
        return FileResponse(static_dir / "index.html")

    @app.get("/{path:path}")
    def catch_all(path: str):
        # /api/* 走 FastAPI 路由，不存在的 API 路径应返回 JSON 404，
        # 而不是被 SPA 兜底吞掉返回 HTML 200（M14）。
        if path.startswith("api"):
            raise HTTPException(404, "not found")

        # 路径包含校验：解析后必须仍在 static_dir 内（C1 路径遍历防护）。
        # %2e%2e 编码的 ".." 在路由后被解码，必须在此拦截。
        target = (static_dir / path).resolve()
        try:
            target.relative_to(static_root)
        except ValueError:
            return FileResponse(static_dir / "index.html")

        if target.exists() and target.is_file():
            return FileResponse(target)
        # SPA 回退
        return FileResponse(static_dir / "index.html")

