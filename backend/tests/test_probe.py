from app.services.probe import probe_video


def test_probe_video(sample_video):
    result = probe_video(sample_video)
    assert "codec" in result
    assert "width" in result
    assert "height" in result
    assert "duration" in result
    assert result["width"] == 320
    assert result["height"] == 240
    assert result["duration"] >= 1.5
    # probe.py 仅返回 ffprobe 字段；file_size 由 scanner stat，不在此返回
    assert "file_size" not in result
    assert "resolution_str" not in result
