from app.probe import probe_video, resolution_label

def test_probe_video(sample_video):
    result = probe_video(sample_video)
    assert "codec" in result
    assert "width" in result
    assert "height" in result
    assert "duration" in result
    assert result["width"] == 320
    assert result["height"] == 240
    assert result["duration"] >= 1.5

def test_resolution_label():
    assert resolution_label(2160) == "4K"
    assert resolution_label(1440) == "2K"
    assert resolution_label(1080) == "FHD"
    assert resolution_label(720) == "HD"
    assert resolution_label(480) == "SD"
    assert resolution_label(360) == "LD"
    assert resolution_label(0) == "Unknown"
