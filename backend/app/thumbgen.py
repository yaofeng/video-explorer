"""Raw frame extraction from video files using ffmpeg.

Returns raw PNG bytes with no server-side image processing
(resizing, aspect-ratio adjustment, or letterboxing).
"""

import subprocess

from .probe import probe_video

SEEK_TIME = 210.0  # 3:30


def _extract_frame(path: str, probe: dict) -> bytes | None:
    """Run ffmpeg to extract a single frame, returning raw PNG bytes.

    Prioritises embedded cover streams, then SEEK_TIME seek,
    then video midpoint for short clips.
    """
    if probe.get("cover_stream_index") is not None:
        idx = probe["cover_stream_index"]
        cmd = [
            "ffmpeg", "-v", "error",
            "-i", str(path),
            "-map", f"0:{idx}",
            "-frames:v", "1",
            "-f", "image2pipe", "-vcodec", "png", "-",
        ]
    else:
        dur = probe.get("duration", 0.0)
        t = SEEK_TIME if dur > SEEK_TIME else (dur / 2 if dur > 0 else 0.0)
        cmd = [
            "ffmpeg", "-v", "error",
            "-ss", f"{t:.2f}",
            "-i", str(path),
            "-frames:v", "1",
            "-f", "image2pipe", "-vcodec", "png", "-",
        ]

    try:
        out = subprocess.run(cmd, capture_output=True, timeout=120)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None

    if out.returncode != 0 or not out.stdout:
        return None
    return out.stdout


def extract_frame(path: str) -> bytes | None:
    """Extract a single raw PNG frame from *path*.

    Probes the video internally to determine cover-stream vs seek strategy.
    Returns ``None`` when ffprobe or ffmpeg fails.
    """
    try:
        probe = probe_video(path)
    except Exception:
        return None
    return _extract_frame(path, probe)


def extract_frame_from_probe(path: str, probe: dict) -> bytes | None:
    """Extract a single raw PNG frame using pre-computed *probe* data.

    *probe* must contain ``cover_stream_index`` (int | None) and
    ``duration`` (float).  Returns ``None`` when ffmpeg fails.
    """
    return _extract_frame(path, probe)
