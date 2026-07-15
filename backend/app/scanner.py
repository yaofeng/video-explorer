import os
import threading
import time
from collections import OrderedDict
from pathlib import Path
from . import config, probe, cache_index, thumbgen, path_id
from .probe import resolution_label

VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".avi", ".m4v", ".flv", ".webm", ".wmv", ".ts", ".mpg", ".mpeg", ".3gp", ".rm", ".rmvb"}

# 最多缓存的 L2 目录状态数（LRU 淘汰），避免无限内存增长
MAX_CACHED_L2_DIRS = 20


def _build_cache_entry(video_path: Path, item: dict, level: int,
                       thumb_file: str | None = None) -> dict:
    """构建扁平化的 index.yaml 条目。

    字段：file_name, group, level, create_time, modify_time, file_size(MB 整数),
    codec, width, height, duration(秒 整数), resolution_label, thumb_file(可选)。
    """
    stat = video_path.stat()
    meta = item.get("meta") or {}
    entry = {
        "file_name": video_path.name,
        "group": item.get("group"),
        "level": level,
        "create_time": int(stat.st_ctime),
        "modify_time": int(stat.st_mtime),
        "file_size": int(stat.st_size / (1024 * 1024)),  # MB 整数
    }
    if meta:
        entry["codec"] = meta.get("codec")
        entry["width"] = meta.get("width")
        entry["height"] = meta.get("height")
        entry["duration"] = int(meta.get("duration", 0) or 0)  # 秒 整数
        entry["resolution_label"] = meta.get("resolution_label")
    if thumb_file:
        entry["thumb_file"] = thumb_file
    return entry


def _meta_from_cache(cached: dict) -> dict | None:
    """从扁平缓存条目重建内存中的 meta 字典（供 API 返回）。

    内存 meta 保留 resolution_str 和字节级 file_size 以兼容现有 API。
    """
    if not cached.get("codec"):
        return None
    width = cached.get("width", 0) or 0
    height = cached.get("height", 0) or 0
    file_size_mb = cached.get("file_size", 0) or 0
    return {
        "codec": cached["codec"],
        "width": width,
        "height": height,
        "duration": float(cached.get("duration", 0) or 0),
        "resolution_str": f"{width}x{height}",
        "file_size": file_size_mb * 1024 * 1024,  # MB → bytes
        "resolution_label": cached.get("resolution_label", ""),
    }


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
        # 使用 RLock 作为防御性安全网：即使将来误在持锁时调用 _build_*，
        # 也不会死锁。正常代码路径不应依赖可重入性。
        self.lock = threading.RLock()
        self.scanning = False
        self.total = 0
        self.seq = 0
        self.videos = {}  # video_id -> dict
        self.last_used = 0.0  # LRU 时间戳


class _Task:
    """后台索引任务的进度跟踪。"""
    def __init__(self, task_id: str, kind: str, label: str):
        self.id = task_id
        self.kind = kind  # "scan" | "build"
        self.label = label
        self.total = 0
        self.done = 0
        self.running = True
        self.lock = threading.Lock()


