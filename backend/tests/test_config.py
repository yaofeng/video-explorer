import pytest
from app.config import AppConfig, load_config, save_config, data_path, ip_whitelist
import os


def test_ip_whitelist_parses_comma_separated(monkeypatch):
    monkeypatch.setenv("IP_WHITE_LIST", "192.168.1.1,10.0.0.1")
    assert ip_whitelist() == ["192.168.1.1", "10.0.0.1"]


def test_ip_whitelist_empty(monkeypatch):
    monkeypatch.setenv("IP_WHITE_LIST", "")
    assert ip_whitelist() == []


def test_ip_whitelist_trims_spaces(monkeypatch):
    monkeypatch.setenv("IP_WHITE_LIST", " 192.168.1.1 10.0.0.1 ")
    assert ip_whitelist() == ["192.168.1.1", "10.0.0.1"]


def test_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_PATH", str(tmp_path))
    cfg = load_config()
    assert cfg.video_path_list == []
    assert cfg.page_size == 0
    assert cfg.column_size == 4


def test_save_load_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_PATH", str(tmp_path))
    cfg = AppConfig(
        video_path_list=["/videos/test"],
        page_size=20,
        column_size=3,
    )
    save_config(cfg)
    loaded = load_config()
    assert loaded.video_path_list == ["/videos/test"]
    assert loaded.page_size == 20
    assert loaded.column_size == 3
