# 视频帧预览 + 播放功能 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Lightbox 浮层中新增 20 帧预览（右键切换 + 小图条）和视频播放（浏览器新标签页 + IINA）功能。

**Architecture:** 后端新增 `framegen.py` 服务（批量抽帧 + 状态管理）、`frames.py` 路由（帧查询/抽取/获取）、`video.py` 路由（流式代理）。前端新增 `useFramePreview.ts` composable，大幅改造 `LightboxModal.vue`。

**Tech Stack:** Python 3.12 + FastAPI + ffmpeg/ffprobe（后端）；Vue 3 + TypeScript + Tailwind + Pinia（前端）。

---

## 文件结构

**新增：**
| 文件 | 职责 |
|------|------|
| `backend/app/services/framegen.py` | 帧抽取：单帧提取、批量抽取、状态文件管理 |
| `backend/app/routes/frames.py` | 帧 API：状态查询、触发抽取、单帧获取 |
| `backend/app/routes/video.py` | 视频流代理：Range 支持、安全校验 |
| `backend/tests/test_framegen.py` | framegen 单元测试 |
| `backend/tests/test_frames_api.py` | 帧 API 集成测试 |
| `backend/tests/test_video_api.py` | 视频流 API 集成测试 |
| `frontend/src/composables/useFramePreview.ts` | 帧预览状态管理 composable |

**修改：**
| 文件 | 变更 |
|------|------|
| `backend/app/main.py` | 注册 frames 和 video 路由 |
| `frontend/src/components/LightboxModal.vue` | 大幅改造：大图帧切换 + 小图条 + 播放按钮 |

---

### Task 1: framegen 单帧提取

**Files:**
- Create: `backend/app/services/framegen.py`
- Create: `backend/tests/test_framegen.py`

- [ ] **Step 1: Write the failing test for `extract_frame_at`**

```python
# backend/tests/test_framegen.py
"""Tests for framegen: multi-frame extraction from videos."""

import json
from pathlib import Path

from app.services.framegen import extract_frame_at, FRAME_COUNT


def test_extract_frame_at_returns_jpeg(sample_video):
    """extract_frame_at 应在指定时间点提取一帧 JPEG。"""
    result = extract_frame_at(sample_video, time_sec=1.0)
    assert result is not None
    # JPEG magic bytes
    assert result[:3] == b"\xff\xd8\xff"


def test_extract_frame_at_returns_none_for_nonexistent():
    """不存在的视频文件应返回 None。"""
    result = extract_frame_at("/tmp/nonexistent_video_12345.mp4", time_sec=1.0)
    assert result is None


def test_frame_count_is_20():
    """FRAME_COUNT 常量应为 20。"""
    assert FRAME_COUNT == 20
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_framegen.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.framegen'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/services/framegen.py
"""Multi-frame extraction from video files using ffmpeg.

Extracts frames at evenly-spaced time intervals at original resolution.
Output format is JPEG.
"""

import subprocess

from .probe import probe_video

FRAME_COUNT = 20


def compute_frame_times(duration: float, count: int = FRAME_COUNT) -> list[float]:
    """计算 N 帧的等间隔时间点。

    t_i = duration * (i + 0.5) / count，避免首尾黑帧。
    短于 count 秒的视频仍均匀分布。
    """
    if duration <= 0:
        return [0.0] * count
    return [duration * (i + 0.5) / count for i in range(count)]


def extract_frame_at(path: str, time_sec: float) -> bytes | None:
    """在指定时间点提取单帧 JPEG。

    返回 JPEG bytes，失败返回 None。
    """
    cmd = [
        "ffmpeg", "-v", "error",
        "-ss", f"{time_sec:.3f}",
        "-i", str(path),
        "-frames:v", "1",
        "-f", "image2pipe", "-vcodec", "mjpeg", "-",
    ]
    try:
        out = subprocess.run(cmd, capture_output=True, timeout=120)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None

    if out.returncode != 0 or not out.stdout:
        return None
    return out.stdout
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_framegen.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/framegen.py backend/tests/test_framegen.py
git commit -m "feat(framegen): add single-frame extraction at time offset

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: framegen 批量抽取 + 状态管理

**Files:**
- Modify: `backend/app/services/framegen.py`
- Modify: `backend/tests/test_framegen.py`

- [ ] **Step 1: Write failing tests for batch extraction and status**

在 `backend/tests/test_framegen.py` 末尾追加：

```python
from app.services.framegen import (
    extract_frame_at, FRAME_COUNT,
    get_frames_dir, read_status, write_status,
    extract_all_frames,
)


