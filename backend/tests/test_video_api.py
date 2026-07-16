# backend/tests/test_video_api.py
"""Tests for video streaming endpoint."""

import time
import shutil
from pathlib import Path

from fastapi.testclient import TestClient
from app.main import app
from app.config import AppConfig, save_config
from app.path_id import path_id
from app.services.scanner import get_shared_scanner

import pytest

client = TestClient(app)


@pytest.fixture
def video_for_playback(tmp_path, monkeypatch, sample_video):
    """搭建带单个测试视频的库，返回 video_id。"""
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

    vid = path_id(str(video.resolve()))
    # 使用共享 scanner 触发扫描
    scanner = get_shared_scanner()
    scanner.ensure_scan(str(l2))
    time.sleep(1)
    return vid, str(video.resolve())


def test_video_stream_returns_content(video_for_playback):
    """GET /api/video/{id} 应返回视频内容。"""
    vid, video_path = video_for_playback
    resp = client.get(f"/api/video/{vid}")
    assert resp.status_code == 200
    assert "video" in resp.headers["content-type"]
    assert len(resp.content) > 0


def test_video_stream_range_request(video_for_playback):
    """Range 请求应返回 206 Partial Content。"""
    vid, video_path = video_for_playback
    resp = client.get(f"/api/video/{vid}", headers={"Range": "bytes=0-1023"})
    assert resp.status_code == 206
    assert resp.headers["content-range"].startswith("bytes 0-1023/")
    assert len(resp.content) == 1024


def test_video_stream_not_found():
    """未知 video_id 返回 404。"""
    resp = client.get("/api/video/nonexistent_id_12345")
    assert resp.status_code == 404
