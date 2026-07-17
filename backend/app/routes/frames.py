from fastapi import APIRouter, HTTPException, Response
from ..services.scanner import get_shared_scanner

router = APIRouter()
scanner = get_shared_scanner()


@router.get("/frames/{video_id}")
def get_frame_status(video_id: str):
    """返回 20 帧就绪状态和每帧 URL。"""
    result = scanner.get_frame_status(video_id)
    if result is None:
        raise HTTPException(404, "video not found")
    return result


@router.post("/frames/{video_id}/generate")
def generate_frames(video_id: str):
    """触发批量抽帧（异步）。"""
    started = scanner.generate_frames(video_id)
    if not started:
        status = scanner.get_frame_status(video_id)
        if status and status["status"] == "ready":
            return {"status": "already_done"}
        return Response(status_code=202, content="generation in progress")
    return Response(status_code=202, content="generation started")


@router.get("/frames/{video_id}/{frame_index:int}")
def get_frame_jpeg(video_id: str, frame_index: int):
    """返回单帧 JPEG。"""
    if frame_index < 0 or frame_index >= 20:
        raise HTTPException(404, "frame index out of range")
    jpeg_bytes = scanner.get_frame_jpeg(video_id, frame_index)
    if jpeg_bytes is None:
        return Response(status_code=202, content="frame not ready")
    return Response(
        content=jpeg_bytes,
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=86400"},
    )
