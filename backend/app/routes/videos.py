from fastapi import APIRouter, HTTPException, Response
from .. import paths
from ..services.scanner import get_shared_scanner

router = APIRouter()
scanner = get_shared_scanner()


@router.get("/l2/{l2_id}/videos")
def get_videos(l2_id: str):
    """Get all video filenames under L2 directory (L1 - instant filesystem scan).
    Triggers background processing for metadata and thumbnails."""

    l2_path = paths.resolve_l2(l2_id)
    if l2_path is None:
        raise HTTPException(404, "l2 directory not found")

    groups, scanning, progress = scanner.ensure_scan(l2_path)
    return {"groups": groups, "scanning": scanning, "progress": progress}


@router.get("/thumb/{video_id}")
def get_thumb(video_id: str, size: str = "full"):
    """获取缩略图。size=small 返回压缩小图（卡片用），默认 full 返回原始 JPEG（浮层用）。
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
