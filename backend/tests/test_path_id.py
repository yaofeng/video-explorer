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
