import os
import threading
import time
from pathlib import Path
from . import config, probe, cache_index, thumbgen, path_id
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
                return self._build_groups(state), True, self._build_progress(state)

            state.scanning = True
            state.thread = threading.Thread(
                target=self._scan_worker, args=(l2_path, state), daemon=True
            )
            state.thread.start()

        # 短暂等待快速扫描
        time.sleep(0.5)
        return self._build_groups(state), state.scanning, self._build_progress(state)

    def _scan_worker(self, l2_path: str, state: _L2State):
        try:
            cfg = config.load_config()
            root = find_root(l2_path, cfg.video_path_list)

            # 收集视频
            video_paths = []
            for root_dir, dirs, files in os.walk(l2_path):
                for f in files:
                    if Path(f).suffix.lower() in VIDEO_EXTS:
                        video_paths.append(Path(root_dir) / f)

            with state.lock:
                state.total = len(video_paths)

            # ---------------------------------------------------------------
            # Phase L1 — Fast:  filesystem scan, collect file-level info
            # ---------------------------------------------------------------
            for video_path in video_paths:
                vid = path_id.path_id(str(video_path))
                self.id_to_path[vid] = str(video_path)

                group_name = self._group_name(str(video_path), l2_path)
                file_size = video_path.stat().st_size

                item = {
                    "video_id": vid,
                    "file_name": video_path.name,
                    "file_size": file_size,
                    "group": group_name,
                    "level": 1,
                    "meta": None,
                }

                # Persist minimal entry to index.yaml
                if root:
                    index_path, _ = cache_index.video_cache_path(
                        str(root), str(video_path)
                    )
                    cache_index.update_video_in_index(
                        index_path,
                        {
                            "file_name": video_path.name,
                            "file_size_gb": file_size / (1024**3),
                            "group": group_name,
                            "level": 1,
                        },
                    )

                with state.lock:
                    state.seq += 1
                    item["seq"] = state.seq
                    state.videos[vid] = item

            # ---------------------------------------------------------------
            # Phase L2 — ffprobe metadata
            # ---------------------------------------------------------------
            for video_path in video_paths:
                vid = path_id.path_id(str(video_path))

                # Skip if already at level >= 2 (e.g. from a previous scan)
                with state.lock:
                    if state.videos.get(vid, {}).get("level", 1) >= 2:
                        continue

                meta = None
                probe_result = None
                try:
                    probe_result = probe.probe_video(str(video_path))
                    meta = {
                        "codec": probe_result["codec"],
                        "width": probe_result["width"],
                        "height": probe_result["height"],
                        "duration": probe_result["duration"],
                        "resolution_str": probe_result["resolution_str"],
                        "resolution_label": resolution_label(probe_result["height"]),
                    }
                except Exception:
                    meta = None

                with state.lock:
                    if vid in state.videos:
                        state.videos[vid]["meta"] = meta
                        state.videos[vid]["level"] = 2
                        state.videos[vid]["_probe"] = probe_result  # cached for L3

                if root and meta:
                    index_path, _ = cache_index.video_cache_path(
                        str(root), str(video_path)
                    )
                    cache_index.update_video_in_index(
                        index_path,
                        {
                            "file_name": video_path.name,
                            "file_size_gb": video_path.stat().st_size / (1024**3),
                            "group": self._group_name(str(video_path), l2_path),
                            "level": 2,
                            "meta": meta,
                        },
                    )

            # ---------------------------------------------------------------
            # Phase L3 — Thumbnail extraction
            # ---------------------------------------------------------------
            for video_path in video_paths:
                vid = path_id.path_id(str(video_path))

                with state.lock:
                    entry = state.videos.get(vid)
                    probe_result = entry.get("_probe") if entry else None

                if probe_result is None:
                    # Probe failed during L2, nothing to extract from
                    continue

                try:
                    png_bytes = thumbgen.extract_frame_from_probe(
                        str(video_path), probe_result
                    )
                except Exception:
                    png_bytes = None

                if png_bytes and root:
                    index_path, thumb_path = cache_index.video_cache_path(
                        str(root), str(video_path)
                    )
                    thumb_path.write_bytes(png_bytes)

                    with state.lock:
                        if vid in state.videos:
                            state.videos[vid]["level"] = 3
                            state.videos[vid].pop("_probe", None)

                    with state.lock:
                        entry = state.videos.get(vid)
                        if entry:
                            cache_index.update_video_in_index(
                                index_path,
                                {
                                    "file_name": video_path.name,
                                    "file_size_gb": video_path.stat().st_size
                                    / (1024**3),
                                    "group": entry.get("group"),
                                    "level": 3,
                                    "meta": entry.get("meta"),
                                    "thumb_file": thumb_path.name,
                                },
                            )

        finally:
            with state.lock:
                state.scanning = False
                # Clean up temporary probe data left from L2 (L3 failures /
                # early-exit path).
                for entry in state.videos.values():
                    entry.pop("_probe", None)

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

    def _build_progress(self, state: _L2State):
        with state.lock:
            level1 = 0
            level2 = 0
            level3 = 0
            for item in state.videos.values():
                lv = item.get("level", 1)
                if lv == 1:
                    level1 += 1
                elif lv == 2:
                    level2 += 1
                elif lv == 3:
                    level3 += 1
            return {
                "total": state.total,
                "level1": level1,
                "level2": level2,
                "level3": level3,
            }

    def status(self, l2_path: str, since: int = 0):
        state = self._get_l2_state(l2_path)
        with state.lock:
            updates = []
            for vid, item in state.videos.items():
                if item.get("seq", -1) > since:
                    entry = {
                        "seq": item["seq"],
                        "video_id": vid,
                        "file_name": item["file_name"],
                        "file_size": item["file_size"],
                        "group": item["group"],
                        "level": item.get("level", 1),
                    }
                    if item.get("meta") is not None:
                        entry["meta"] = item["meta"]
                    updates.append(entry)
            updates.sort(key=lambda u: u["seq"])
            return {
                "scanning": state.scanning,
                "total": state.total,
                "ready": sum(1 for v in state.videos.values() if v.get("level", 1) >= 2),
                "last_seq": state.seq,
                "progress": self._build_progress(state),
                "updates": updates,
            }

    def get_thumb(self, video_id: str):
        if video_id not in self.id_to_path:
            return None
        video_path = self.id_to_path[video_id]
        cfg = config.load_config()
        root = find_root(video_path, cfg.video_path_list)
        if root is None:
            return None
        index_path, _ = cache_index.video_cache_path(str(root), video_path)
        thumb_path = cache_index.get_thumb_path(index_path, Path(video_path).name)
        if thumb_path is None:
            return None
        return thumb_path.read_bytes()
