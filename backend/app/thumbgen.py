import io
import subprocess
from PIL import Image
from .probe import probe_video

TARGET_SMALL_W = 480
SEEK_TIME = 210.0  # 3:30


def _get_placeholder(w, h):
    img = Image.new("RGB", (w, h), (0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def fit_to_16_9(img: Image.Image, target_w: int) -> bytes:
    target_h = round(target_w * 9 / 16)
    img = img.convert("RGB")
    src_w, src_h = img.size
    scale = min(target_w / src_w, target_h / src_h)
    new_w, new_h = max(1, round(src_w * scale)), max(1, round(src_h * scale))
    resized = img.resize((new_w, new_h), Image.LANCZOS)
    canvas = Image.new("RGB", (target_w, target_h), (0, 0, 0))
    canvas.paste(resized, ((target_w - new_w) // 2, (target_h - new_h) // 2))
    buf = io.BytesIO()
    canvas.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def _extract_frame(path: str, probe: dict) -> Image.Image | None:
    if probe["cover_stream_index"] is not None:
        idx = probe["cover_stream_index"]
        cmd = [
            "ffmpeg", "-v", "error",
            "-i", str(path),
            "-map", f"0:{idx}",
            "-frames:v", "1",
            "-f", "image2pipe", "-vcodec", "png", "-"
        ]
    else:
        dur = probe["duration"]
        t = SEEK_TIME if dur > SEEK_TIME else (dur / 2 if dur > 0 else 0.0)
        cmd = [
            "ffmpeg", "-v", "error",
            "-ss", f"{t:.2f}",
            "-i", str(path),
            "-frames:v", "1",
            "-f", "image2pipe", "-vcodec", "png", "-"
        ]

    out = subprocess.run(cmd, capture_output=True, timeout=120)
    if out.returncode != 0 or not out.stdout:
        return None  # 抽帧失败，返回占位图

    return Image.open(io.BytesIO(out.stdout))


def generate_thumbnails(path: str):
    """生成小图和高清图，都返回 bytes。失败时返回占位图。"""
    probe = probe_video(path)
    img = _extract_frame(path, probe)

    # 小图
    if img is not None:
        small_bytes = fit_to_16_9(img, TARGET_SMALL_W)
    else:
        small_bytes = _get_placeholder(TARGET_SMALL_W, round(TARGET_SMALL_W * 9 / 16))

    # 高清图
    if img is not None:
        target_w = min(probe["width"], img.size[0])
        full_bytes = fit_to_16_9(img, target_w)
    else:
        full_w = probe["width"] if probe["width"] > 0 else 1920
        full_bytes = _get_placeholder(full_w, round(full_w * 9 / 16))

    meta = {
        "codec": probe["codec"],
        "duration": probe["duration"],
        "width": probe["width"],
        "height": probe["height"],
        "resolution_label": None,  # 调用者填充
    }
    return meta, small_bytes, full_bytes
