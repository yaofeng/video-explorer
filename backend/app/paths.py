"""id → 路径 解析的集中实现（M6/M7/M8）。

之前 dirs.py / videos.py / scan.py 各有一份遍历文件系统的解析逻辑，
且每次请求都全量 walk + stat，对 NAS 极不友好。这里统一为带 TTL 缓存的
解析器：在同一 TTL 窗口内重复请求命中内存，扫描期间的 2s 轮询不再反复冲刷。
"""
from __future__ import annotations

import time
from pathlib import Path

from . import config, path_id

# 解析结果缓存 TTL（秒）。目录结构变化后最多 TTL 秒生效。
_RESOLVE_TTL = 3.0

# 应过滤掉的 NAS/系统目录前缀（Synology @eaDir/@Recycle、macOS .DS_Store 等，M8）
_HIDDEN_PREFIXES = (".", "@")


def _is_hidden(name: str) -> bool:
    return name.startswith(_HIDDEN_PREFIXES)


def _safe_iter_dirs(parent: Path) -> list[Path]:
    """列出 parent 下的子目录，跳过隐藏/特殊目录并吞掉 IO 错误（M8）。"""
    try:
        it = list(parent.iterdir())
    except (OSError, PermissionError):
        return []
    out = []
    for item in it:
        if _is_hidden(item.name):
            continue
        try:
            if item.is_dir():
                out.append(item)
        except OSError:
            continue
    return out


class _ResolveCache:
    """root_id / l1_id / l2_id → path 的带 TTL 缓存。"""

    def __init__(self) -> None:
        self._ts = 0.0
        self._roots: dict[str, str] = {}
        self._l1: dict[str, str] = {}
        self._l2: dict[str, str] = {}

    def _maybe_refresh(self) -> None:
        if time.time() - self._ts < _RESOLVE_TTL:
            return
        roots: dict[str, str] = {}
        l1: dict[str, str] = {}
        l2: dict[str, str] = {}
        cfg = config.load_config()
        for root_p in cfg.video_path_list:
            rp = Path(root_p).resolve()
            if not rp.exists() or not rp.is_dir():
                continue
            roots[path_id.path_id(str(rp))] = str(rp)
            for l1_item in _safe_iter_dirs(rp):
                l1[path_id.path_id(str(l1_item))] = str(l1_item)
                for l2_item in _safe_iter_dirs(l1_item):
                    l2[path_id.path_id(str(l2_item))] = str(l2_item)
        self._roots, self._l1, self._l2 = roots, l1, l2
        self._ts = time.time()

    def root(self, root_id: str) -> str | None:
        self._maybe_refresh()
        return self._roots.get(root_id)

    def l1(self, l1_id: str) -> str | None:
        self._maybe_refresh()
        return self._l1.get(l1_id)

    def l2(self, l2_id: str) -> str | None:
        self._maybe_refresh()
        return self._l2.get(l2_id)

    def list_l1_under(self, root_id: str) -> list[Path]:
        """列出某 root 下的 L1 目录（带过滤），用于 dirs.list_l1。"""
        self._maybe_refresh()
        root = self._roots.get(root_id)
        if root is None:
            return []
        return _safe_iter_dirs(Path(root))

    def list_l2_under(self, l1_id: str) -> list[Path]:
        self._maybe_refresh()
        l1 = self._l1.get(l1_id)
        if l1 is None:
            return []
        return _safe_iter_dirs(Path(l1))

    def roots(self) -> list[str]:
        self._maybe_refresh()
        return list(self._roots.values())


_cache = _ResolveCache()


def resolve_root(root_id: str) -> str | None:
    return _cache.root(root_id)


def resolve_l1(l1_id: str) -> str | None:
    return _cache.l1(l1_id)


def resolve_l2(l2_id: str) -> str | None:
    return _cache.l2(l2_id)


def list_roots() -> list[str]:
    return _cache.roots()


def list_l1_dirs(root_id: str) -> list[Path]:
    return _cache.list_l1_under(root_id)


def list_l2_dirs(l1_id: str) -> list[Path]:
    return _cache.list_l2_under(l1_id)
