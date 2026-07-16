"""日志配置模块。

将日志初始化逻辑从 main.py 抽取到独立模块，便于复用和测试。
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging(log_dir: Path) -> None:
    """初始化应用日志：文件轮转 + 控制台输出。

    Args:
        log_dir: 日志文件存放目录（不存在则创建）。
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        log_dir / "app.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[handler, logging.StreamHandler()],
    )