class Scanner:
    def __init__(self):
        self._l2_states = OrderedDict()  # LRU 有序：最近使用的在末尾
        self._id_to_path = {}
        self._lock = threading.Lock()  # 保护 _l2_states 和 _id_to_path
        self._tasks = {}  # task_id -> _Task
        self._tasks_lock = threading.Lock()

    def _get_l2_state(self, l2_path: str) -> _L2State:
        with self._lock:
            state = self._l2_states.get(l2_path)
            if state is None:
                state = _L2State()
                self._l2_states[l2_path] = state
            else:
                # 移到末尾（最近使用）
                self._l2_states.move_to_end(l2_path)
            state.last_used = time.time()
            # LRU 淘汰：超过上限时驱逐最久未用的、且未在扫描中的状态
            while len(self._l2_states) > MAX_CACHED_L2_DIRS:
                old_path, old_state = next(iter(self._l2_states.items()))
                if old_state.scanning:
                    # 正在扫描的不能驱逐，跳过（罕见情况）
                    break
                self._l2_states.pop(old_path)
            return state

    def ensure_scan(self, l2_path: str):
        state = self._get_l2_state(l2_path)

        # 在锁内只做状态判断和线程启动，不调用 _build_*（避免重入）
        with state.lock:
            already_scanning = state.scanning
            if not already_scanning:
                state.scanning = True
                t = threading.Thread(
                    target=self._scan_worker, args=(l2_path, state), daemon=True
                )
                t.start()

        # 锁已释放，安全调用 _build_*
        if not already_scanning:
            # 新启动的扫描，短暂等待快速阶段填充数据
            time.sleep(0.5)
        return self._build_groups(state), state.scanning, self._build_progress(state)

    def _scan_worker(self, l2_path: str, state: _L2State):
        try:
            cfg = config.load_config()
            root = find_root(l2_path, cfg.video_path_list)

            # 收集视频文件
            video_paths = []
            for root_dir, dirs, files in os.walk(l2_path):
                for f in files:
                    if Path(f).suffix.lower() in VIDEO_EXTS:
                        video_paths.append(Path(root_dir) / f)

            # 清理孤儿条目：state.videos 中存在但源文件已删除的条目
            existing_vids = {path_id.path_id(str(p)) for p in video_paths}
            with state.lock:
                stale_vids = [vid for vid in state.videos if vid not in existing_vids]
                for vid in stale_vids:
                    state.videos.pop(vid, None)

            with state.lock:
                state.total = len(video_paths)

            # 注册扫描任务（供前端浮窗显示进度）
            scan_task_id = f"scan:{path_id.path_id(l2_path)}"
            self._register_task(scan_task_id, "scan", f"扫描: {Path(l2_path).name}")
            self._update_task(scan_task_id, total=len(video_paths))

            # 批量注册 id_to_path（一次加锁，减少竞争）
            id_path_map = {}
            for video_path in video_paths:
                vid = path_id.path_id(str(video_path))
                id_path_map[vid] = str(video_path)
            with self._lock:
                self._id_to_path.update(id_path_map)

            # ---------------------------------------------------------------
            # Phase L0 — 读缓存预填充：已完整缓存的视频（level 3 + 缩略图存在）
            # 直接标记 level 3，跳过昂贵的 ffprobe/抽帧，实现秒开。
            # ---------------------------------------------------------------
            fully_cached_vids = set()
            if root:
                for video_path in video_paths:
                    vid = path_id.path_id(str(video_path))
                    try:
                        source_mtime = int(video_path.stat().st_mtime)
                    except OSError:
                        continue
                    index_path, thumb_path = cache_index.video_cache_path(
                        str(root), str(video_path)
                    )
                    cached_entries = cache_index.load_index(index_path)
                    cached = next(
                        (v for v in cached_entries if v.get("file_name") == video_path.name),
                        None,
                    )
                    if not cached:
                        continue
                    # 缓存有效性：modify_time（整数秒）记录源文件上次扫描时的 mtime
                    if int(cached.get("modify_time", 0)) < source_mtime:
                        continue  # 源文件已更新，缓存过期
                    if cached.get("level", 1) >= 3 and cached.get("thumb_file") and thumb_path.exists():
                        meta = _meta_from_cache(cached)
                        item = {
                            "video_id": vid,
                            "file_name": video_path.name,
                            "file_size": video_path.stat().st_size,
                            "group": self._group_name(str(video_path), l2_path),
                            "level": 3,
                            "meta": meta,
                        }
                        with state.lock:
                            state.seq += 1
                            item["seq"] = state.seq
                            state.videos[vid] = item
                        fully_cached_vids.add(vid)

            # ---------------------------------------------------------------
            # Phase L1 — 快速阶段：文件系统扫描，收集文件级信息
            # （跳过已完整缓存的视频）
            # ---------------------------------------------------------------
            for video_path in video_paths:
                vid = path_id.path_id(str(video_path))
                if vid in fully_cached_vids:
                    continue

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

                # 持久化最小条目到 index.yaml（磁盘 I/O，在锁外）
                if root:
                    index_path, _ = cache_index.video_cache_path(
                        str(root), str(video_path)
                    )
                    cache_index.update_video_in_index(
                        index_path,
                        _build_cache_entry(video_path, item, level=1),
                    )

                with state.lock:
                    state.seq += 1
                    item["seq"] = state.seq
                    state.videos[vid] = item

            # ---------------------------------------------------------------
            # Phase L2 — ffprobe 元数据
            # ---------------------------------------------------------------
            for video_path in video_paths:
                vid = path_id.path_id(str(video_path))

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
                        "file_size": probe_result["file_size"],
                        "resolution_label": resolution_label(probe_result["height"]),
                    }
                except Exception:
                    meta = None

                with state.lock:
                    if vid in state.videos:
                        state.videos[vid]["meta"] = meta
                        state.videos[vid]["level"] = 2
                        state.videos[vid]["_probe"] = probe_result
                        processed = sum(1 for v in state.videos.values() if v.get("level", 1) >= 2)
                self._update_task(scan_task_id, done=processed)

                # 持久化元数据（磁盘 I/O，在锁外）
                if root and meta:
                    index_path, _ = cache_index.video_cache_path(
                        str(root), str(video_path)
                    )
                    tmp_item = {"group": self._group_name(str(video_path), l2_path), "meta": meta}
                    cache_index.update_video_in_index(
                        index_path,
                        _build_cache_entry(video_path, tmp_item, level=2),
                    )

            # ---------------------------------------------------------------
            # Phase L3 — 缩略图提取
            # ---------------------------------------------------------------
            for video_path in video_paths:
                vid = path_id.path_id(str(video_path))

                with state.lock:
                    entry = state.videos.get(vid)
                    probe_result = entry.get("_probe") if entry else None

                if probe_result is None:
                    continue

                # 抽帧（慢 I/O，在锁外）
                try:
                    png_bytes = thumbgen.extract_frame_from_probe(
                        str(video_path), probe_result
                    )
                except Exception:
                    png_bytes = None

                if not png_bytes or not root:
                    continue

                index_path, thumb_path = cache_index.video_cache_path(
                    str(root), str(video_path)
                )
                # 写 PNG（磁盘 I/O，在锁外）
                thumb_path.write_bytes(png_bytes)

                # 锁内：只更新内存 level，并快照所需字段
                with state.lock:
                    entry_snapshot = None
                    if vid in state.videos:
                        state.videos[vid]["level"] = 3
                        state.videos[vid].pop("_probe", None)
                        entry_snapshot = dict(state.videos[vid])

                # 锁外：用快照持久化（磁盘 I/O）
                if entry_snapshot:
                    cache_index.update_video_in_index(
                        index_path,
                        _build_cache_entry(
                            video_path, entry_snapshot, level=3, thumb_file=thumb_path.name
                        ),
                    )

        finally:
            with state.lock:
                state.scanning = False
                # 清理残留的临时 _probe 字段
                for entry in state.videos.values():
                    entry.pop("_probe", None)
            self._remove_task(scan_task_id)

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
        # 调用者不应持有 state.lock；本方法自行加锁。
        # 注意：使用 RLock 即使误重入也不会死锁。
        with state.lock:
            groups_dict = {}
            for vid, item in state.videos.items():
                g = item["group"]
                if g not in groups_dict:
                    groups_dict[g] = []
                # 浅拷贝，避免返回带 _probe 的临时字段
                clean = {k: v for k, v in item.items() if k != "_probe"}
                groups_dict[g].append(clean)
        return [{"name": k, "videos": v} for k, v in groups_dict.items()]

    def _build_progress(self, state: _L2State):
        # 同上：调用者不应持锁。
        with state.lock:
            level1 = level2 = level3 = 0
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
        # 单次加锁内完成所有内存读取，不再调用 _build_progress（避免重入）
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

            level1 = level2 = level3 = 0
            for v in state.videos.values():
                lv = v.get("level", 1)
                if lv == 1:
                    level1 += 1
                elif lv == 2:
                    level2 += 1
                elif lv == 3:
                    level3 += 1
            progress = {
                "total": state.total,
                "level1": level1,
                "level2": level2,
                "level3": level3,
            }
            scanning = state.scanning
            total = state.total
            ready = sum(1 for v in state.videos.values() if v.get("level", 1) >= 2)
            last_seq = state.seq

        return {
            "scanning": scanning,
            "total": total,
            "ready": ready,
            "last_seq": last_seq,
            "progress": progress,
            "updates": updates,
        }

    def get_thumb(self, video_id: str, small: bool = False):
        """返回缩略图字节。

        small=True 返回压缩后的小 JPEG（卡片用，懒生成并缓存为 .small.jpg）；
        small=False 返回原始 JPEG（浮层用）。
        """
        with self._lock:
            video_path = self._id_to_path.get(video_id)
        if video_path is None:
            return None
        cfg = config.load_config()
        root = find_root(video_path, cfg.video_path_list)
        if root is None:
            return None
        index_path, _ = cache_index.video_cache_path(str(root), video_path)
        full_path = cache_index.get_thumb_path(index_path, Path(video_path).name)
        if full_path is None:
            return None
        if small:
            # 小图：{stem}.small.jpg，与 full 同目录
            small_path = full_path.with_suffix(".small.jpg")
            if not small_path.exists() or small_path.stat().st_mtime < full_path.stat().st_mtime:
                small_bytes = thumbgen.make_small_jpeg(full_path.read_bytes())
                small_path.write_bytes(small_bytes)
            return ("image/jpeg", small_path.read_bytes())
        return ("image/jpeg", full_path.read_bytes())

    # ------------------------------------------------------------------
    # 任务进度跟踪（供前端浮窗显示）
    # ------------------------------------------------------------------
    def _register_task(self, task_id: str, kind: str, label: str) -> _Task:
        with self._tasks_lock:
            task = _Task(task_id, kind, label)
            self._tasks[task_id] = task
            return task

    def _get_task(self, task_id: str) -> _Task | None:
        with self._tasks_lock:
            return self._tasks.get(task_id)

    def _update_task(self, task_id: str, **kwargs):
        with self._tasks_lock:
            task = self._tasks.get(task_id)
        if task:
            with task.lock:
                for k, v in kwargs.items():
                    setattr(task, k, v)

    def _remove_task(self, task_id: str):
        with self._tasks_lock:
            self._tasks.pop(task_id, None)

    def get_tasks(self) -> list[dict]:
        """返回所有运行中的任务进度。"""
        with self._tasks_lock:
            tasks = list(self._tasks.values())
        result = []
        for t in tasks:
            with t.lock:
                if not t.running:
                    continue
                result.append({
                    "id": t.id,
                    "kind": t.kind,
                    "label": t.label,
                    "total": t.total,
                    "done": t.done,
                })
        return result

    def build_index(self, root_path: str) -> dict:
        """为整个视频库根目录构建索引（所有 L2 目录）。后台执行，立即返回状态。"""
        task_id = f"build:{path_id.path_id(root_path)}"
        existing = self._get_task(task_id)
        if existing:
            with existing.lock:
                if existing.running:
                    return {"running": True, "total": existing.total, "done": existing.done}

        self._register_task(task_id, "build", f"构建索引: {Path(root_path).name}")
        t = threading.Thread(target=self._build_worker, args=(root_path, task_id), daemon=True)
        t.start()
        return {"running": True, "total": 0, "done": 0}

    def _build_worker(self, root_path: str, task_id: str):
        try:
            root = Path(root_path)
            l2_dirs = []
            for l1 in sorted(root.iterdir()):
                if not l1.is_dir():
                    continue
                for l2 in sorted(l1.iterdir()):
                    if l2.is_dir():
                        l2_dirs.append(str(l2))
            self._update_task(task_id, total=len(l2_dirs))

            for idx, l2 in enumerate(l2_dirs):
                # 触发该 L2 目录扫描（若已在扫描则跳过等待）
                self.ensure_scan(l2)
                # 等待该目录扫描完成
                state = self._get_l2_state(l2)
                while True:
                    with state.lock:
                        scanning = state.scanning
                    if not scanning:
                        break
                    time.sleep(0.3)
                self._update_task(task_id, done=idx + 1)
        finally:
            task = self._get_task(task_id)
            if task:
                with task.lock:
                    task.running = False
            self._remove_task(task_id)
