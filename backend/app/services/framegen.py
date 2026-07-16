"""Multi-frame extraction from video files using ffmpeg.

Extracts frames at evenly-spaced time intervals at original resolution.
Output format is JPEG.
"""

import subprocess

from .probe import probe_video

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
