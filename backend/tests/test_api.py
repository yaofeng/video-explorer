from fastapi.testclient import TestClient
from app.main import app
import pytest

client = TestClient(app)


def test_health():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_get_config():
    resp = client.get("/api/config")
    assert resp.status_code == 200
    data = resp.json()
    assert "video_path_list" in data
    assert "page_size" in data
    assert "column_size" in data


def test_list_roots(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_PATH", str(tmp_path))
    # 更新配置添加测试路径
    from app.config import AppConfig, save_config
    cfg = AppConfig(video_path_list=[str(tmp_path / "videos")], page_size=0, column_size=4)
    save_config(cfg)

    # 创建 videos 目录，让 roots 端点能找到它
    (tmp_path / "videos").mkdir(parents=True, exist_ok=True)

    resp = client.get("/api/roots")
    assert resp.status_code == 200
