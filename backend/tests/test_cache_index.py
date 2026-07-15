import yaml
from pathlib import Path

from app.cache_index import (
    root_cache_dir,
    video_cache_path,
    load_index,
    save_index,
    update_video_in_index,
    remove_video_from_index,
    get_thumb_path,
)


def test_root_cache_dir(monkeypatch):
    monkeypatch.setattr("app.cache_index.data_path", lambda: Path("/tmp/test_data"))
    monkeypatch.setattr("app.cache_index.path_id", lambda p: "abcdef1234567890")
    result = root_cache_dir("/media/videos/Movies")
    expected = Path("/tmp/test_data/cache/Movies-abcd")
    assert result == expected, f"Expected {expected}, got {result}"


def test_root_cache_dir_first_four_chars_used(monkeypatch):
    monkeypatch.setattr("app.cache_index.data_path", lambda: Path("/tmp/test_data"))
    monkeypatch.setattr("app.cache_index.path_id", lambda p: "9876543210abcdef")
    result = root_cache_dir("/some/root")
    expected = Path("/tmp/test_data/cache/root-9876")
    assert result == expected


def test_video_cache_path(monkeypatch, tmp_path):
    monkeypatch.setattr("app.cache_index.data_path", lambda: tmp_path)
    monkeypatch.setattr("app.cache_index.path_id", lambda p: "abcdef1234567890")
    root = "/media/videos"
    video = "/media/videos/movies/dune.mkv"
    index_path, thumb_path = video_cache_path(root, video)
    expected_index = tmp_path / "cache" / "videos-abcd" / "movies" / "index.yaml"
    expected_thumb = tmp_path / "cache" / "videos-abcd" / "movies" / "dune.mkv.png"
    assert index_path == expected_index, f"Expected {expected_index}, got {index_path}"
    assert thumb_path == expected_thumb, f"Expected {expected_thumb}, got {thumb_path}"
    assert index_path.parent.exists(), "Parent directory should have been created"
    assert thumb_path.parent == index_path.parent


def test_video_cache_path_root_level_video(monkeypatch, tmp_path):
    monkeypatch.setattr("app.cache_index.data_path", lambda: tmp_path)
    monkeypatch.setattr("app.cache_index.path_id", lambda p: "abcdef1234567890")
    root = "/media/videos"
    video = "/media/videos/dune.mkv"
    index_path, thumb_path = video_cache_path(root, video)
    expected_index = tmp_path / "cache" / "videos-abcd" / "index.yaml"
    expected_thumb = tmp_path / "cache" / "videos-abcd" / "dune.mkv.png"
    assert index_path == expected_index
    assert thumb_path == expected_thumb


def test_round_trip_save_load(tmp_path):
    index_path = tmp_path / "index.yaml"
    videos = [
        {
            "file_name": "dune.mkv",
            "file_size_gb": 8.0,
            "resolution": "3840x2160",
            "codec": "HEVC",
        }
    ]
    save_index(index_path, videos)
    assert index_path.exists()
    loaded = load_index(index_path)
    assert loaded == videos


def test_save_load_empty_list(tmp_path):
    index_path = tmp_path / "index.yaml"
    save_index(index_path, [])
    loaded = load_index(index_path)
    assert loaded == []


def test_load_nonexistent_index(tmp_path):
    index_path = tmp_path / "nonexistent_subdir" / "index.yaml"
    assert load_index(index_path) == []


def test_load_invalid_yaml_returns_empty(tmp_path):
    index_path = tmp_path / "index.yaml"
    index_path.write_text("not: valid: yaml: [[[")
    result = load_index(index_path)
    assert result == []


def test_load_missing_videos_key_returns_empty(tmp_path):
    index_path = tmp_path / "index.yaml"
    save_index(index_path, [])
    # Manually write yaml without videos key
    with open(index_path, "w") as f:
        yaml.safe_dump({"something_else": []}, f)
    result = load_index(index_path)
    assert result == []


def test_update_video_in_index_add(monkeypatch, tmp_path):
    monkeypatch.setattr("app.cache_index.data_path", lambda: tmp_path)
    index_path = tmp_path / "index.yaml"
    video = {"file_name": "dune.mkv", "codec": "HEVC"}
    update_video_in_index(index_path, video)
    loaded = load_index(index_path)
    assert loaded == [video]


def test_update_video_in_index_replace_existing(monkeypatch, tmp_path):
    monkeypatch.setattr("app.cache_index.data_path", lambda: tmp_path)
    index_path = tmp_path / "index.yaml"
    v1 = {"file_name": "dune.mkv", "codec": "HEVC", "resolution": "3840x2160"}
    v2 = {"file_name": "dune.mkv", "codec": "H264", "resolution": "1920x1080"}
    update_video_in_index(index_path, v1)
    update_video_in_index(index_path, v2)
    loaded = load_index(index_path)
    assert len(loaded) == 1
    assert loaded[0] == v2


