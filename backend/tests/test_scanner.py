import pytest
import threading
import time
from pathlib import Path
import subprocess
from app.services.scanner import Scanner, find_root
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


def _setup(video_dir, monkeypatch):
    monkeypatch.setenv("DATA_PATH", str(Path(video_dir).parent))
    cfg = config.AppConfig(video_path_list=[video_dir], page_size=0, column_size=4)
    monkeypatch.setattr(config, "load_config", lambda: cfg)


def test_find_root(video_dir, monkeypatch):
    monkeypatch.setenv("DATA_PATH", str(Path(video_dir).parent))
    cfg = config.AppConfig(video_path_list=[video_dir])
    monkeypatch.setattr(config, "load_config", lambda: cfg)

    video_file = Path(video_dir) / "movies" / "action" / "test.mp4"
    root = find_root(str(video_file), [video_dir])
    assert root == Path(video_dir).resolve()


def test_scanner_ensures_scan(video_dir, monkeypatch):
    _setup(video_dir, monkeypatch)

    scanner = Scanner()
    l2_path = str(Path(video_dir) / "movies" / "action")
    groups, scanning, progress = scanner.ensure_scan(l2_path)

    # 新设计：首次扫描时 Phase 1 在后台运行，需要等待完成
    # 轮询等待扫描完成（最多 5 秒）
    import time
    timeout = time.time() + 5.0
    while time.time() < timeout:
        state = scanner._get_l2_state(l2_path)
        with state.lock:
            if not state.scanning and len(state.videos) > 0:
                break
        time.sleep(0.1)

    # 重新获取结果
    groups = scanner._build_groups(scanner._get_l2_state(l2_path))
    progress = scanner._build_progress(scanner._get_l2_state(l2_path))
    state = scanner._get_l2_state(l2_path)

    assert len(groups) > 0
    assert state.scanning == False  # 扫描完成
    assert progress["total"] >= 1


def test_status_does_not_deadlock(video_dir, monkeypatch):
    """回归测试：status() 内部不再调用 _build_progress 造成重入死锁。"""
    _setup(video_dir, monkeypatch)

    scanner = Scanner()
    l2_path = str(Path(video_dir) / "movies" / "action")
    scanner.ensure_scan(l2_path)

    # status() 必须在限定时间内返回，否则视为死锁
    result = {}
    def call_status():
        result["status"] = scanner.status(l2_path)

    t = threading.Thread(target=call_status)
    t.start()
    t.join(timeout=5)
    assert not t.is_alive(), "status() 死锁（5s 内未返回）"
    assert "status" in result
    assert "progress" in result["status"]


def test_ensure_scan_revisit_does_not_deadlock(video_dir, monkeypatch):
    """回归测试：回访正在扫描的目录不应死锁（非重入锁问题）。"""
    _setup(video_dir, monkeypatch)

    scanner = Scanner()
    l2_path = str(Path(video_dir) / "movies" / "action")

    # 第一次访问启动扫描
    scanner.ensure_scan(l2_path)
    # 立即再次访问（可能仍在扫描）——不应死锁
    result = {}
    def revisit():
        result["r"] = scanner.ensure_scan(l2_path)

    t = threading.Thread(target=revisit)
    t.start()
    t.join(timeout=5)
    assert not t.is_alive(), "ensure_scan() 回访死锁（5s 内未返回）"
    assert "r" in result


def test_concurrent_status_and_ensure_scan(video_dir, monkeypatch):
    """并发调用 status 和 ensure_scan 不应死锁或崩溃。"""
    _setup(video_dir, monkeypatch)

    scanner = Scanner()
    l2_path = str(Path(video_dir) / "movies" / "action")
    scanner.ensure_scan(l2_path)

    errors = []
    def worker(fn):
        try:
            for _ in range(10):
                fn()
        except Exception as e:
            errors.append(e)

    threads = [
        threading.Thread(target=worker, args=(lambda: scanner.status(l2_path),)),
        threading.Thread(target=worker, args=(lambda: scanner.status(l2_path),)),
        threading.Thread(target=worker, args=(lambda: scanner.ensure_scan(l2_path),)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)
        assert not t.is_alive(), "并发调用死锁"

    assert not errors, f"并发调用产生异常: {errors}"

