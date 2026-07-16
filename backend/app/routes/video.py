# backend/app/routes/video.py
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from ..services.scanner import get_shared_scanner, find_root
from .. import config

router = APIRouter()
scanner = get_shared_scanner()

VIDEO_MIME = {
    ".mp4": "video/mp4",
    ".mkv": "video/x-matroska",
    ".mov": "video/quicktime",
    ".avi": "video/x-msvideo",
    ".webm": "video/webm",
    ".m4v": "video/mp4",
    ".flv": "video/x-flv",
    ".ts": "video/mp2t",
    ".wmv": "video/x-ms-wmv",
    ".mpg": "video/mpeg",
    ".mpeg": "video/mpeg",
    ".3gp": "video/3gpp",
    ".rm": "video/vnd.rn-realvideo",
    ".rmvb": "video/vnd.rn-realvideo",
}

CHUNK_SIZE = 64 * 1024  # 64KB


def _resolve_video_path(video_id: str) -> Path | None:
    """通过 scanner 的 _id_to_path 解析 video_id → 绝对路径。"""
    with scanner._lock:
        return scanner._id_to_path.get(video_id)


@router.get("/video/{video_id}")
async def stream_video(video_id: str, request: Request):
    """流式返回视频文件，支持 HTTP Range 请求。"""
    video_path = _resolve_video_path(video_id)
    if video_path is None:
        raise HTTPException(404, "video not found")

    path = Path(video_path)
    if not path.exists() or not path.is_file():
        raise HTTPException(404, "video file not found")

    # 安全校验：确认路径在 video_path_list 内
    cfg = config.load_config()
    root = find_root(str(path), cfg.video_path_list)
    if root is None:
        raise HTTPException(403, "access denied")

    file_size = path.stat().st_size
    ext = path.suffix.lower()
    content_type = VIDEO_MIME.get(ext, "application/octet-stream")

    # 处理 Range 请求
    range_header = request.headers.get("range")
    if range_header:
        range_spec = range_header.replace("bytes=", "")
        parts = range_spec.split("-")
        start = int(parts[0]) if parts[0] else 0
        end = int(parts[1]) if parts[1] else file_size - 1
        end = min(end, file_size - 1)
        content_length = end - start + 1

        def iter_range():
            with open(path, "rb") as f:
                f.seek(start)
                remaining = content_length
                while remaining > 0:
                    chunk = f.read(min(CHUNK_SIZE, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        return StreamingResponse(
            iter_range(),
            status_code=206,
            media_type=content_type,
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(content_length),
                "Cache-Control": "private, max-age=3600",
            },
        )

    # 完整文件
    def iter_full():
        with open(path, "rb") as f:
            while True:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break
                yield chunk

    return StreamingResponse(
        iter_full(),
        media_type=content_type,
        headers={
            "Accept-Ranges": "bytes",
            "Content-Length": str(file_size),
            "Cache-Control": "private, max-age=3600",
        },
    )
