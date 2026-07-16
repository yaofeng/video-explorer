"""Tests for frames API endpoints."""

import time
import shutil
from pathlib import Path

from fastapi.testclient import TestClient
from app.main import app
from app.config import AppConfig, save_config
from app.path_id import path_id

import pytest

client = TestClient(app)


@pytest.fixture
def video_with_scan(tmp_path, monkeypatch, sample_video):
    """搭建带单个测试视频的库，返回 (video_id, l2_id)。"""
    monkeypatch.setenv("DATA_PATH", str(tmp_path))
    videos_dir = tmp_path / "videos"
    l1 = videos_dir / "movies"
    l2 = l1 / "action"
    l2.mkdir(parents=True)
    video = l2 / "test.mp4"
    shutil.copy(sample_video, video)

    cfg = AppConfig(video_path_list=[str(videos_dir)], page_size=0, column_size=4)
    save_config(cfg)
    from app import paths
    paths._cache._ts = 0.0

    l2_id = path_id(str(l2.resolve()))
    vid = path_id(str(video.resolve()))
    # 触发扫描
    from app.services.scanner import Scanner
    scanner = Scanner()
    scanner.ensure_scan(str(l2))
    time.sleep(1)

    # 让 frames 路由使用同一个 scanner 实例，以便共享 _id_to_path 映射
    import app.routes.frames as frames_module
    original_scanner = frames_module.scanner
    frames_module.scanner = scanner
    yield vid, l2_id, scanner
    frames_module.scanner = original_scanner


def test_get_frame_status_not_started(video_with_scan):
    """GET /api/frames/{id} 未开始时返回 not_started。"""
    vid, _, _ = video_with_scan
    resp = client.get(f"/api/frames/{vid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "not_started"
    assert data["total"] == 20
    assert data["ready_count"] == 0
    assert len(data["frame_urls"]) == 20


def test_generate_frames_triggers_extraction(video_with_scan):
    """POST /api/frames/{id}/generate 触发抽帧。"""
    vid, _, _ = video_with_scan
    resp = client.post(f"/api/frames/{vid}/generate")
    assert resp.status_code == 202


def test_get_frame_jpeg_after_generation(video_with_scan):
    """抽帧完成后，GET /api/frames/{id}/{index} 返回 JPEG。"""
    vid, _, _ = video_with_scan
    client.post(f"/api/frames/{vid}/generate")
    for _ in range(30):
        time.sleep(0.5)
        resp = client.get(f"/api/frames/{vid}")
        if resp.json()["status"] == "ready":
            break

    resp = client.get(f"/api/frames/{vid}/0")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/jpeg"
    assert resp.content[:3] == b"\xff\xd8\xff"


def test_get_frame_jpeg_not_ready(video_with_scan):
    """帧未就绪时返回 202。"""
    vid, _, _ = video_with_scan
    resp = client.get(f"/api/frames/{vid}/0")
    assert resp.status_code == 202


def test_get_frame_jpeg_invalid_index(video_with_scan):
    """无效帧索引返回 404。"""
    vid, _, _ = video_with_scan
    resp = client.get(f"/api/frames/{vid}/99")
    assert resp.status_code == 404