def test_update_video_in_index_preserves_other_entries(monkeypatch, tmp_path):
    monkeypatch.setattr("app.cache_index.data_path", lambda: tmp_path)
    index_path = tmp_path / "index.yaml"
    v1 = {"file_name": "dune.mkv"}
    v2 = {"file_name": "other.mkv"}
    update_video_in_index(index_path, v1)
    update_video_in_index(index_path, v2)
    loaded = load_index(index_path)
    assert len(loaded) == 2


def test_remove_video_from_index(tmp_path):
    index_path = tmp_path / "index.yaml"
    v1 = {"file_name": "dune.mkv", "codec": "HEVC"}
    v2 = {"file_name": "other.mkv", "codec": "H264"}
    save_index(index_path, [v1, v2])
    remove_video_from_index(index_path, "dune.mkv")
    loaded = load_index(index_path)
    assert len(loaded) == 1
    assert loaded[0]["file_name"] == "other.mkv"


def test_remove_video_from_index_not_found(tmp_path):
    index_path = tmp_path / "index.yaml"
    v = {"file_name": "dune.mkv"}
    save_index(index_path, [v])
    remove_video_from_index(index_path, "nonexistent.mkv")
    loaded = load_index(index_path)
    assert len(loaded) == 1
    assert loaded[0]["file_name"] == "dune.mkv"


def test_remove_video_from_index_empty(tmp_path):
    index_path = tmp_path / "index.yaml"
    save_index(index_path, [])
    remove_video_from_index(index_path, "dune.mkv")
    assert load_index(index_path) == []


def test_resolution_string_stored_correctly(tmp_path):
    """Verify the resolution field is correctly stored as 'WxH' string."""
    index_path = tmp_path / "index.yaml"
    video = {
        "file_name": "test.mkv",
        "width": 3840,
        "height": 2160,
        "resolution": "3840x2160",
    }
    save_index(index_path, [video])
    loaded = load_index(index_path)
    assert loaded[0]["resolution"] == "3840x2160"
    # Verify the raw YAML contains the resolution string
    with open(index_path) as f:
        raw = f.read()
    assert "3840x2160" in raw


def test_resolution_from_width_height_fields(monkeypatch, tmp_path):
    """Test that when a caller provides width/height, the resolution
    string is correctly formatted when saving and loading."""
    monkeypatch.setattr("app.cache_index.data_path", lambda: tmp_path)
    index_path = tmp_path / "index.yaml"
    width, height = 1920, 1080
    video = {
        "file_name": "video.mp4",
        "width": width,
        "height": height,
        "resolution": f"{width}x{height}",
    }
    save_index(index_path, [video])
    loaded = load_index(index_path)
    assert loaded[0]["resolution"] == "1920x1080"


def test_get_thumb_path_found(tmp_path):
    index_path = tmp_path / "index.yaml"
    thumb = tmp_path / "movie.mkv.png"
    thumb.write_text("dummy")
    video = {"file_name": "movie.mkv", "thumb_file": "movie.mkv.png"}
    save_index(index_path, [video])
    result = get_thumb_path(index_path, "movie.mkv")
    assert result == thumb


def test_get_thumb_path_file_missing(tmp_path):
    index_path = tmp_path / "index.yaml"
    video = {"file_name": "movie.mkv", "thumb_file": "movie.mkv.png"}
    save_index(index_path, [video])
    # thumb file doesn't exist on disk
    result = get_thumb_path(index_path, "movie.mkv")
    assert result is None


def test_get_thumb_path_no_thumb_file_field(tmp_path):
    index_path = tmp_path / "index.yaml"
    video = {"file_name": "movie.mkv"}
    save_index(index_path, [video])
    result = get_thumb_path(index_path, "movie.mkv")
    assert result is None


def test_get_thumb_path_no_entry(tmp_path):
    index_path = tmp_path / "index.yaml"
    save_index(index_path, [])
    result = get_thumb_path(index_path, "missing.mkv")
    assert result is None


def test_save_index_preserves_field_order(tmp_path):
    """Verify that yaml.safe_dump with sort_keys=False preserves insertion order."""
    index_path = tmp_path / "index.yaml"
    video = {
        "file_name": "dune.mkv",
        "file_size_gb": 8.0,
        "resolution": "3840x2160",
        "codec": "HEVC",
        "create_time": 1720900000,
        "modify_time": 1720900000.0,
        "thumb_file": "dune.mkv.png",
    }
    save_index(index_path, [video])
    with open(index_path) as f:
        lines = [l.strip() for l in f if l.strip()]
    # The first field is prefixed with "- " in YAML block sequence; strip it
    key_lines = [l.lstrip("- ") for l in lines]
    idx = key_lines.index("file_name: dune.mkv")
    file_size_idx = key_lines.index("file_size_gb: 8.0")
    codec_idx = key_lines.index("codec: HEVC")
    thumb_idx = key_lines.index("thumb_file: dune.mkv.png")
    assert file_size_idx > idx, "file_size_gb should come after file_name"
    assert codec_idx > file_size_idx, "codec should come after file_size_gb"
    assert thumb_idx > codec_idx, "thumb_file should come after codec"
