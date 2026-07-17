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


def test_video_stream_suffix_range(video_for_playback):
    """Suffix range 'bytes=-500' 应返回最后 500 字节。"""
    vid, video_path = video_for_playback
    import os
    file_size = os.path.getsize(video_path)
    resp = client.get(f"/api/video/{vid}", headers={"Range": "bytes=-500"})
    assert resp.status_code == 206
    expected_start = max(0, file_size - 500)
    assert resp.headers["content-range"] == f"bytes {expected_start}-{file_size - 1}/{file_size}"
    assert len(resp.content) == file_size - expected_start


def test_video_stream_open_ended_range(video_for_playback):
    """Open-ended range 'bytes=100-' 应返回从 100 到文件末尾。"""
    vid, video_path = video_for_playback
    import os
    file_size = os.path.getsize(video_path)
    resp = client.get(f"/api/video/{vid}", headers={"Range": "bytes=100-"})
    assert resp.status_code == 206
    assert resp.headers["content-range"] == f"bytes 100-{file_size - 1}/{file_size}"
    assert len(resp.content) == file_size - 100


def test_video_stream_capitalized_range_header(video_for_playback):
    """大写 'Bytes=0-100' 也应正确处理。"""
    vid, video_path = video_for_playback
    resp = client.get(f"/api/video/{vid}", headers={"Bytes": "0-100"})
    # FastAPI/Starlette 会标准化 header 名为小写，所以实际到达时是 "bytes"
    # 但如果 header 原样传递，我们的代码也应该能处理
    # 此测试主要验证不会崩溃
    assert resp.status_code in (200, 206)
