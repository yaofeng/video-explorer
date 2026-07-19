from fastapi.testclient import TestClient
from pathlib import Path
from app.main import app
import pytest

client = TestClient(app)


@pytest.fixture
def video_library(tmp_path, monkeypatch):
    """搭建一个带单个测试视频的 3 层目录库，返回 (root_path, l2_id)。"""
    import subprocess
    from app.config import AppConfig, save_config
    from app.path_id import path_id

    monkeypatch.setenv("DATA_PATH", str(tmp_path))
    videos = tmp_path / "videos"
    l1 = videos / "movies"
    l2 = l1 / "action"
    l2.mkdir(parents=True)

    video = l2 / "test.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i",
         "testsrc=duration=2:size=320x240:rate=30",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video)],
        capture_output=True, check=True,
    )

    cfg = AppConfig(video_path_list=[str(videos)], page_size=0, column_size=4)
    save_config(cfg)
    # 让 paths 解析器刷新缓存
    from app import paths
    paths._cache._ts = 0.0
    l2_id = path_id(str(l2.resolve()))
    return str(videos), l2_id


def test_health():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_get_config():
    resp = client.get("/api/config")
    assert resp.status_code == 200
    data = resp.json()
    assert "video_path_list" in data
    assert "page_size" in data
    assert "column_size" in data


def test_list_roots(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_PATH", str(tmp_path))
    # 更新配置添加测试路径
    from app.config import AppConfig, save_config
    cfg = AppConfig(video_path_list=[str(tmp_path / "videos")], page_size=0, column_size=4)
    save_config(cfg)

    # 创建 videos 目录，让 roots 端点能找到它
    (tmp_path / "videos").mkdir(parents=True, exist_ok=True)

    resp = client.get("/api/roots")
    assert resp.status_code == 200


def test_l1_l2_listing(video_library):
    root_path, l2_id = video_library
    from app.path_id import path_id
    root_id = path_id(str(Path(root_path).resolve()))

    # L1 列表
    resp = client.get(f"/api/roots/{root_id}/l1")
    assert resp.status_code == 200
    l1_dirs = resp.json()
    assert len(l1_dirs) == 1
    assert l1_dirs[0]["name"] == "movies"

    # L2 列表
    l1_id = l1_dirs[0]["id"]
    resp = client.get(f"/api/l1/{l1_id}/l2")
    assert resp.status_code == 200
    l2_dirs = resp.json()
    assert len(l2_dirs) == 1
    assert l2_dirs[0]["name"] == "action"


def test_get_videos_triggers_scan(video_library):
    _, l2_id = video_library
    resp = client.get(f"/api/l2/{l2_id}/videos")
    assert resp.status_code == 200
    data = resp.json()
    assert "groups" in data
    assert "scanning" in data
    assert "progress" in data

    # 新设计：首次扫描时 Phase 1 在后台运行，需要轮询等待完成
    import time
    timeout = time.time() + 5.0
    while time.time() < timeout:
        resp = client.get(f"/api/l2/{l2_id}/videos")
        data = resp.json()
        if len(data["groups"]) >= 1 and not data["scanning"]:
            break
        time.sleep(0.1)

    # 至少有一个分组、包含我们的测试视频
    assert len(data["groups"]) >= 1
    all_names = [v["file_name"] for g in data["groups"] for v in g["videos"]]
    assert "test.mp4" in all_names


def test_thumb_not_ready_returns_202(video_library):
    """刚触发扫描时缩略图通常尚未生成，应返回 202（而非 500）。"""
    _, l2_id = video_library
    client.get(f"/api/l2/{l2_id}/videos")
    from app.path_id import path_id
    vid = path_id(str(Path(video_library[0]) / "movies" / "action" / "test.mp4"))
    resp = client.get(f"/api/thumb/{vid}")
    assert resp.status_code in (200, 202)


def test_scan_status(video_library):
    _, l2_id = video_library
    client.get(f"/api/l2/{l2_id}/videos")
    resp = client.get(f"/api/scan-status?l2_id={l2_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert "scanning" in data
    assert "progress" in data
    assert "updates" in data
    assert "last_seq" in data


def test_scan_status_404_for_unknown_l2(video_library):
    resp = client.get("/api/scan-status?l2_id=does_not_exist")
    assert resp.status_code == 404


def test_parse_rules_test_bad_dir(video_library):
    """source_dir 不存在应返回 400。"""
    resp = client.post("/api/parse-rules/test", json={
        "rules": [],
        "source_dir": "/no/such/dir/xyz",
    })
    assert resp.status_code == 400


def test_tasks_endpoint(video_library):
    _, l2_id = video_library
    client.get(f"/api/l2/{l2_id}/videos")
    resp = client.get("/api/tasks")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_put_config_validation_rejects_bad_column_size(video_library):
    """column_size 越界应被 pydantic 拒绝（M13）。"""
    resp = client.put("/api/config", json={
        "video_path_list": [],
        "page_size": 0,
        "column_size": 0,  # < ge=1
    })
    assert resp.status_code == 422

    resp = client.put("/api/config", json={
        "video_path_list": [],
        "page_size": 0,
        "column_size": 999,  # > le=32
    })
    assert resp.status_code == 422


def test_unknown_api_returns_404_not_spa(video_library):
    """拼错的 API 路径应返回 JSON 404，而不是被 SPA 兜底吞成 HTML 200（M14）。"""
    resp = client.get("/api/videoss")
    assert resp.status_code == 404

