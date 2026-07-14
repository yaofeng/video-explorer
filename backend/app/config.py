import os
import logging
from dataclasses import dataclass, field
from pathlib import Path
import yaml
from dotenv import load_dotenv

# 从项目根目录加载 .env 文件
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

logger = logging.getLogger(__name__)


__all__ = ("AppConfig", "load_config", "save_config", "data_path", "config_file", "ip_whitelist")


@dataclass
class AppConfig:
    video_path_list: list = field(default_factory=list)
    page_size: int = 0
    column_size: int = 4


def data_path() -> Path:
    p = Path(os.getenv("DATA_PATH", os.getcwd())).resolve()
    (p / "logs").mkdir(parents=True, exist_ok=True)
    (p / "cache").mkdir(parents=True, exist_ok=True)
    return p


def config_file() -> Path:
    return data_path() / "config.yaml"


def ip_whitelist() -> list[str]:
    raw = os.getenv("IP_WHITE_LIST", "").strip()
    if not raw:
        return []
    return [x.strip() for x in raw.replace(",", " ").split() if x.strip()]


def load_config() -> AppConfig:
    f = config_file()
    loaded = {}
    if f.exists():
        try:
            with open(f, "r", encoding="utf-8") as fh:
                loaded = yaml.safe_load(fh) or {}
        except (yaml.YAMLError, OSError) as exc:
            logger.warning("Failed to load config from %s: %s", f, exc)
    return AppConfig(
        video_path_list=list(loaded.get("video_path_list", []) or []),
        page_size=int(loaded.get("page_size", 0) or 0),
        column_size=int(loaded.get("column_size", 4) or 4),
    )


def save_config(cfg: AppConfig) -> None:
    data = {
        "video_path_list": list(cfg.video_path_list),
        "page_size": cfg.page_size,
        "column_size": cfg.column_size,
    }
    with open(config_file(), "w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, allow_unicode=True, sort_keys=False)
