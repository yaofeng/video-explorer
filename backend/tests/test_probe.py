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
    assert isinstance(result["file_size"], int)
    assert result["file_size"] >= 0  # 小视频可能不足 1MB，整数除法结果为 0
    # probe.py 不再返回 resolution_str（由前端计算）
    assert "resolution_str" not in result
