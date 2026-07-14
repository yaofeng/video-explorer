from fastapi import APIRouter
from .. import config
from ..models import ConfigModel

router = APIRouter()


@router.get("/config", response_model=ConfigModel)
def get_config():
    cfg = config.load_config()
    return ConfigModel(
        video_path_list=cfg.video_path_list,
        page_size=cfg.page_size,
        column_size=cfg.column_size,
    )


@router.put("/config", response_model=ConfigModel)
def update_config(model: ConfigModel):
    cfg = config.AppConfig(
        video_path_list=model.video_path_list,
        page_size=model.page_size,
        column_size=model.column_size,
    )
    config.save_config(cfg)
    return model
