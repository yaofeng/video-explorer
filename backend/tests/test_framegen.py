"""Tests for framegen: multi-frame extraction from videos."""

import json
from pathlib import Path

from app.services.framegen import extract_frame_at, FRAME_COUNT


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
