"""Tests for framegen: multi-frame extraction from videos."""

import json
from pathlib import Path

from app.services.framegen import (
    extract_frame_at, FRAME_COUNT,
    get_frames_dir, read_status, write_status,
    extract_all_frames,
)


def test_extract_frame_at_returns_jpeg(sample_video):
    """extract_frame_at 应在指定时间点提取一帧 JPEG。"""
    result = extract_frame_at(sample_video, time_sec=1.0)
    assert result is not None
    # JPEG magic bytes
    assert result[:3] == b"\xff\xd8\xff"


def test_extract_frame_at_returns_none_for_nonexistent():
    """不存在的视频文件应返回 None。"""
    result = extract_frame_at("/tmp/nonexistent_video_12345.mp4", time_sec=1.0)
    assert result is None


def test_frame_count_is_20():
    """FRAME_COUNT 常量应为 20。"""
    assert FRAME_COUNT == 20


def test_get_frames_dir_creates_directory(tmp_path):
    """get_frames_dir 应返回 {thumb_path}.frames 目录并创建。"""
    thumb_path = tmp_path / "dune.jpg"
    thumb_path.write_bytes(b"fake")
    frames_dir = get_frames_dir(thumb_path)
    assert frames_dir == tmp_path / "dune.frames"
    assert frames_dir.is_dir()


def test_read_status_returns_none_when_missing(tmp_path):
    """status.json 不存在时返回 None。"""
    assert read_status(tmp_path / "nonexistent.frames") is None


def test_write_and_read_status_roundtrip(tmp_path):
    """write_status + read_status 应可往返。"""
    frames_dir = tmp_path / "test.frames"
    frames_dir.mkdir()
    status = {"total": 20, "ready_count": 5, "generating": True, "width": 1920, "height": 1080}
    write_status(frames_dir, status)
    loaded = read_status(frames_dir)
    assert loaded == status


def test_extract_all_frames_creates_jpegs(sample_video, tmp_path):
    """extract_all_frames 应在 frames_dir 中生成 20 个 JPEG。"""
    thumb_path = tmp_path / "test.jpg"
    thumb_path.write_bytes(b"fake")
    frames_dir = get_frames_dir(thumb_path)

    result = extract_all_frames(sample_video, frames_dir, duration=2.0)
    assert result["total"] == 20
    assert result["ready_count"] == 20
    assert result["generating"] is False

    for i in range(20):
        frame_path = frames_dir / f"frame_{i:02d}.jpg"
        assert frame_path.exists(), f"frame_{i:02d}.jpg should exist"
        data = frame_path.read_bytes()
        assert data[:3] == b"\xff\xd8\xff", f"frame_{i:02d} should be JPEG"


def test_extract_all_frames_short_video(sample_video, tmp_path):
    """短于 1 秒的视频也应能抽取。"""
    thumb_path = tmp_path / "short.jpg"
    thumb_path.write_bytes(b"fake")
    frames_dir = get_frames_dir(thumb_path)

    result = extract_all_frames(sample_video, frames_dir, duration=0.5)
    assert result["total"] == 20
    assert result["ready_count"] > 0