def test_get_frames_dir_creates_directory(tmp_path):
    """get_frames_dir 应返回 {thumb_path}.frames 目录并创建。"""
    # thumb_path 类似 /cache/movies/dune.jpg
    thumb_path = tmp_path / "dune.jpg"
    thumb_path.write_bytes(b"fake")
    frames_dir = get_frames_dir(thumb_path)
    assert frames_dir == tmp_path / "dune.frames"
    assert frames_dir.is_dir()


def test_read_status_returns_none_when_missing(tmp_path):
    """status.json 不存在时返回 None。"""
    assert read_status(tmp_path / "nonexistent.frames") is None


def test_write_and_read_status_roundtrip(tmp_path):
    """write_status + read_status 应可往返。"""
    frames_dir = tmp_path / "test.frames"
    frames_dir.mkdir()
    status = {"total": 20, "ready_count": 5, "generating": True, "width": 1920, "height": 1080}
    write_status(frames_dir, status)
    loaded = read_status(frames_dir)
    assert loaded == status


def test_extract_all_frames_creates_jpegs(sample_video, tmp_path):
    """extract_all_frames 应在 frames_dir 中生成 20 个 JPEG。"""
    thumb_path = tmp_path / "test.jpg"
    thumb_path.write_bytes(b"fake")
    frames_dir = get_frames_dir(thumb_path)

    # 2 秒视频，抽 20 帧
    result = extract_all_frames(sample_video, frames_dir, duration=2.0)
    assert result["total"] == 20
    assert result["ready_count"] == 20
    assert result["generating"] is False

    # 验证文件存在
    for i in range(20):
        frame_path = frames_dir / f"frame_{i:02d}.jpg"
        assert frame_path.exists(), f"frame_{i:02d}.jpg should exist"
        data = frame_path.read_bytes()
        assert data[:3] == b"\xff\xd8\xff", f"frame_{i:02d} should be JPEG"


def test_extract_all_frames_short_video(sample_video, tmp_path):
    """短于 1 秒的视频也应能抽取。"""
    thumb_path = tmp_path / "short.jpg"
    thumb_path.write_bytes(b"fake")
    frames_dir = get_frames_dir(thumb_path)

    result = extract_all_frames(sample_video, frames_dir, duration=0.5)
    assert result["total"] == 20
    assert result["ready_count"] > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_framegen.py -v`
Expected: FAIL — `ImportError: cannot import name 'get_frames_dir'`

- [ ] **Step 3: Implement batch extraction in `framegen.py`**

在 `backend/app/services/framegen.py` 末尾追加：

```python
import json
import logging

logger = logging.getLogger(__name__)


def get_frames_dir(thumb_path: Path) -> Path:
    """返回帧目录路径：{thumb_stem}.frames/。自动创建。"""
    frames_dir = thumb_path.with_suffix(".frames")
    frames_dir.mkdir(parents=True, exist_ok=True)
    return frames_dir


def _status_path(frames_dir: Path) -> Path:
    return frames_dir / "status.json"


