from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
from contextlib import asynccontextmanager
from . import config
from .security import IPWhitelistMiddleware
from .routes import config as config_routes, dirs, videos, scan, parse_rules
import logging
from logging.handlers import RotatingFileHandler


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
log_dir = config.data_path() / "logs"
log_dir.mkdir(parents=True, exist_ok=True)
handler = RotatingFileHandler(
    log_dir / "app.log", maxBytes=10*1024*1024, backupCount=5, encoding="utf-8"
)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[handler, logging.StreamHandler()],
)

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

    @app.get("/")
    def root():
        return FileResponse(static_dir / "index.html")

    @app.get("/{path:path}")
    def catch_all(path: str):
        file = static_dir / path
        if file.exists():
            return FileResponse(file)
        # SPA 回退
        return FileResponse(static_dir / "index.html")
