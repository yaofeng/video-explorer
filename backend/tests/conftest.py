import pytest
import subprocess
from pathlib import Path

@pytest.fixture
def sample_video(tmp_path):
    video_path = tmp_path / "test.mp4"
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi", "-i",
        "testsrc=duration=2:size=320x240:rate=30",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        str(video_path)
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    return str(video_path)
