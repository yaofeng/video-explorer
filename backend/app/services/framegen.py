"""Multi-frame extraction from video files using ffmpeg.

Extracts frames at evenly-spaced time intervals at original resolution.
Output format is JPEG.
"""

import json
import logging
import subprocess
from pathlib import Path

from .probe import probe_video

logger = logging.getLogger(__name__)

FRAME_COUNT = 20


def compute_frame_times(duration: float, count: int = FRAME_COUNT) -> list[float]:
    """计算 N 帧的等间隔时间点。

    t_i = duration * (i + 0.5) / count，避免首尾黑帧。
    短于 count 秒的视频仍均匀分布。
    """
    if duration <= 0:
        return [0.0] * count
    return [duration * (i + 0.5) / count for i in range(count)]


def extract_frame_at(path: str, time_sec: float) -> bytes | None:
    """在指定时间点提取单帧 JPEG。

    返回 JPEG bytes，失败返回 None。
    """
    cmd = [
        "ffmpeg", "-v", "error",
        "-ss", f"{time_sec:.3f}",
        "-i", str(path),
        "-frames:v", "1",
        "-f", "image2pipe", "-vcodec", "mjpeg", "-",
    ]
    try:
        out = subprocess.run(cmd, capture_output=True, timeout=120)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None

    if out.returncode != 0 or not out.stdout:
        return None
    return out.stdout


def get_frames_dir(thumb_path: Path) -> Path:
    """返回帧目录路径：{thumb_stem}.frames/。自动创建。"""
    frames_dir = thumb_path.with_suffix(".frames")
    frames_dir.mkdir(parents=True, exist_ok=True)
    return frames_dir


def _status_path(frames_dir: Path) -> Path:
    return frames_dir / "status.json"


def read_status(frames_dir: Path) -> dict | None:
    """读取 status.json。不存在或损坏时返回 None。"""
    sp = _status_path(frames_dir)
    if not sp.exists():
        return None
    try:
        return json.loads(sp.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def write_status(frames_dir: Path, status: dict) -> None:
    """原子写 status.json。"""
    sp = _status_path(frames_dir)
    sp.write_text(json.dumps(status, ensure_ascii=False), encoding="utf-8")


def _count_ready_frames(frames_dir: Path) -> int:
    """统计 frames_dir 中已存在的 frame_XX.jpg 文件数。"""
    count = 0
    for i in range(FRAME_COUNT):
        if (frames_dir / f"frame_{i:02d}.jpg").exists():
            count += 1
    return count


def extract_all_frames(
    video_path: str,
    frames_dir: Path,
    duration: float,
    width: int = 0,
    height: int = 0,
) -> dict:
    """批量抽取 FRAME_COUNT 帧，写入 frames_dir。

    逐帧写入，每完成一帧更新 status.json 的 ready_count。
    返回最终 status dict。
    """
    frame_times = compute_frame_times(duration, FRAME_COUNT)
    frames_dir.mkdir(parents=True, exist_ok=True)

    status = {
        "total": FRAME_COUNT,
        "ready_count": 0,
        "generating": True,
        "width": width,
        "height": height,
    }
    write_status(frames_dir, status)

    for i, t in enumerate(frame_times):
        frame_path = frames_dir / f"frame_{i:02d}.jpg"
        if frame_path.exists():
            status["ready_count"] = _count_ready_frames(frames_dir)
            write_status(frames_dir, status)
            continue

        jpeg_bytes = extract_frame_at(video_path, t)
        if jpeg_bytes:
            frame_path.write_bytes(jpeg_bytes)

        status["ready_count"] = _count_ready_frames(frames_dir)
        write_status(frames_dir, status)

    status["generating"] = False
    write_status(frames_dir, status)
    return status
