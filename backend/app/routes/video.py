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

    # 处理 Range 请求（RFC 7233）
    range_header = request.headers.get("range") or request.headers.get("Range")
    if range_header:
        # 仅支持单 range；多 range 返回完整文件（浏览器几乎不使用多 range）
        try:
            # 解析 "bytes=start-end" / "bytes=start-" / "bytes=-suffix"
            if not range_header.lower().startswith("bytes="):
                raise ValueError("unsupported unit")
            range_spec = range_header[6:]  # strip "bytes="
            if "," in range_spec:
                raise ValueError("multi-range not supported")
            parts = range_spec.split("-", 1)
            if len(parts) != 2:
                raise ValueError("malformed range")

            if parts[0] == "":
                # Suffix range: bytes=-500 → last 500 bytes
                suffix_len = int(parts[1])
                if suffix_len <= 0:
                    raise ValueError("non-positive suffix")
                start = max(0, file_size - suffix_len)
                end = file_size - 1
            elif parts[1] == "":
                # Open-ended: bytes=500-
                start = int(parts[0])
                end = file_size - 1
            else:
                start = int(parts[0])
                end = int(parts[1])

            if start < 0 or start >= file_size or start > end:
                raise HTTPException(416, "Range not satisfiable",
                                    headers={"Content-Range": f"bytes */{file_size}"})
            end = min(end, file_size - 1)
            content_length = end - start + 1
        except (ValueError, IndexError):
            # 无法解析的 Range → 返回完整文件
            range_header = None

    if range_header:
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
