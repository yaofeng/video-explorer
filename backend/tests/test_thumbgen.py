"""Tests for thumbgen: raw frame extraction from videos."""

from app.probe import probe_video
from app.thumbgen import extract_frame, extract_frame_from_probe


def test_extract_frame_returns_png(sample_video):
    """Verify extract_frame_from_probe returns valid PNG bytes."""
    probe = probe_video(sample_video)
    result = extract_frame_from_probe(sample_video, probe)
    assert result is not None
    assert result[:8] == b"\x89PNG\r\n\x1a\n"  # PNG magic bytes


def test_extract_frame_from_probe_returns_png(sample_video):
    """Verify extract_frame (which probes internally) returns valid PNG bytes."""
    result = extract_frame(sample_video)
    assert result is not None
    assert result[:8] == b"\x89PNG\r\n\x1a\n"


def test_extract_frame_returns_none_for_nonexistent():
    """Verify extract_frame returns None for a non-existent file."""
    result = extract_frame("/tmp/nonexistent_video_12345.mp4")
    assert result is None


def test_extract_frame_from_probe_none_on_bad_probe(sample_video):
    """Verify extract_frame_from_probe returns None when probe data is missing required fields."""
    result = extract_frame_from_probe(sample_video, {})
    assert result is None


def test_extract_frame_from_probe_seek_short_video(sample_video):
    """Verify frame is extracted from a short video via midpoint seek."""
    probe = probe_video(sample_video)
    result = extract_frame_from_probe(sample_video, probe)
    assert result is not None
    assert len(result) > 100  # PNG should be more than a few bytes
