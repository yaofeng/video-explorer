"""Tests for Scanner frame-related methods."""

import time
from pathlib import Path
from unittest.mock import patch

from app.services.scanner import Scanner


def test_scanner_get_frames_dir_returns_none_for_unknown_video():
    """未知 video_id 应返回 None。"""
    scanner = Scanner()
    result = scanner.get_frames_dir("nonexistent_video_id")
    assert result is None


def test_scanner_get_frame_status_not_started(sample_video, tmp_path, monkeypatch):
    """未开始抽帧时，get_frame_status 应返回 not_started。"""
    from app.config import AppConfig, save_config
    from app.path_id import path_id

    monkeypatch.setenv("DATA_PATH", str(tmp_path))

    videos_dir = tmp_path / "videos"
    l1 = videos_dir / "movies"
    l2 = l1 / "action"
    l2.mkdir(parents=True)
    import shutil
    video_in_l2 = l2 / "test.mp4"
    shutil.copy(sample_video, video_in_l2)

    cfg = AppConfig(video_path_list=[str(videos_dir)], page_size=0, column_size=4)
    save_config(cfg)

    scanner = Scanner()
    scanner.ensure_scan(str(l2))
    time.sleep(1)

    vid = path_id(str(video_in_l2.resolve()))
    result = scanner.get_frame_status(vid)
    assert result is not None
    assert result["status"] == "not_started"
    assert result["total"] == 20
    assert result["ready_count"] == 0


def test_scanner_generate_frames(sample_video, tmp_path, monkeypatch):
    """generate_frames 应触发异步抽帧并最终完成。"""
    from app.config import AppConfig, save_config
    from app.path_id import path_id

    monkeypatch.setenv("DATA_PATH", str(tmp_path))

    videos_dir = tmp_path / "videos"
    l1 = videos_dir / "movies"
    l2 = l1 / "action"
    l2.mkdir(parents=True)
    import shutil
    video_in_l2 = l2 / "test.mp4"
    shutil.copy(sample_video, video_in_l2)

    cfg = AppConfig(video_path_list=[str(videos_dir)], page_size=0, column_size=4)
    save_config(cfg)

    scanner = Scanner()
    scanner.ensure_scan(str(l2))
    time.sleep(1)

    vid = path_id(str(video_in_l2.resolve()))
    scanner.generate_frames(vid)
    time.sleep(5)

    status = scanner.get_frame_status(vid)
    assert status["status"] == "ready"
    assert status["ready_count"] == 20
