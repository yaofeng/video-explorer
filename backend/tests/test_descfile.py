from app.descfile import write_desc, read_desc

def test_write_read_roundtrip(tmp_path):
    desc_path = tmp_path / "test.desc"
    desc = {
        "file_name": "test.mp4",
        "codec": "H264",
        "duration": 123.4,
        "width": 1920,
        "height": 1080,
        "resolution_label": "FHD",
    }
    small_thumb = b"fake_jpeg_data_small"
    full_thumb = b"fake_jpeg_data_full"

    write_desc(str(desc_path), desc, small_thumb, full_thumb)

    loaded_desc, loaded_small, loaded_full = read_desc(str(desc_path))
    assert loaded_desc == desc
    assert loaded_small == small_thumb
    assert loaded_full == full_thumb


def test_bad_magic(tmp_path):
    bad_path = tmp_path / "bad.desc"
    with open(bad_path, "wb") as f:
        f.write(b"BADM" + b"\x00" * 32)

    try:
        read_desc(str(bad_path))
        assert False, "should raise ValueError"
    except ValueError as e:
        assert "bad magic" in str(e)
