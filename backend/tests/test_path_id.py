from app.path_id import path_id


def test_same_path_same_id():
    id1 = path_id("/videos/test/file.mp4")
    id2 = path_id("/videos/test/file.mp4")
    assert id1 == id2
    assert len(id1) == 16


def test_different_path_different_id():
    id1 = path_id("/videos/test/file1.mp4")
    id2 = path_id("/videos/test/file2.mp4")
    assert id1 != id2
    assert len(id1) == 16
    assert len(id2) == 16


def test_path_id_with_path_object():
    from pathlib import Path
    id1 = path_id(Path("/videos/test/file.mp4"))
    id2 = path_id("/videos/test/file.mp4")
    assert id1 == id2
    assert len(id1) == 16


def test_relative_path_raises():
    try:
        path_id("relative/path.mp4")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "relative" in str(e).lower()
