import pytest
from pathlib import Path
import subprocess
from app.scanner import Scanner, find_root
from app import config


@pytest.fixture
def video_dir(tmp_path):
    # 创建测试目录结构
    videos = tmp_path / "videos"
    l1 = videos / "movies"
    l2 = l1 / "action"
    l2.mkdir(parents=True)

    # 生成测试视频
    video_path = l2 / "test.mp4"
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi", "-i",
        "testsrc=duration=2:size=320x240:rate=30",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        str(video_path)
    ]
    subprocess.run(cmd, capture_output=True, check=True)

    return str(videos)


def test_find_root(video_dir, monkeypatch):
    monkeypatch.setenv("DATA_PATH", str(Path(video_dir).parent))
    cfg = config.AppConfig(video_path_list=[video_dir])
    monkeypatch.setattr(config, "load_config", lambda: cfg)

    video_file = Path(video_dir) / "movies" / "action" / "test.mp4"
    root = find_root(str(video_file), [video_dir])
    assert root == Path(video_dir).resolve()


def test_scanner_ensures_scan(video_dir, monkeypatch):
    monkeypatch.setenv("DATA_PATH", str(Path(video_dir).parent))
    cfg = config.AppConfig(video_path_list=[video_dir], page_size=0, column_size=4)
    monkeypatch.setattr(config, "load_config", lambda: cfg)

    scanner = Scanner()
    l2_path = str(Path(video_dir) / "movies" / "action")
    groups, scanning = scanner.ensure_scan(l2_path)
    assert len(groups) > 0
    assert scanning == False  # 小目录扫描快速完成
