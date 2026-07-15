"""Tests for thumbgen: raw frame extraction from videos."""

from app.probe import probe_video
from app.thumbgen import extract_frame, extract_frame_from_probe


def test_extract_frame_returns_jpeg(sample_video):
    """Verify extract_frame_from_probe returns valid JPEG bytes."""
    probe = probe_video(sample_video)
    result = extract_frame_from_probe(sample_video, probe)
    assert result is not None
    # JPEG magic bytes: FF D8 FF
    assert result[:3] == b"\xff\xd8\xff"


def test_extract_frame_returns_jpeg_internal_probe(sample_video):
    """Verify extract_frame (which probes internally) returns valid JPEG bytes."""
    result = extract_frame(sample_video)
    assert result is not None
    assert result[:3] == b"\xff\xd8\xff"


def test_extract_frame_returns_none_for_nonexistent():
    """Verify extract_frame returns None for a non-existent file."""
    result = extract_frame("/tmp/nonexistent_video_12345.mp4")
    assert result is None


def test_extract_frame_from_probe_none_on_invalid_cover_index(sample_video):
    """Verify extract_frame_from_probe returns None when cover_stream_index points to a non-existent stream."""
    result = extract_frame_from_probe(
        sample_video,
        {"cover_stream_index": 999, "duration": 0.0},
    )
    assert result is None


def test_extract_frame_from_probe_seek_short_video(sample_video):
    """Verify frame is extracted from a short video via midpoint seek."""
    probe = probe_video(sample_video)
    result = extract_frame_from_probe(sample_video, probe)
    assert result is not None
    assert len(result) > 100  # JPEG should be more than a few bytes
