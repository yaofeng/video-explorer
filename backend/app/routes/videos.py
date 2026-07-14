from fastapi import APIRouter, HTTPException, Response
from ..scanner import Scanner

router = APIRouter()
scanner = Scanner()


@router.get("/l2/{l2_id}/videos")
def get_videos(l2_id: str):
    from ..path_id import path_id
    from pathlib import Path

    from .. import config
    cfg = config.load_config()
    l2_path = None
    for root_p in cfg.video_path_list:
        root = Path(root_p).resolve()
        if not root.exists():
            continue
        for item in root.iterdir():
            if item.is_dir() and path_id(str(item)) == l2_id:
                l2_path = str(item)
                break
        if l2_path:
            break

    if l2_path is None:
        raise HTTPException(404, "未找到 l2 目录")

    groups, scanning = scanner.ensure_scan(l2_path)
    return {"groups": groups, "scanning": scanning}


@router.get("/thumb/{video_id}")
def get_thumb(video_id: str, full: int = 0):
    thumb = scanner.get_thumb(video_id, full=full == 1)
    if thumb is None:
        return Response(status_code=202, content="缩略图未就绪")
    return Response(content=thumb, media_type="image/jpeg")
