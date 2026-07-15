import json
import os
import subprocess

def probe_video(path: str) -> dict:
    cmd = [
        "ffprobe", "-v", "error",
        "-show_streams", "-show_format",
        "-of", "json", str(path)
    ]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffprobe failed: {e.stderr}")
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"ffprobe timed out for: {path}")

    data = json.loads(out.stdout)
    streams = data.get("streams", [])

    vstream = None
    cover_index = None
    for i, s in enumerate(streams):
        if s.get("codec_type") == "video":
            disp = int(s.get("disposition", {}).get("attached_pic", 0))
            codec = s.get("codec_name", "")
            if disp == 1 or codec in ("mjpeg", "png", "jpegls"):
                if cover_index is None:
                    cover_index = i
            else:
                if vstream is None:
                    vstream = s

    if vstream is None:
        vstream = next((s for s in streams if s.get("codec_type") == "video"), {})

    width = int(vstream.get("width") or 0)
    height = int(vstream.get("height") or 0)
    codec = (vstream.get("codec_name") or "unknown").upper()
    duration = float(data.get("format", {}).get("duration") or vstream.get("duration") or 0.0)
    file_size_bytes = os.path.getsize(path)

    return {
        "codec": codec,
        "width": width,
        "height": height,
        "duration": duration,
        "cover_stream_index": cover_index,
        "resolution_str": f"{width}x{height}",
        "file_size": file_size_bytes,
    }

def resolution_label(height: int) -> str:
    if height >= 2160:
        return "4K"
    if height >= 1440:
        return "2K"
    if height >= 1080:
        return "FHD"
    if height >= 720:
        return "HD"
    if height >= 480:
        return "SD"
    if height >= 360:
        return "LD"
    return f"{height}P" if height else "Unknown"
