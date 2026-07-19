from fastapi import APIRouter
from .. import config
from ..models import ConfigModel
from ..services.scanner import get_shared_scanner

router = APIRouter()


@router.get("/config", response_model=ConfigModel)
def get_config():
    cfg = config.load_config()
    return ConfigModel(
        video_path_list=cfg.video_path_list,
        page_size=cfg.page_size,
        column_size=cfg.column_size,
        parse_rules=cfg.parse_rules,
    )


@router.put("/config", response_model=ConfigModel)
def update_config(model: ConfigModel):
    # 读取旧配置以检测 parse_rules 是否变化
    old_cfg = config.load_config()
    old_rules = old_cfg.parse_rules

    cfg = config.AppConfig(
        video_path_list=model.video_path_list,
        page_size=model.page_size,
        column_size=model.column_size,
        parse_rules=model.parse_rules,
    )
    config.save_config(cfg)

    # parse_rules 变化 → 通知 scanner 清除内存缓存，下次打开目录会重新解析
    if model.parse_rules != old_rules:
        get_shared_scanner().invalidate_all_caches()

    return ConfigModel(
        video_path_list=cfg.video_path_list,
        page_size=cfg.page_size,
        column_size=cfg.column_size,
        parse_rules=cfg.parse_rules,
    )