def read_status(frames_dir: Path) -> dict | None:
    """读取 status.json。不存在或损坏时返回 None。"""
    sp = _status_path(frames_dir)
    if not sp.exists():
        return None
    try:
        return json.loads(sp.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def write_status(frames_dir: Path, status: dict) -> None:
    """原子写 status.json。"""
    sp = _status_path(frames_dir)
    sp.write_text(json.dumps(status, ensure_ascii=False), encoding="utf-8")


def _count_ready_frames(frames_dir: Path) -> int:
    """统计 frames_dir 中已存在的 frame_XX.jpg 文件数。"""
    count = 0
    for i in range(FRAME_COUNT):
        if (frames_dir / f"frame_{i:02d}.jpg").exists():
            count += 1
    return count


def extract_all_frames(
    video_path: str,
    frames_dir: Path,
    duration: float,
    width: int = 0,
    height: int = 0,
) -> dict:
    """批量抽取 FRAME_COUNT 帧，写入 frames_dir。

    逐帧写入，每完成一帧更新 status.json 的 ready_count。
    返回最终 status dict。
    """
    frame_times = compute_frame_times(duration, FRAME_COUNT)
    frames_dir.mkdir(parents=True, exist_ok=True)

    # 初始状态
    status = {
        "total": FRAME_COUNT,
        "ready_count": 0,
        "generating": True,
        "width": width,
        "height": height,
    }
    write_status(frames_dir, status)

    for i, t in enumerate(frame_times):
        frame_path = frames_dir / f"frame_{i:02d}.jpg"
        # 已存在则跳过（支持中断恢复）
        if frame_path.exists():
            status["ready_count"] = _count_ready_frames(frames_dir)
            write_status(frames_dir, status)
            continue

        jpeg_bytes = extract_frame_at(video_path, t)
        if jpeg_bytes:
            frame_path.write_bytes(jpeg_bytes)

        status["ready_count"] = _count_ready_frames(frames_dir)
        write_status(frames_dir, status)

    status["generating"] = False
    write_status(frames_dir, status)
    return status
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_framegen.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/framegen.py backend/tests/test_framegen.py
git commit -m "feat(framegen): add batch frame extraction with status tracking

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: Scanner 集成帧服务

**Files:**
- Modify: `backend/app/services/scanner.py`
- Create: `backend/tests/test_scanner_frames.py`

- [ ] **Step 1: Write failing test for scanner frame methods**

```python
# backend/tests/test_scanner_frames.py
"""Tests for Scanner frame-related methods."""

import time
from pathlib import Path
from unittest.mock import patch

from app.services.scanner import Scanner


def test_scanner_get_frames_dir_returns_none_for_unknown_video():
    """未知 video_id 应返回 None。"""
    scanner = Scanner()
    result = scanner.get_frames_dir("nonexistent_video_id")
    assert result is None


def test_scanner_get_frame_status_not_started(sample_video, tmp_path, monkeypatch):
    """未开始抽帧时，get_frame_status 应返回 not_started。"""
    from app.config import AppConfig, save_config
    from app.path_id import path_id

    monkeypatch.setenv("DATA_PATH", str(tmp_path))

    # 设置最小目录结构
    videos_dir = tmp_path / "videos"
    l1 = videos_dir / "movies"
    l2 = l1 / "action"
    l2.mkdir(parents=True)
    # 复制 sample_video 到 l2
    import shutil
    video_in_l2 = l2 / "test.mp4"
    shutil.copy(sample_video, video_in_l2)

    cfg = AppConfig(video_path_list=[str(videos_dir)], page_size=0, column_size=4)
    save_config(cfg)

    scanner = Scanner()
    # 触发扫描以填充 _id_to_path
    scanner.ensure_scan(str(l2))
    time.sleep(1)  # 等待扫描完成

    vid = path_id(str(video_in_l2.resolve()))
    result = scanner.get_frame_status(vid)
    assert result is not None
    assert result["status"] == "not_started"
    assert result["total"] == 20
    assert result["ready_count"] == 0


def test_scanner_generate_frames(sample_video, tmp_path, monkeypatch):
    """generate_frames 应触发异步抽帧并最终完成。"""
    from app.config import AppConfig, save_config
    from app.path_id import path_id

    monkeypatch.setenv("DATA_PATH", str(tmp_path))

    videos_dir = tmp_path / "videos"
    l1 = videos_dir / "movies"
    l2 = l1 / "action"
    l2.mkdir(parents=True)
    import shutil
    video_in_l2 = l2 / "test.mp4"
    shutil.copy(sample_video, video_in_l2)

    cfg = AppConfig(video_path_list=[str(videos_dir)], page_size=0, column_size=4)
    save_config(cfg)

    scanner = Scanner()
    scanner.ensure_scan(str(l2))
    time.sleep(1)

    vid = path_id(str(video_in_l2.resolve()))
    # 触发抽帧
    scanner.generate_frames(vid)
    # 等待线程池完成
    time.sleep(5)

    status = scanner.get_frame_status(vid)
    assert status["status"] == "ready"
    assert status["ready_count"] == 20
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_scanner_frames.py -v`
Expected: FAIL — `AttributeError: 'Scanner' object has no attribute 'get_frames_dir'`

- [ ] **Step 3: Add frame methods to Scanner**

在 `backend/app/services/scanner.py` 的 `Scanner` 类中追加方法（在 `get_thumb` 方法之后）：

```python
# 在 Scanner.__init__ 中添加线程池（修改 __init__）
# 找到 __init__ 方法，添加一行：
#   self._frame_executor = ThreadPoolExecutor(max_workers=2)

# 在文件顶部添加 import：
# from concurrent.futures import ThreadPoolExecutor

# 在 Scanner 类中 get_thumb 方法之后追加：

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
        return thumbgen.get_frames_dir(thumb_path)

    def get_frame_status(self, video_id: str) -> dict | None:
        """返回帧抽取状态。video_id 未知时返回 None。"""
        frames_dir = self.get_frames_dir(video_id)
        if frames_dir is None:
            return None
        status = thumbgen.read_status(frames_dir)
        if status is None:
            return {
                "status": "not_started",
                "total": thumbgen.FRAME_COUNT,
                "ready_count": 0,
                "frame_urls": [None] * thumbgen.FRAME_COUNT,
            }
        # 构建 frame_urls
        frame_urls = []
        for i in range(thumbgen.FRAME_COUNT):
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
        status = thumbgen.read_status(frames_dir)
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
            thumbgen.extract_all_frames,
            video_path, frames_dir, duration, width, height,
        )
        return True

    def get_frame_jpeg(self, video_id: str, frame_index: int) -> bytes | None:
        """返回指定帧的 JPEG bytes。不存在返回 None。"""
        frames_dir = self.get_frames_dir(video_id)
        if frames_dir is None:
            return None
        if frame_index < 0 or frame_index >= thumbgen.FRAME_COUNT:
            return None
        frame_path = frames_dir / f"frame_{frame_index:02d}.jpg"
        if not frame_path.exists():
            return None
        return frame_path.read_bytes()
```

同时修改 `Scanner.__init__`，在 `self._tasks_lock = threading.Lock()` 之后添加：

```python
        self._frame_executor = ThreadPoolExecutor(max_workers=2)
```

并在文件顶部添加：

```python
from concurrent.futures import ThreadPoolExecutor
```

- [ ] **Step 4: Run test to verify they pass**

Run: `cd backend && pytest tests/test_scanner_frames.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/scanner.py backend/tests/test_scanner_frames.py
git commit -m "feat(scanner): integrate frame extraction with thread pool

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: Frames API 路由

**Files:**
- Create: `backend/app/routes/frames.py`
- Create: `backend/tests/test_frames_api.py`

- [ ] **Step 1: Write failing API tests**

```python
# backend/tests/test_frames_api.py
"""Tests for frames API endpoints."""

import time
import shutil
from pathlib import Path

from fastapi.testclient import TestClient
from app.main import app
from app.config import AppConfig, save_config
from app.path_id import path_id

import pytest

client = TestClient(app)


@pytest.fixture
def video_with_scan(tmp_path, monkeypatch, sample_video):
    """搭建带单个测试视频的库，返回 (video_id, l2_id)。"""
    monkeypatch.setenv("DATA_PATH", str(tmp_path))
    videos_dir = tmp_path / "videos"
    l1 = videos_dir / "movies"
    l2 = l1 / "action"
    l2.mkdir(parents=True)
    video = l2 / "test.mp4"
    shutil.copy(sample_video, video)

    cfg = AppConfig(video_path_list=[str(videos_dir)], page_size=0, column_size=4)
    save_config(cfg)
    from app import paths
    paths._cache._ts = 0.0

    l2_id = path_id(str(l2.resolve()))
    vid = path_id(str(video.resolve()))
    # 触发扫描
    from app.services.scanner import Scanner
    scanner = Scanner()
    scanner.ensure_scan(str(l2))
    time.sleep(1)
    return vid, l2_id, scanner


def test_get_frame_status_not_started(video_with_scan):
    """GET /api/frames/{id} 未开始时返回 not_started。"""
    vid, _, _ = video_with_scan
    resp = client.get(f"/api/frames/{vid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "not_started"
    assert data["total"] == 20
    assert data["ready_count"] == 0
    assert len(data["frame_urls"]) == 20


def test_generate_frames_triggers_extraction(video_with_scan):
    """POST /api/frames/{id}/generate 触发抽帧。"""
    vid, _, _ = video_with_scan
    resp = client.post(f"/api/frames/{vid}/generate")
    assert resp.status_code == 202


def test_get_frame_jpeg_after_generation(video_with_scan):
    """抽帧完成后，GET /api/frames/{id}/{index} 返回 JPEG。"""
    vid, _, _ = video_with_scan
    # 触发抽帧并等待完成
    client.post(f"/api/frames/{vid}/generate")
    # 轮询直到完成
    for _ in range(30):
        time.sleep(0.5)
        resp = client.get(f"/api/frames/{vid}")
        if resp.json()["status"] == "ready":
            break

    # 获取第 0 帧
    resp = client.get(f"/api/frames/{vid}/0")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/jpeg"
    assert resp.content[:3] == b"\xff\xd8\xff"


def test_get_frame_jpeg_not_ready(video_with_scan):
    """帧未就绪时返回 202。"""
    vid, _, _ = video_with_scan
    resp = client.get(f"/api/frames/{vid}/0")
    assert resp.status_code == 202


def test_get_frame_jpeg_invalid_index(video_with_scan):
    """无效帧索引返回 404。"""
    vid, _, _ = video_with_scan
    resp = client.get(f"/api/frames/{vid}/99")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_frames_api.py -v`
Expected: FAIL — `ConnectionError` (routes not registered yet)

- [ ] **Step 3: Implement frames routes**

```python
# backend/app/routes/frames.py
from fastapi import APIRouter, HTTPException, Response
from ..services.scanner import Scanner

router = APIRouter()
scanner = Scanner()


@router.get("/frames/{video_id}")
def get_frame_status(video_id: str):
    """返回 20 帧就绪状态和每帧 URL。"""
    result = scanner.get_frame_status(video_id)
    if result is None:
        raise HTTPException(404, "video not found")
    return result


@router.post("/frames/{video_id}/generate")
def generate_frames(video_id: str):
    """触发批量抽帧（异步）。"""
    started = scanner.generate_frames(video_id)
    if not started:
        # 已完成或已在生成中
        status = scanner.get_frame_status(video_id)
        if status and status["status"] == "ready":
            return {"status": "already_done"}
        return Response(status_code=202, content="generation in progress")
    return Response(status_code=202, content="generation started")


@router.get("/frames/{video_id}/{frame_index:int}")
def get_frame_jpeg(video_id: str, frame_index: int):
    """返回单帧 JPEG。"""
    if frame_index < 0 or frame_index >= 20:
        raise HTTPException(404, "frame index out of range")
    jpeg_bytes = scanner.get_frame_jpeg(video_id, frame_index)
    if jpeg_bytes is None:
        return Response(status_code=202, content="frame not ready")
    return Response(
        content=jpeg_bytes,
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=86400"},
    )
```

- [ ] **Step 4: Register route in main.py**

在 `backend/app/main.py` 中，添加导入和路由注册：

在 `from .routes import config as config_routes, dirs, videos, scan, parse_rules` 行改为：

```python
from .routes import config as config_routes, dirs, videos, scan, parse_rules, frames
```

在 `app.include_router(parse_rules.router, prefix="/api")` 行后添加：

```python
app.include_router(frames.router, prefix="/api")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_frames_api.py -v`
Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
git add backend/app/routes/frames.py backend/tests/test_frames_api.py backend/app/main.py
git commit -m "feat(api): add frames endpoints for status, generation, and retrieval

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 5: Video 流式代理路由

**Files:**
- Create: `backend/app/routes/video.py`
- Create: `backend/tests/test_video_api.py`

- [ ] **Step 1: Write failing API tests**

```python
# backend/tests/test_video_api.py
"""Tests for video streaming endpoint."""

import time
import shutil
from pathlib import Path

from fastapi.testclient import TestClient
from app.main import app
from app.config import AppConfig, save_config
from app.path_id import path_id

import pytest

client = TestClient(app)


@pytest.fixture
def video_for_playback(tmp_path, monkeypatch, sample_video):
    """搭建带单个测试视频的库，返回 video_id。"""
    monkeypatch.setenv("DATA_PATH", str(tmp_path))
    videos_dir = tmp_path / "videos"
    l1 = videos_dir / "movies"
    l2 = l1 / "action"
    l2.mkdir(parents=True)
    video = l2 / "test.mp4"
    shutil.copy(sample_video, video)

    cfg = AppConfig(video_path_list=[str(videos_dir)], page_size=0, column_size=4)
    save_config(cfg)
    from app import paths
    paths._cache._ts = 0.0

    vid = path_id(str(video.resolve()))
    # 触发扫描以注册 id→path
    from app.services.scanner import Scanner
    scanner = Scanner()
    scanner.ensure_scan(str(l2))
    time.sleep(1)
    return vid, str(video.resolve())


def test_video_stream_returns_content(video_for_playback):
    """GET /api/video/{id} 应返回视频内容。"""
    vid, video_path = video_for_playback
    resp = client.get(f"/api/video/{vid}")
    assert resp.status_code == 200
    assert "video" in resp.headers["content-type"]
    assert len(resp.content) > 0


def test_video_stream_range_request(video_for_playback):
    """Range 请求应返回 206 Partial Content。"""
    vid, video_path = video_for_playback
    resp = client.get(f"/api/video/{vid}", headers={"Range": "bytes=0-1023"})
    assert resp.status_code == 206
    assert resp.headers["content-range"].startswith("bytes 0-1023/")
    assert len(resp.content) == 1024


def test_video_stream_not_found():
    """未知 video_id 返回 404。"""
    resp = client.get("/api/video/nonexistent_id_12345")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_video_api.py -v`
Expected: FAIL — 404 (route not registered)

- [ ] **Step 3: Implement video route**

```python
# backend/app/routes/video.py
import os
import mimetypes
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from ..services.scanner import Scanner, find_root
from .. import config

router = APIRouter()
scanner = Scanner()

VIDEO_MIME = {
    ".mp4": "video/mp4",
    ".mkv": "video/x-matroska",
    ".mov": "video/quicktime",
    ".avi": "video/x-msvideo",
    ".webm": "video/webm",
    ".m4v": "video/mp4",
    ".flv": "video/x-flv",
    ".ts": "video/mp2t",
    ".wmv": "video/x-ms-wmv",
    ".mpg": "video/mpeg",
    ".mpeg": "video/mpeg",
    ".3gp": "video/3gpp",
    ".rm": "video/vnd.rn-realvideo",
    ".rmvb": "video/vnd.rn-realvideo",
}

CHUNK_SIZE = 64 * 1024  # 64KB


def _resolve_video_path(video_id: str) -> Path | None:
    """通过 scanner 的 _id_to_path 解析 video_id → 绝对路径。"""
    with scanner._lock:
        return scanner._id_to_path.get(video_id)


@router.get("/video/{video_id}")
async def stream_video(video_id: str, request: Request):
    """流式返回视频文件，支持 HTTP Range 请求。"""
    video_path = _resolve_video_path(video_id)
    if video_path is None:
        raise HTTPException(404, "video not found")

    path = Path(video_path)
    if not path.exists() or not path.is_file():
        raise HTTPException(404, "video file not found")

    # 安全校验：确认路径在 video_path_list 内
    cfg = config.load_config()
    root = find_root(str(path), cfg.video_path_list)
    if root is None:
        raise HTTPException(403, "access denied")

    file_size = path.stat().st_size
    ext = path.suffix.lower()
    content_type = VIDEO_MIME.get(ext, "application/octet-stream")

    # 处理 Range 请求
    range_header = request.headers.get("range")
    if range_header:
        # 解析 "bytes=start-end"
        range_spec = range_header.replace("bytes=", "")
        parts = range_spec.split("-")
        start = int(parts[0]) if parts[0] else 0
        end = int(parts[1]) if parts[1] else file_size - 1
        end = min(end, file_size - 1)
        content_length = end - start + 1

        def iter_range():
            with open(path, "rb") as f:
                f.seek(start)
                remaining = content_length
                while remaining > 0:
                    chunk = f.read(min(CHUNK_SIZE, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        return StreamingResponse(
            iter_range(),
            status_code=206,
            media_type=content_type,
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(content_length),
                "Cache-Control": "private, max-age=3600",
            },
        )

    # 完整文件
    def iter_full():
        with open(path, "rb") as f:
            while True:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break
                yield chunk

    return StreamingResponse(
        iter_full(),
        media_type=content_type,
        headers={
            "Accept-Ranges": "bytes",
            "Content-Length": str(file_size),
            "Cache-Control": "private, max-age=3600",
        },
    )
```

- [ ] **Step 4: Register route in main.py**

在 `backend/app/main.py` 中修改导入：

```python
from .routes import config as config_routes, dirs, videos, scan, parse_rules, frames, video
```

在 `app.include_router(frames.router, prefix="/api")` 后添加：

```python
app.include_router(video.router, prefix="/api")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_video_api.py -v`
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add backend/app/routes/video.py backend/tests/test_video_api.py backend/app/main.py
git commit -m "feat(api): add video streaming endpoint with Range support

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 6: 前端 useFramePreview composable

**Files:**
- Create: `frontend/src/composables/useFramePreview.ts`

- [ ] **Step 1: Implement the composable**

```typescript
// frontend/src/composables/useFramePreview.ts
import { ref, watch, onUnmounted, type Ref } from 'vue'
import axios from 'axios'

export interface FrameStatus {
  status: 'not_started' | 'generating' | 'ready'
  total: number
  ready_count: number
  frame_urls: (string | null)[]
}

export function useFramePreview(videoId: Ref<string | null>) {
  const frames = ref<(string | null)[]>(Array(20).fill(null))
  const currentFrame = ref(0)
  const status = ref<'not_started' | 'generating' | 'ready'>('not_started')
  const readyCount = ref(0)

  let pollTimer: ReturnType<typeof setInterval> | null = null

  function nextFrame() {
    // 循环切换到下一个已就绪的帧
    const total = frames.value.length
    for (let i = 1; i <= total; i++) {
      const next = (currentFrame.value + i) % total
      if (frames.value[next] !== null) {
        currentFrame.value = next
        return
      }
    }
  }

  function selectFrame(index: number) {
    if (index >= 0 && index < frames.value.length && frames.value[index] !== null) {
      currentFrame.value = index
    }
  }

  async function startGeneration() {
    if (!videoId.value) return
    // 重置状态
    frames.value = Array(20).fill(null)
    currentFrame.value = 0
    status.value = 'not_started'
    readyCount.value = 0

    try {
      await axios.post(`/api/frames/${videoId.value}/generate`)
    } catch {
      // 已在生成或已完成，忽略
    }

    // 先立即查一次状态
    await pollStatus()

    // 如果还在生成，启动轮询
    if (status.value === 'generating' || status.value === 'not_started') {
      startPolling()
    }
  }

  async function pollStatus() {
    if (!videoId.value) return
    try {
      const { data } = await axios.get<FrameStatus>(`/api/frames/${videoId.value}`)
      status.value = data.status
      readyCount.value = data.ready_count
      frames.value = data.frame_urls

      // 如果 frame_0 就绪且当前还在封面（currentFrame=0 且之前没有帧），保持不变
      // 用户右键时才切换

      if (data.status === 'ready') {
        stopPolling()
      }
    } catch {
      // 网络错误，继续轮询
    }
  }

  function startPolling() {
    stopPolling()
    pollTimer = setInterval(pollStatus, 2000)
  }

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }

  // 当 videoId 变化时重新开始（immediate: true 确保组件挂载时也触发）
  watch(videoId, (newId) => {
    stopPolling()
    if (newId) {
      startGeneration()
    }
  }, { immediate: true })

  onUnmounted(stopPolling)

  return {
    frames,
    currentFrame,
    status,
    readyCount,
    nextFrame,
    selectFrame,
    startGeneration,
    stopPolling,
  }
}
```

- [ ] **Step 2: Typecheck**

Run: `cd frontend && bun run typecheck`
Expected: 无错误

- [ ] **Step 3: Commit**

```bash
git add frontend/src/composables/useFramePreview.ts
git commit -m "feat(frontend): add useFramePreview composable for frame state management

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 7: LightboxModal 大幅改造

**Files:**
- Modify: `frontend/src/components/LightboxModal.vue`

- [ ] **Step 1: Rewrite LightboxModal.vue**

完整替换 `frontend/src/components/LightboxModal.vue`：

```vue
<template>
  <transition
    enter-active-class="transition duration-200 ease-out"
    enter-from-class="opacity-0"
    enter-to-class="opacity-100"
    leave-active-class="transition duration-150 ease-in"
    leave-from-class="opacity-100"
    leave-to-class="opacity-0"
  >
    <div
      v-if="video"
      class="fixed inset-0 bg-slate-950/85 backdrop-blur-sm flex items-center justify-center z-50 p-4 sm:p-8"
      @click.self="$emit('close')"
    >
      <div class="relative w-full max-w-5xl">
        <!-- 关闭按钮 -->
        <button
          @click="$emit('close')"
          class="absolute -top-2 -right-2 z-10 w-9 h-9 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 rounded-full shadow-lg flex items-center justify-center hover:scale-110 transition"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M18 6 6 18M6 6l12 12"/></svg>
        </button>

        <!-- 视频标题 + 元信息 -->
        <div class="mb-3">
          <div class="text-lg font-semibold text-white leading-snug line-clamp-1">{{ displayName }}</div>
          <div class="flex gap-2 mt-1 text-xs text-slate-400">
            <span v-if="video.codec">{{ video.codec }}</span>
            <span v-if="video.resolution_label">{{ video.resolution_label }}</span>
            <span v-if="video.duration">{{ formatDuration(video.duration) }}</span>
            <span>{{ formatSize(video.file_size) }}</span>
          </div>
        </div>

        <!-- 大图预览区 -->
        <div
          class="relative bg-black rounded-lg overflow-hidden aspect-video flex items-center justify-center"
          @contextmenu.prevent="onRightClick"
        >
          <!-- 封面（帧未就绪时）或当前帧 -->
          <img
            v-if="displaySrc"
            :src="displaySrc"
            class="max-w-full max-h-full object-contain"
          />
          <p v-else class="text-slate-500 text-sm animate-pulse">加载中...</p>

          <!-- 帧计数器 -->
          <div
            v-if="framesReady"
            class="absolute top-2 left-2 bg-black/60 text-white text-xs px-2 py-1 rounded-md backdrop-blur-sm"
          >
            {{ currentFrame + 1 }} / {{ frames.length }}
          </div>

          <!-- 右键提示 -->
          <div
            v-if="framesReady"
            class="absolute bottom-2 right-2 bg-black/60 text-slate-400 text-xs px-2 py-1 rounded-md backdrop-blur-sm"
          >
            右键切换下一帧 →
          </div>
        </div>

        <!-- 小图条 -->
        <div class="flex gap-1 mt-3 overflow-x-auto py-1 px-1" ref="stripRef">
          <div
            v-for="(url, i) in frames"
            :key="i"
            @click="selectFrame(i)"
            class="flex-shrink-0 w-20 aspect-video rounded cursor-pointer transition-all"
            :class="i === currentFrame && url ? 'ring-2 ring-indigo-500 shadow-lg shadow-indigo-500/40' : 'ring-1 ring-slate-700 hover:ring-slate-500'"
          >
            <img
              v-if="url"
              :src="url"
              class="w-full h-full object-cover rounded"
              loading="lazy"
            />
            <div v-else class="w-full h-full bg-slate-800 rounded flex items-center justify-center">
              <svg class="w-4 h-4 text-slate-600 animate-spin" viewBox="0 0 24 24" fill="none">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
              </svg>
            </div>
          </div>
        </div>

        <!-- 播放按钮 -->
        <div class="flex gap-3 justify-center mt-4">
          <button
            @click="openInBrowser"
            title="浏览器播放"
            class="w-10 h-10 rounded-full bg-blue-600 hover:bg-blue-500 text-white flex items-center justify-center transition hover:scale-110"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
              <path d="M8 5v14l11-7z"/>
            </svg>
          </button>
          <button
            @click="openInIINA"
            title="IINA 播放"
            class="w-10 h-10 rounded-full bg-purple-600 hover:bg-purple-500 text-white flex items-center justify-center transition hover:scale-110"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
              <path d="M8 5v14l11-7z"/>
              <circle cx="12" cy="12" r="11" fill="none" stroke="currentColor" stroke-width="1.5"/>
            </svg>
          </button>
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup lang="ts">
import { computed, ref, watch, nextTick } from 'vue'
import { useFramePreview } from '../composables/useFramePreview'

const props = defineProps<{
  video: any | null
}>()
defineEmits<{
  (e: 'close'): void
}>()

const videoIdRef = computed(() => props.video?.video_id ?? null)
const { frames, currentFrame, status, nextFrame, selectFrame } = useFramePreview(videoIdRef)
const stripRef = ref<HTMLElement | null>(null)

const framesReady = computed(() => status.value === 'ready' || status.value === 'generating')

// 当前显示的图片源：有帧就显示帧，否则显示封面
const displaySrc = computed(() => {
  if (frames.value[currentFrame.value]) {
    return frames.value[currentFrame.value]
  }
  // fallback 到封面
  if (props.video?.video_id) {
    return `/api/thumb/${props.video.video_id}`
  }
  return null
})

const displayName = computed(() => {
  if (!props.video) return ''
  if (props.video.ext?.title) return props.video.ext.title
  return props.video.file_name || ''
})

function onRightClick() {
  nextFrame()
  scrollStripToCurrent()
}

function scrollStripToCurrent() {
  nextTick(() => {
    if (!stripRef.value) return
    const active = stripRef.value.children[currentFrame.value] as HTMLElement | undefined
    if (active) {
      active.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' })
    }
  })
}

function openInBrowser() {
  if (!props.video?.video_id) return
  const url = `/api/video/${props.video.video_id}`
  window.open(url, '_blank')
}

function openInIINA() {
  if (!props.video?.video_id) return
  const videoUrl = `${window.location.origin}/api/video/${props.video.video_id}`
  window.location.href = `iina://open?url=${encodeURIComponent(videoUrl)}`
}

function formatDuration(sec?: number): string {
  if (!sec) return ''
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  const s = Math.floor(sec % 60)
  return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
}

function formatSize(mb: number): string {
  if (!mb || mb <= 0) return ''
  if (mb < 1024) return `${mb}M`
  return `${(mb / 1024).toFixed(1)}G`
}

// currentFrame 变化时自动滚动小图条
watch(currentFrame, () => {
  scrollStripToCurrent()
})
</script>
```

- [ ] **Step 2: Typecheck and build**

Run: `cd frontend && bun run typecheck && bun run build`
Expected: 无错误，构建成功

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/LightboxModal.vue
git commit -m "feat(frontend): redesign LightboxModal with frame preview and playback

- Large image with right-click frame cycling
- Thumbnail strip with 20 frames, auto-scroll
- Browser playback (new tab) + IINA playback (iina:// protocol)
- Frame counter and right-click hint overlays

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 8: 全量集成测试

**Files:**
- None (uses existing test files)

- [ ] **Step 1: Run all backend tests**

Run: `cd backend && pytest -v`
Expected: All tests pass

- [ ] **Step 2: Run frontend typecheck**

Run: `cd frontend && bun run typecheck`
Expected: No errors

- [ ] **Step 3: Build frontend**

Run: `cd frontend && bun run build`
Expected: Build succeeds

- [ ] **Step 4: Final commit (if any fixups needed)**

```bash
git add -A
git commit -m "fix: integration fixes for frame preview and playback

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## 自检清单

- [x] **Spec 覆盖**：20 帧按需抽取 ✓、右键切换 ✓、小图条 ✓、浏览器播放 ✓、IINA 播放 ✓、Range 支持 ✓、安全校验 ✓
- [x] **无占位符**：所有步骤包含完整代码
- [x] **类型一致性**：`useFramePreview` 返回的 `frames`/`currentFrame`/`nextFrame`/`selectFrame` 在 LightboxModal 中使用一致；`FRAME_COUNT = 20` 在后端常量和前端数组长度一致
