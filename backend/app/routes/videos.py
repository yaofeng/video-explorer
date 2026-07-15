from fastapi import APIRouter, HTTPException, Response
from pathlib import Path
from .. import config, path_id
from ..scanner import Scanner

router = APIRouter()
scanner = Scanner()


@router.get("/l2/{l2_id}/videos")
def get_videos(l2_id: str):
    """Get all video filenames under L2 directory (L1 - instant filesystem scan).
    Triggers background processing for metadata and thumbnails."""

    l2_path = _find_l2_path(l2_id)
    if l2_path is None:
        raise HTTPException(404, "l2 directory not found")

    groups, scanning, progress = scanner.ensure_scan(l2_path)
    return {"groups": groups, "scanning": scanning, "progress": progress}


@router.get("/thumb/{video_id}")
def get_thumb(video_id: str, size: str = "full"):
    """获取缩略图。size=small 返回压缩小图（卡片用），默认 full 返回原始 PNG（浮层用）。
    未就绪返回 202。响应带长缓存头供浏览器复用。"""
    small = size == "small"
    result = scanner.get_thumb(video_id, small=small)
    if result is None:
        return Response(status_code=202, content="thumbnail not ready")
    media_type, thumb_bytes = result
    return Response(
        content=thumb_bytes,
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )


def _find_l2_path(l2_id: str) -> str | None:
    """Helper: resolve l2_id to absolute path."""
    cfg = config.load_config()
    for root_p in cfg.video_path_list:
        root = Path(root_p).resolve()
        if not root.exists():
            continue
        for l1_item in root.iterdir():
            if not l1_item.is_dir():
                continue
            for l2_item in l1_item.iterdir():
                if l2_item.is_dir() and path_id.path_id(str(l2_item)) == l2_id:
                    return str(l2_item)
    return None
