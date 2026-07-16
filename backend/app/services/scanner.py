import os
import logging
import threading
import time
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
    """根据视频高度计算分辨率标签（4K/2K/FHD/HD/SD/LD）。

    从 probe.py 移出，由 scanner 在写入缓存时本地计算。
    前端也可独立计算（参见 VideoCard.vue formatResolution）。
    """
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


def _parse_filename(file_name: str, rules: list[dict]) -> dict | None:
    """对文件名应用解析规则，匹配成功返回 ext 字典。

    规则格式：{"name": "JAV", "pattern": "^(?P<code>[A-Z]+-?\\d+)..."}
    匹配成功的 named groups 成为 ext 字段的 key-value。

    使用带超时的 safe_match，避免用户提交的灾难性正则挂死扫描线程（H3）。
    """
    if not rules:
        return None
    for rule in rules:
        pattern = rule.get("pattern", "")
        if not pattern:
            continue
        m = safe_match(pattern, file_name, timeout=2.0)
        if m:
            ext = {k: v for k, v in m.groupdict().items() if v is not None}
            if ext:
                return ext
    return None


def _build_cache_entry(video_path: Path, item: dict, level: int,
                       thumb_file: str | None = None) -> dict:
    """构建扁平化的 index.yaml 条目。

    item 为扁平结构（无 meta 嵌套），与 API 响应一致。
    """
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
    # L2+ 元数据字段（直接从 item 读取，不再从 meta 嵌套读取）
    if level >= 2:
        entry["codec"] = item.get("codec")
        entry["width"] = item.get("width")
        entry["height"] = item.get("height")
        # 保留亚秒精度（L1）：round 到 3 位小数
        entry["duration"] = round(float(item.get("duration", 0) or 0), 3)
        entry["resolution_label"] = item.get("resolution_label")
    ext = item.get("ext")
    if ext:
        entry["ext"] = ext
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
    """将缓存条目中的元数据字段合并到扁平 item（原地修改）。

    缓存和 API 中 file_size 单位统一为 MB（整数）。
    """
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
        # 该 L2 目录是否已完整扫描到 L3（用于短路重复打开，M3）
        self.fully_scanned = False
        self.last_source_mtime = 0  # 完整扫描完成时记录的源目录最大 mtime
        # 扫描完成事件（供 build_worker 等待，替代忙等，I4）
        self.done_event = threading.Event()


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
        self._frame_executor = ThreadPoolExecutor(max_workers=2)

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
                # 同步清理该 L2 目录下视频的 id→path 映射，避免无限增长（M5）
                self._evict_id_to_path(old_path)
            return state

    def _evict_id_to_path(self, l2_path: str) -> None:
        """驱逐某个 L2 目录在 _id_to_path 中的条目（须持有 self._lock）。"""
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
        state = self._get_l2_state(l2_path)

        # 在锁内只做状态判断和线程启动，不调用 _build_*（避免重入）
        with state.lock:
            already_scanning = state.scanning
            # M3：已完整扫描且目录 mtime 未变 → 直接短路返回，避免重复全量扫描
            short_circuit = False
            if not already_scanning and state.fully_scanned:
                try:
                    cur_mtime = int(Path(l2_path).stat().st_mtime)
                    short_circuit = cur_mtime <= state.last_source_mtime
                except OSError:
                    short_circuit = False
            if not already_scanning and not short_circuit:
                state.scanning = True
                state.done_event.clear()
                t = threading.Thread(
                    target=self._scan_worker, args=(l2_path, state), daemon=True
                )
                t.start()

        # 锁已释放，安全调用 _build_*
        if not already_scanning and not short_circuit:
            # 新启动的扫描，短暂等待快速阶段填充数据（I5：保留较小等待，
            # 让首次响应即可携带 L1 数据；前端也会轮询补齐后续阶段）
            time.sleep(0.3)
        return self._build_groups(state), state.scanning, self._build_progress(state)

    def _scan_worker(self, l2_path: str, state: _L2State):
        scan_task_id = f"scan:{path_id.path_id(l2_path)}"
        completed = False
        try:
            cfg = config.load_config()  # 只加载一次，循环内复用（M2）
            root = find_root(l2_path, cfg.video_path_list)
            parse_rules = cfg.parse_rules

            # L2 目录 mtime，用于完成时记录、下次短路判定（M3）
            try:
                l2_mtime = int(Path(l2_path).stat().st_mtime)
            except OSError:
                l2_mtime = 0

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
                        item = {
                            "video_id": vid,
                            "file_name": video_path.name,
                            "file_size": int(video_path.stat().st_size / (1024 * 1024)),  # bytes → MB
                            "modify_time": source_mtime,
                            "group": self._group_name(str(video_path), l2_path),
                            "level": 3,
                        }
                        _apply_cache_to_item(item, cached)
                        if "ext" in cached:
                            item["ext"] = cached["ext"]
                        with state.lock:
                            state.seq += 1
                            item["seq"] = state.seq
                            state.videos[vid] = item
                        fully_cached_vids.add(vid)

            # ---------------------------------------------------------------
            # Phase L1 — 快速阶段：文件系统扫描，收集文件级信息
            # （跳过已完整缓存的视频）。index.yaml 按目录批量写一次（M4）。
            # ---------------------------------------------------------------
            l1_pending: dict[Path, list[dict]] = {}
            for video_path in video_paths:
                vid = path_id.path_id(str(video_path))
                if vid in fully_cached_vids:
                    continue

                group_name = self._group_name(str(video_path), l2_path)
                file_size = int(video_path.stat().st_size / (1024 * 1024))  # bytes → MB
                file_mtime = int(video_path.stat().st_mtime)

                item = {
                    "video_id": vid,
                    "file_name": video_path.name,
                    "file_size": file_size,  # MB
                    "modify_time": file_mtime,
                    "group": group_name,
                    "level": 1,
                }

                # 应用文件名解析规则（复用顶部加载的 cfg，M2）
                ext_data = _parse_filename(video_path.name, parse_rules)
                if ext_data:
                    item["ext"] = ext_data

                with state.lock:
                    state.seq += 1
                    item["seq"] = state.seq
                    state.videos[vid] = item

                # 收集到待写缓冲，稍后按目录批量落盘（M4）
                if root:
                    index_path, _ = cache_index.video_cache_path(str(root), str(video_path))
                    l1_pending.setdefault(index_path, []).append(
                        _build_cache_entry(video_path, item, level=1)
                    )

            if root:
                for ip, entries in l1_pending.items():
                    cache_index.upsert_many(ip, entries)

            # ---------------------------------------------------------------
            # Phase L2 — ffprobe 元数据。index.yaml 按目录批量写一次（M4）。
            # ---------------------------------------------------------------
            processed = 0  # H1：初始化，避免 probe 失败时 NameError
            l2_pending: dict[Path, list[dict]] = {}
            for video_path in video_paths:
                vid = path_id.path_id(str(video_path))

                with state.lock:
                    if state.videos.get(vid, {}).get("level", 1) >= 2:
                        continue

                probe_result = None
                try:
                    probe_result = probe.probe_video(str(video_path))
                except Exception:
                    probe_result = None

                with state.lock:
                    if vid in state.videos and probe_result is not None:
                        _merge_metadata(state.videos[vid], probe_result)
                        state.videos[vid]["level"] = 2
                        state.videos[vid]["_probe"] = probe_result
                        processed = sum(1 for v in state.videos.values() if v.get("level", 1) >= 2)
                self._update_task(scan_task_id, done=processed)

                # 收集到待写缓冲
                if root and probe_result is not None:
                    index_path, _ = cache_index.video_cache_path(str(root), str(video_path))
                    with state.lock:
                        item_snapshot = dict(state.videos.get(vid, {}))
                    item_snapshot["group"] = self._group_name(str(video_path), l2_path)
                    l2_pending.setdefault(index_path, []).append(
                        _build_cache_entry(video_path, item_snapshot, level=2)
                    )

            if root:
                for ip, entries in l2_pending.items():
                    cache_index.upsert_many(ip, entries)

            # ---------------------------------------------------------------
            # Phase L3 — 缩略图提取。index.yaml 按目录批量写一次（M4）。
            # ---------------------------------------------------------------
            l3_pending: dict[Path, list[dict]] = {}
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
                # 写 JPEG（磁盘 I/O，在锁外）
                thumb_path.write_bytes(png_bytes)

                # 锁内：只更新内存 level，并快照所需字段
                with state.lock:
                    entry_snapshot = None
                    if vid in state.videos:
                        state.videos[vid]["level"] = 3
                        state.videos[vid].pop("_probe", None)
                        entry_snapshot = dict(state.videos[vid])

                # 收集到待写缓冲
                if entry_snapshot:
                    l3_pending.setdefault(index_path, []).append(
                        _build_cache_entry(
                            video_path, entry_snapshot, level=3, thumb_file=thumb_path.name
                        )
                    )

            if root:
                for ip, entries in l3_pending.items():
                    cache_index.upsert_many(ip, entries)

            completed = True

        except Exception:
            # H2：记录扫描失败，避免静默中止（原本只 try/finally）
            logger.exception("scan worker failed for %s", l2_path)
        finally:
            with state.lock:
                state.scanning = False
                # M3：完整完成才标记 fully_scanned（异常时不标记，下次重扫）
                if completed:
                    state.fully_scanned = True
                    state.last_source_mtime = l2_mtime
                # 清理残留的临时 _probe 字段
                for entry in state.videos.values():
                    entry.pop("_probe", None)
            state.done_event.set()  # I4：通知等待者
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
                    # 扁平更新条目：基础字段 + 可选元数据字段
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
                    # L2+ 元数据字段
                    if item.get("level", 1) >= 2 and item.get("codec"):
                        entry["codec"] = item["codec"]
                        entry["width"] = item.get("width")
                        entry["height"] = item.get("height")
                        entry["duration"] = item.get("duration")
                        entry["resolution_label"] = item.get("resolution_label")
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

    def get_frames_dir(self, video_id: str) -> Path | None:
        """返回视频帧目录路径。video_id 未知时返回 None。"""
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
        """返回帧抽取状态。video_id 未知时返回 None。"""
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
        # 构建 frame_urls
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
        """触发异步帧抽取。已在生成中或已完成时返回 False。"""
        with self._lock:
            video_path = self._id_to_path.get(video_id)
        if video_path is None:
            return False
        frames_dir = self.get_frames_dir(video_id)
        if frames_dir is None:
            return False

        # 检查状态：已完成或正在生成则跳过
        status = framegen.read_status(frames_dir)
        if status is not None:
            if not status.get("generating", False):
                return False  # 已完成
            return False  # 正在生成中

        # 提交到线程池
        cfg = config.load_config()
        root = find_root(video_path, cfg.video_path_list)
        if root is None:
            return False
        index_path, _ = cache_index.video_cache_path(str(root), video_path)
        # 从 index.yaml 读取 duration
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

        self._frame_executor.submit(
            framegen.extract_all_frames,
            video_path, frames_dir, duration, width, height,
        )
        return True

    def get_frame_jpeg(self, video_id: str, frame_index: int) -> bytes | None:
        """返回指定帧的 JPEG bytes。不存在返回 None。"""
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
                # 等待该目录扫描完成（I4：用 Event 替代忙等）
                state = self._get_l2_state(l2)
                while True:
                    with state.lock:
                        scanning = state.scanning
                    if not scanning:
                        break
                    # 等待事件或超时重检（避免长时间持锁/忙轮询）
                    state.done_event.wait(timeout=1.0)
                self._update_task(task_id, done=idx + 1)
        finally:
            task = self._get_task(task_id)
            if task:
                with task.lock:
                    task.running = False
            self._remove_task(task_id)
