import os
import logging
import threading
import time
import hashlib
import json
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from . import probe, cache_index, thumbgen, framegen
from .. import config, path_id
from ..safe_regex import safe_match

logger = logging.getLogger(__name__)

VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".avi", ".m4v", ".flv", ".webm", ".wmv", ".ts", ".mpg", ".mpeg", ".3gp", ".rm", ".rmvb"}

# 最多缓存的 L2 目录状态数（LRU 淘汰），避免无限内存增长
MAX_CACHED_L2_DIRS = 20


def _resolution_label(height: int) -> str:
    """根据视频高度计算分辨率标签（4K/2K/FHD/HD/SD/LD）。"""
    if height >= 2160:
        return "4K"
    if height >= 1440:
        return "2K"
    if height >= 1080:
        return "FHD"
    if height >= 720:
        return "HD"
    if height >= 480:
        return "SD"
    if height >= 360:
        return "LD"
    return f"{height}P" if height else "Unknown"


def parse_rules_hash(rules: list[dict]) -> str:
    """计算 parse_rules 的稳定哈希，用于缓存失效判定。"""
    if not rules:
        return ""
    serialized = json.dumps(rules, sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(serialized.encode("utf-8")).hexdigest()[:12]


def _parse_filename(file_name: str, rules: list[dict]) -> dict | None:
    """对文件名（**去掉扩展名后**）应用解析规则，匹配成功返回 ext 字典。

    - 先剥离原始扩展名再匹配（用户要求）
    - 无规则匹配时返回 None（调用方应删除已有 ext）

    使用带超时的 safe_match，避免用户提交的灾难性正则挂死扫描线程（H3）。
    """
    if not rules:
        return None
    # 剥离扩展名：test.mp4 → test
    name_without_ext = Path(file_name).stem
    for rule in rules:
        pattern = rule.get("pattern", "")
        if not pattern:
            continue
        m = safe_match(pattern, name_without_ext, timeout=2.0)
        if m:
            ext = {k: v for k, v in m.groupdict().items() if v is not None}
            if ext:
                return ext
    return None


def _build_cache_entry(video_path: Path, item: dict, level: int,
                       thumb_file: str | None = None) -> dict:
    """构建扁平化的 index.yaml 条目。"""
    stat = video_path.stat()
    entry = {
        "file_name": video_path.name,
        "group": item.get("group"),
        "level": level,
        "create_time": int(stat.st_ctime),
        "modify_time": int(stat.st_mtime),
        # 缓存中 file_size 单位为 MB（整数），读取时再转换为 bytes
        "file_size": int(stat.st_size / (1024 * 1024)),
    }
    # L2+ 元数据字段
    if level >= 2:
        entry["codec"] = item.get("codec")
        entry["width"] = item.get("width")
        entry["height"] = item.get("height")
        entry["duration"] = round(float(item.get("duration", 0) or 0), 3)
        entry["resolution_label"] = item.get("resolution_label")
    # ext 字段：只有非空时才写入（用户要求：无匹配时删除 ext）
    ext = item.get("ext")
    if ext:
        entry["ext"] = ext
    # 不写入 ext key，这样 load_index 时 "ext" in cached 为 False
    if thumb_file:
        entry["thumb_file"] = thumb_file
    return entry


def _merge_metadata(item: dict, probe_result: dict) -> None:
    """将 probe 结果合并到扁平 item 中（原地修改）。"""
    item["codec"] = probe_result["codec"]
    item["width"] = probe_result["width"]
    item["height"] = probe_result["height"]
    item["duration"] = probe_result["duration"]
    item["resolution_label"] = _resolution_label(probe_result["height"])


def _apply_cache_to_item(item: dict, cached: dict) -> None:
    """将缓存条目中的元数据字段合并到扁平 item（原地修改）。"""
    if not cached.get("codec"):
        return
    item["codec"] = cached["codec"]
    item["width"] = cached.get("width", 0) or 0
    item["height"] = cached.get("height", 0) or 0
    item["duration"] = float(cached.get("duration", 0) or 0)
    item["resolution_label"] = cached.get("resolution_label", "")


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


# ---------------------------------------------------------------------------
# 并发控制：per-index_path 锁，防止多个线程同时读写同一个 index.yaml
# ---------------------------------------------------------------------------
_index_locks: dict[str, threading.Lock] = {}
_index_locks_lock = threading.Lock()


def _get_index_lock(index_path: Path) -> threading.Lock:
    key = str(index_path)
    with _index_locks_lock:
        if key not in _index_locks:
            _index_locks[key] = threading.Lock()
        return _index_locks[key]


def _atomic_update_index(index_path: Path, video_info: dict) -> None:
    """原子地 upsert 一条 entry 到 index.yaml（读-改-写 + 文件锁）。"""
    lock = _get_index_lock(index_path)
    with lock:
        cache_index.update_video_in_index(index_path, video_info)


def _atomic_remove_from_index(index_path: Path, file_name: str) -> None:
    """原子地从 index.yaml 删除一条 entry（读-改-写 + 文件锁）。"""
    lock = _get_index_lock(index_path)
    with lock:
        cache_index.remove_video_from_index(index_path, file_name)


class _L2State:
    def __init__(self):
        # 使用 RLock 作为防御性安全网
        self.lock = threading.RLock()
        self.scanning = False
        # 扫描阶段："idle" | "quick" | "deep" | "done"
        # - idle: 未扫描
        # - quick: Phase 1 进行中（快速文件系统扫描，处理新增/删除）
        # - deep: Phase 2 进行中（深度扫描，ffprobe + 缩略图）
        # - done: 完成
        self.phase = "idle"
        self.total = 0
        self.seq = 0
        self.videos = {}  # video_id -> dict
        self.last_used = 0.0  # LRU 时间戳
        self.fully_scanned = False
        self.last_source_mtime = 0
        # parse_rules 哈希（用于缓存失效判定）
        self.last_parse_rules_hash = ""
        # 扫描完成事件（供 build_worker 等待）
        self.done_event = threading.Event()
        # Phase 1 完成标志：一次性通知前端全量刷新（处理删除等场景）
        self.refresh_full = False
        # 错误列表（聚合计数，供右上角 TaskToast 显示）
        self.errors: list[dict] = []  # [{"file": "...", "message": "..."}]


class _Task:
    """后台索引任务的进度跟踪（仅 build 任务使用，scan 任务不再有进度条）。"""
    def __init__(self, task_id: str, kind: str, label: str):
        self.id = task_id
        self.kind = kind  # "build"
        self.label = label
        self.total = 0
        self.done = 0
        self.running = True
        self.lock = threading.Lock()


class Scanner:
    def __init__(self):
        self._l2_states = OrderedDict()  # LRU 有序
        self._id_to_path = {}
        self._lock = threading.Lock()  # 保护 _l2_states 和 _id_to_path
        self._tasks = {}  # task_id -> _Task
        self._tasks_lock = threading.Lock()
        self._frame_executor = ThreadPoolExecutor(max_workers=2)
        self._frame_generating: set[str] = set()
        self._frame_generating_lock = threading.Lock()

    def _get_l2_state(self, l2_path: str) -> _L2State:
        with self._lock:
            state = self._l2_states.get(l2_path)
            if state is None:
                state = _L2State()
                self._l2_states[l2_path] = state
            else:
                self._l2_states.move_to_end(l2_path)
            state.last_used = time.time()
            while len(self._l2_states) > MAX_CACHED_L2_DIRS:
                old_path, old_state = next(iter(self._l2_states.items()))
                if old_state.scanning:
                    break
                self._l2_states.pop(old_path)
                self._evict_id_to_path(old_path)
            return state

    def _evict_id_to_path(self, l2_path: str) -> None:
        try:
            l2_resolved = str(Path(l2_path).resolve())
        except OSError:
            l2_resolved = l2_path
        stale = [
            vid for vid, p in self._id_to_path.items()
            if str(p).startswith(l2_resolved + os.sep) or str(p) == l2_resolved
        ]
        for vid in stale:
            self._id_to_path.pop(vid, None)

    def ensure_scan(self, l2_path: str):
        """打开 L2 目录：若 index.yaml 已存在则立即从缓存渲染，后台并行扫描。"""
        state = self._get_l2_state(l2_path)
        cfg = config.load_config()
        current_hash = parse_rules_hash(cfg.parse_rules)

        with state.lock:
            already_scanning = state.scanning
            # 短路判定：已完整扫描 + 目录 mtime 未变 + parse_rules 未变
            short_circuit = False
            if not already_scanning and state.fully_scanned:
                try:
                    cur_mtime = int(Path(l2_path).stat().st_mtime)
                    short_circuit = (
                        cur_mtime <= state.last_source_mtime
                        and state.last_parse_rules_hash == current_hash
                    )
                except OSError:
                    short_circuit = False

            if not already_scanning and not short_circuit:
                state.scanning = True
                state.phase = "quick"
                state.refresh_full = False
                state.errors = []
                state.last_parse_rules_hash = current_hash
                state.done_event.clear()

                # 从已有 index.yaml 加载到 state.videos，实现秒开渲染
                had_cache = self._load_from_cache(l2_path, state)

                t = threading.Thread(
                    target=self._scan_worker, args=(l2_path, state), daemon=True
                )
                t.start()

                # 无缓存时短暂等待，让 Phase 1 有时间填充数据
                if not had_cache:
                    time.sleep(2.0)  # 给扫描线程足够时间完成 Phase 1

        return self._build_groups(state), state.scanning, self._build_progress(state)

    def _load_from_cache(self, l2_path: str, state: _L2State) -> bool:
        """从磁盘上已有的 index.yaml 加载视频条目到 state.videos，实现立即渲染。

        Returns True 表示成功加载了至少一个条目，False 表示无缓存。
        """
        cfg = config.load_config()
        root = find_root(l2_path, cfg.video_path_list)
        if not root:
            return False

        loaded_count = 0
        # 遍历 l2_path 下所有含 index.yaml 的目录
        for dirpath, _dirnames, filenames in os.walk(l2_path):
            if "index.yaml" not in filenames:
                continue
            index_path = Path(dirpath) / "index.yaml"
            cached_entries = cache_index.load_index(index_path)
            for cached in cached_entries:
                fname = cached.get("file_name")
                if not fname:
                    continue
                video_path = Path(dirpath) / fname
                if not video_path.exists():
                    continue
                try:
                    stat = video_path.stat()
                except OSError:
                    continue
                vid = path_id.path_id(str(video_path))
                item = {
                    "video_id": vid,
                    "file_name": fname,
                    "file_size": int(stat.st_size / (1024 * 1024)),
                    "modify_time": int(stat.st_mtime),
                    "group": self._group_name(str(video_path), l2_path),
                    "level": cached.get("level", 1),
                }
                _apply_cache_to_item(item, cached)
                if "ext" in cached:
                    item["ext"] = cached["ext"]
                with state.lock:
                    state.seq += 1
                    item["seq"] = state.seq
                    state.videos[vid] = item
                    self._id_to_path[vid] = str(video_path)
                loaded_count += 1
        return loaded_count > 0

    def _scan_worker(self, l2_path: str, state: _L2State):
        """两阶段扫描：Phase 1 快速文件系统扫描 + Phase 2 深度 ffprobe/缩略图。"""
        completed = False
        l2_mtime = 0
        try:
            cfg = config.load_config()
            root = find_root(l2_path, cfg.video_path_list)
            parse_rules = cfg.parse_rules

            try:
                l2_mtime = int(Path(l2_path).stat().st_mtime)
            except OSError:
                l2_mtime = 0

            # 收集视频文件
            video_paths: list[Path] = []
            for root_dir, _dirs, files in os.walk(l2_path):
                for f in files:
                    if Path(f).suffix.lower() in VIDEO_EXTS:
                        video_paths.append(Path(root_dir) / f)

            with state.lock:
                state.total = len(video_paths)

            existing_vids = {path_id.path_id(str(p)) for p in video_paths}

            # 批量注册 id_to_path
            id_path_map = {}
            for video_path in video_paths:
                vid = path_id.path_id(str(video_path))
                id_path_map[vid] = str(video_path)
            with self._lock:
                self._id_to_path.update(id_path_map)

            # ---------------------------------------------------------------
            # Phase 1 — 快速文件系统扫描
            # 更新 index.yaml：处理新增/删除文件、更新 ext 字段
            # ---------------------------------------------------------------

            # 1a. 处理删除：state.videos 中存在但磁盘已不存在的文件
            deleted_entries = []
            with state.lock:
                stale_vids = [vid for vid in state.videos if vid not in existing_vids]
                for vid in stale_vids:
                    deleted_entries.append({
                        "video_id": vid,
                        "file_name": state.videos[vid]["file_name"],
                        "group": state.videos[vid]["group"],
                        "path": self._id_to_path.get(vid),
                    })
                    state.videos.pop(vid, None)
                    state.seq += 1

            # 从 index.yaml 删除 + 清理缩略图
            if root:
                for del_entry in deleted_entries:
                    if del_entry["path"]:
                        try:
                            index_path, thumb_path = cache_index.video_cache_path(
                                str(root), del_entry["path"]
                            )
                            _atomic_remove_from_index(index_path, del_entry["file_name"])
                            if thumb_path.exists():
                                thumb_path.unlink()
                            # 也清理 small 缩略图
                            small_path = thumb_path.with_suffix(".small.jpg")
                            if small_path.exists():
                                small_path.unlink()
                        except OSError as e:
                            logger.warning("清理删除文件缓存失败: %s", e)

            # 1b. 处理新增/已存在的文件：更新 L1 信息 + ext 字段
            if root:
                for idx, video_path in enumerate(video_paths):
                    vid = path_id.path_id(str(video_path))
                    try:
                        stat = video_path.stat()
                        source_mtime = int(stat.st_mtime)
                    except OSError as e:
                        logger.warning(f"Phase 1: stat failed for {video_path}: {e}")
                        continue

                    index_path, _thumb_path = cache_index.video_cache_path(
                        str(root), str(video_path)
                    )
                    group_name = self._group_name(str(video_path), l2_path)

                    # 文件名解析（剥离扩展名后匹配）
                    ext_data = _parse_filename(video_path.name, parse_rules)

                    # 读现有缓存
                    cached_entries = cache_index.load_index(index_path)
                    cached = next(
                        (v for v in cached_entries if v.get("file_name") == video_path.name),
                        None,
                    )

                    file_size_mb = int(stat.st_size / (1024 * 1024))

                    if cached and int(cached.get("modify_time", 0)) >= source_mtime:
                        # 缓存有效（mtime 未变）：仅更新 ext 字段
                        if ext_data:
                            cached["ext"] = ext_data
                        else:
                            cached.pop("ext", None)
                        _atomic_update_index(index_path, cached)

                        # 更新 state
                        item = {
                            "video_id": vid,
                            "file_name": video_path.name,
                            "file_size": file_size_mb,
                            "modify_time": source_mtime,
                            "group": group_name,
                            "level": cached.get("level", 1),
                        }
                        _apply_cache_to_item(item, cached)
                        if "ext" in cached:
                            item["ext"] = cached["ext"]
                        with state.lock:
                            state.seq += 1
                            item["seq"] = state.seq
                            state.videos[vid] = item
                    else:
                        # 新文件或缓存失效：创建 L1 条目
                        item = {
                            "video_id": vid,
                            "file_name": video_path.name,
                            "file_size": file_size_mb,
                            "modify_time": source_mtime,
                            "group": group_name,
                            "level": 1,
                        }
                        if ext_data:
                            item["ext"] = ext_data
                        # 无匹配时不写入 ext（_build_cache_entry 会跳过）

                        entry = _build_cache_entry(video_path, item, level=1)
                        _atomic_update_index(index_path, entry)

                        with state.lock:
                            state.seq += 1
                            item["seq"] = state.seq
                            state.videos[vid] = item

            # Phase 1 完成：通知前端全量刷新（处理删除等）
            with state.lock:
                state.phase = "deep"
                state.refresh_full = True

            # ---------------------------------------------------------------
            # Phase 2 — 深度扫描
            # 对需要更新的文件（level<3 或 mtime 变化）执行 ffprobe + 缩略图
            # 每完成一个文件就原子更新 index.yaml
            # ---------------------------------------------------------------
            for video_path in video_paths:
                vid = path_id.path_id(str(video_path))

                # 判断是否需要深度扫描
                with state.lock:
                    item = state.videos.get(vid)
                    if not item:
                        continue
                    current_level = item.get("level", 1)
                    current_mtime = item.get("modify_time")
                try:
                    actual_mtime = int(video_path.stat().st_mtime)
                except OSError:
                    continue
                if current_level >= 3 and current_mtime == actual_mtime:
                    # 已完整扫描且 mtime 未变，跳过
                    continue

                # --- ffprobe ---
                probe_result = None
                try:
                    probe_result = probe.probe_video(str(video_path))
                except Exception as e:
                    with state.lock:
                        state.errors.append({
                            "file": video_path.name,
                            "message": f"ffprobe 失败: {e}",
                        })
                    continue

                if probe_result is None:
                    continue

                # 更新 state 到 L2
                with state.lock:
                    if vid in state.videos:
                        _merge_metadata(state.videos[vid], probe_result)
                        state.videos[vid]["level"] = 2
                        state.videos[vid]["_probe"] = probe_result
                        state.seq += 1
                        state.videos[vid]["seq"] = state.seq
                        snapshot = dict(state.videos[vid])

                # 原子更新 index.yaml 到 L2
                if root:
                    index_path, _ = cache_index.video_cache_path(
                        str(root), str(video_path)
                    )
                    snapshot["group"] = self._group_name(str(video_path), l2_path)
                    entry = _build_cache_entry(video_path, snapshot, level=2)
                    _atomic_update_index(index_path, entry)

                # --- 缩略图提取 ---
                png_bytes = None
                try:
                    png_bytes = thumbgen.extract_frame_from_probe(
                        str(video_path), probe_result
                    )
                except Exception as e:
                    with state.lock:
                        state.errors.append({
                            "file": video_path.name,
                            "message": f"缩略图提取失败: {e}",
                        })

                if png_bytes and root:
                    index_path, thumb_path = cache_index.video_cache_path(
                        str(root), str(video_path)
                    )
                    try:
                        thumb_path.write_bytes(png_bytes)
                    except Exception as e:
                        with state.lock:
                            state.errors.append({
                                "file": video_path.name,
                                "message": f"缩略图写入失败: {e}",
                            })
                        # 清理残留 _probe，保持 L2
                        with state.lock:
                            if vid in state.videos:
                                state.videos[vid].pop("_probe", None)
                        continue

                    # 升级到 L3
                    with state.lock:
                        if vid in state.videos:
                            state.videos[vid]["level"] = 3
                            state.videos[vid].pop("_probe", None)
                            state.seq += 1
                            state.videos[vid]["seq"] = state.seq
                            entry_snapshot = dict(state.videos[vid])

                    entry = _build_cache_entry(
                        video_path, entry_snapshot, level=3,
                        thumb_file=thumb_path.name,
                    )
                    _atomic_update_index(index_path, entry)
                else:
                    # 无缩略图：保持 L2，清理 _probe
                    with state.lock:
                        if vid in state.videos:
                            state.videos[vid].pop("_probe", None)

            # Phase 2 完成
            with state.lock:
                state.phase = "done"

            completed = True

        except Exception as e:
            logger.exception("scan worker failed for %s", l2_path)
            with state.lock:
                state.errors.append({
                    "file": "(scan)",
                    "message": f"扫描异常: {e}",
                })
        finally:
            with state.lock:
                state.scanning = False
                if completed:
                    state.fully_scanned = True
                    state.last_source_mtime = l2_mtime
                # 清理残留 _probe
                for entry in state.videos.values():
                    entry.pop("_probe", None)
            state.done_event.set()

    def invalidate_all_caches(self) -> None:
        """清除所有 L2 状态的 fully_scanned 标记（用于 parse_rules 变更时）。"""
        with self._lock:
            for state in self._l2_states.values():
                with state.lock:
                    state.fully_scanned = False

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
                clean = {k: v for k, v in item.items() if k != "_probe"}
                groups_dict[g].append(clean)
        return [{"name": k, "videos": v} for k, v in groups_dict.items()]

    def _build_progress(self, state: _L2State):
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
                    if item.get("modify_time") is not None:
                        entry["modify_time"] = item["modify_time"]
                    if item.get("ext") is not None:
                        entry["ext"] = item["ext"]
                    if item.get("level", 1) >= 2 and item.get("codec"):
                        entry["codec"] = item["codec"]
                        entry["width"] = item.get("width")
                        entry["height"] = item.get("height")
                        entry["duration"] = item.get("duration")
                        entry["resolution_label"] = item.get("resolution_label")
                    updates.append(entry)
            updates.sort(key=lambda u: u["seq"])

            scanning = state.scanning
            total = state.total
            ready = sum(1 for v in state.videos.values() if v.get("level", 1) >= 2)
            last_seq = state.seq
            phase = state.phase
            refresh_full = state.refresh_full
            errors = list(state.errors)
            # refresh_full 是一次性信号，读取后清除
            if state.refresh_full:
                state.refresh_full = False

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
                "total": total,
                "level1": level1,
                "level2": level2,
                "level3": level3,
            }

        return {
            "scanning": scanning,
            "total": total,
            "ready": ready,
            "last_seq": last_seq,
            "progress": progress,
            "phase": phase,
            "refresh_full": refresh_full,
            "errors": errors,
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
            small_path = full_path.with_suffix(".small.jpg")
            if not small_path.exists() or small_path.stat().st_mtime < full_path.stat().st_mtime:
                small_bytes = thumbgen.make_small_jpeg(full_path.read_bytes())
                small_path.write_bytes(small_bytes)
            return ("image/jpeg", small_path.read_bytes())
        return ("image/jpeg", full_path.read_bytes())

    def get_frames_dir(self, video_id: str) -> Path | None:
        with self._lock:
            video_path = self._id_to_path.get(video_id)
        if video_path is None:
            return None
        cfg = config.load_config()
        root = find_root(video_path, cfg.video_path_list)
        if root is None:
            return None
        index_path, thumb_path = cache_index.video_cache_path(str(root), video_path)
        return framegen.get_frames_dir(thumb_path)

    def get_frame_status(self, video_id: str) -> dict | None:
        frames_dir = self.get_frames_dir(video_id)
        if frames_dir is None:
            return None
        status = framegen.read_status(frames_dir)
        if status is None:
            return {
                "status": "not_started",
                "total": framegen.FRAME_COUNT,
                "ready_count": 0,
                "frame_urls": [None] * framegen.FRAME_COUNT,
            }
        frame_urls = []
        for i in range(framegen.FRAME_COUNT):
            if (frames_dir / f"frame_{i:02d}.jpg").exists():
                frame_urls.append(f"/api/frames/{video_id}/{i}")
            else:
                frame_urls.append(None)
        return {
            "status": "ready" if not status.get("generating") else "generating",
            "total": status["total"],
            "ready_count": status["ready_count"],
            "frame_urls": frame_urls,
        }

    def generate_frames(self, video_id: str) -> bool:
        with self._lock:
            video_path = self._id_to_path.get(video_id)
        if video_path is None:
            return False
        frames_dir = self.get_frames_dir(video_id)
        if frames_dir is None:
            return False
        status = framegen.read_status(frames_dir)
        if status is not None:
            if not status.get("generating", False):
                return False
        with self._frame_generating_lock:
            if video_id in self._frame_generating:
                return False
            self._frame_generating.add(video_id)
        cfg = config.load_config()
        root = find_root(video_path, cfg.video_path_list)
        if root is None:
            with self._frame_generating_lock:
                self._frame_generating.discard(video_id)
            return False
        index_path, _ = cache_index.video_cache_path(str(root), video_path)
        videos = cache_index.load_index(index_path)
        duration = 0.0
        width = 0
        height = 0
        fname = Path(video_path).name
        for v in videos:
            if v.get("file_name") == fname:
                duration = float(v.get("duration") or 0)
                width = int(v.get("width") or 0)
                height = int(v.get("height") or 0)
                break

        def _run_and_cleanup():
            try:
                framegen.extract_all_frames(video_path, frames_dir, duration, width, height)
            finally:
                with self._frame_generating_lock:
                    self._frame_generating.discard(video_id)

        self._frame_executor.submit(_run_and_cleanup)
        return True

    def get_frame_jpeg(self, video_id: str, frame_index: int) -> bytes | None:
        frames_dir = self.get_frames_dir(video_id)
        if frames_dir is None:
            return None
        if frame_index < 0 or frame_index >= framegen.FRAME_COUNT:
            return None
        frame_path = frames_dir / f"frame_{frame_index:02d}.jpg"
        if not frame_path.exists():
            return None
        return frame_path.read_bytes()

    # ------------------------------------------------------------------
    # 任务进度跟踪（仅 build 任务使用）
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
        """返回所有运行中的任务进度（仅 build 任务）。"""
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
                self.ensure_scan(l2)
                state = self._get_l2_state(l2)
                while True:
                    with state.lock:
                        scanning = state.scanning
                    if not scanning:
                        break
                    state.done_event.wait(timeout=1.0)
                self._update_task(task_id, done=idx + 1)
        finally:
            task = self._get_task(task_id)
            if task:
                with task.lock:
                    task.running = False
            self._remove_task(task_id)


# 共享 Scanner 实例
_shared_scanner: Scanner | None = None


def get_shared_scanner() -> Scanner:
    global _shared_scanner
    if _shared_scanner is None:
        _shared_scanner = Scanner()
    return _shared_scanner
