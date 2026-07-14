import os
import threading
import time
from pathlib import Path
from . import config, probe, descfile, thumbgen, path_id
from .probe import resolution_label

VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".avi", ".m4v", ".flv", ".webm", ".wmv", ".ts", ".mpg", ".mpeg", ".3gp", ".rm", ".rmvb"}


def find_root(video_path: str, roots: list[str]) -> Path | None:
    p = Path(video_path).resolve()
    best = None
    for r in roots:
        rp = Path(r).resolve()
        try:
            p.relative_to(rp)
            if best is None or len(str(rp)) > len(str(best)):
                best = rp
        except ValueError:
            continue
    return best


class _L2State:
    def __init__(self):
        self.lock = threading.Lock()
        self.scanning = False
        self.total = 0
        self.seq = 0
        self.videos = {}  # video_id -> dict
        self.thread = None


class Scanner:
    def __init__(self):
        self.l2_states = {}
        self.id_to_path = {}
        self._lock = threading.Lock()

    def _get_l2_state(self, l2_path: str) -> _L2State:
        with self._lock:
            if l2_path not in self.l2_states:
                self.l2_states[l2_path] = _L2State()
            return self.l2_states[l2_path]

    def ensure_scan(self, l2_path: str):
        state = self._get_l2_state(l2_path)
        with state.lock:
            if state.scanning:
                return self._build_groups(state), True

            state.scanning = True
            state.thread = threading.Thread(target=self._scan_worker, args=(l2_path, state), daemon=True)
            state.thread.start()

        # 短暂等待快速扫描
        time.sleep(0.5)
        return self._build_groups(state), state.scanning

    def _scan_worker(self, l2_path: str, state: _L2State):
        try:
            cfg = config.load_config()

            # 收集视频
            videos = []
            for root, dirs, files in os.walk(l2_path):
                for f in files:
                    if Path(f).suffix.lower() in VIDEO_EXTS:
                        videos.append(Path(root) / f)

            with state.lock:
                state.total = len(videos)

            for video_path in videos:
                vid = path_id.path_id(str(video_path))
                self.id_to_path[vid] = str(video_path)

                # 检查缓存
                cache_path = self._cache_desc_path(str(video_path), cfg)
                source_mtime = video_path.stat().st_mtime

                if cache_path.exists() and cache_path.stat().st_mtime >= source_mtime:
                    # 缓存有效
                    try:
                        desc, _, _ = descfile.read_desc(str(cache_path))
                        meta = desc
                        meta["resolution_label"] = resolution_label(meta["height"])
                    except Exception:
                        meta = None

                    with state.lock:
                        state.videos[vid] = {
                            "video_id": vid,
                            "file_name": video_path.name,
                            "file_size": video_path.stat().st_size,
                            "group": self._group_name(str(video_path), l2_path),
                            "ready": meta is not None,
                            "meta": meta,
                        }
                else:
                    # 生成
                    try:
                        meta, small_bytes, full_bytes = thumbgen.generate_thumbnails(str(video_path))
                        meta["resolution_label"] = resolution_label(meta["height"])

                        cache_path.parent.mkdir(parents=True, exist_ok=True)
                        descfile.write_desc(str(cache_path), meta, small_bytes, full_bytes)

                        item = {
                            "video_id": vid,
                            "file_name": video_path.name,
                            "file_size": video_path.stat().st_size,
                            "group": self._group_name(str(video_path), l2_path),
                            "ready": True,
                            "meta": meta,
                        }
                    except Exception:
                        item = {
                            "video_id": vid,
                            "file_name": video_path.name,
                            "file_size": video_path.stat().st_size,
                            "group": self._group_name(str(video_path), l2_path),
                            "ready": False,
                            "meta": None,
                        }

                    with state.lock:
                        state.videos[vid] = item
                        state.seq += 1

        finally:
            with state.lock:
                state.scanning = False

    def _cache_desc_path(self, video_path: str, cfg: config.AppConfig) -> Path:
        root = find_root(video_path, cfg.video_path_list)
        if root is None:
            raise ValueError(f"未找到 {video_path} 的根目录")
        rel = Path(video_path).resolve().relative_to(root)
        return config.data_path() / "cache" / rel

    def _group_name(self, video_path: str, l2_path: str) -> str:
        v = Path(video_path).resolve()
        l2 = Path(l2_path).resolve()
        parent = v.parent
        if parent == l2:
            return "未分组"
        try:
            return str(parent.relative_to(l2)).replace("\\", "/")
        except ValueError:
            return "未分组"

    def _build_groups(self, state: _L2State):
        with state.lock:
            groups_dict = {}
            for vid, item in state.videos.items():
                g = item["group"]
                if g not in groups_dict:
                    groups_dict[g] = []
                groups_dict[g].append(item)
        return [{"name": k, "videos": v} for k, v in groups_dict.items()]

    def status(self, l2_path: str, since: int = 0):
        state = self._get_l2_state(l2_path)
        with state.lock:
            updates = []
            for vid, item in state.videos.items():
                if item["ready"] and item["meta"] is not None:
                    updates.append({
                        "seq": state.seq,
                        "video_id": vid,
                        "file_name": item["file_name"],
                        "file_size": item["file_size"],
                        "group": item["group"],
                        "meta": item["meta"],
                    })
            return {
                "scanning": state.scanning,
                "total": state.total,
                "ready": sum(1 for v in state.videos.values() if v["ready"]),
                "last_seq": state.seq,
                "updates": updates,
            }

    def get_thumb(self, video_id: str, full: bool = False):
        if video_id not in self.id_to_path:
            return None
        video_path = self.id_to_path[video_id]
        cache_path = self._cache_desc_path(video_path, config.load_config())
        if not cache_path.exists():
            return None
        try:
            desc, small_thumb, full_thumb = descfile.read_desc(str(cache_path))
            return full_thumb if full else small_thumb
        except Exception:
            return None
