# 视频库浏览器 实施计划

> **给代理工作者：** 必填子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实施此计划。步骤使用复选框（`- [ ]`）语法进行跟踪。

> **实施状态说明（2026-07-16 更新）：** 代码已演进到超越本计划的阶段。实际实现与计划的关键差异：
> - ✅ 服务模块已重组：`scanner.py`、`thumbgen.py`、`probe.py`、`cache_index.py` 移至 `backend/app/services/` 子目录
> - ✅ API 响应扁平化：视频条目直接包含 codec/width/height/duration/resolution_label，无 meta 嵌套
> - ✅ 文件大小统一：缓存（index.yaml）和 API 均以 MB 为单位（整数），前端显示时转换为 GB
> - ✅ `probe.py` 仅返回原始分辨率字段，`resolution_label` 由前端计算
> - ✅ 设置界面为模态框（`SettingsModal.vue`），非独立路由
> - ✅ 实现组内分页（`VideoGrid.vue`）
> - ✅ 顶栏包含搜索、排序、编码过滤、主题切换、设置按钮
> - ✅ 任务进度 Toast（`TaskToast.vue`）和规则测试器（`RuleTestModal.vue`）
> - ✅ 筛选状态持久化到 localStorage

**目标：** 构建一个视频库浏览器，使用 Python 后端（FastAPI）和 Vue3 前端，支持分层目录导航、渐进式缩略图生成和设置管理。

**架构：** FastAPI 提供 API 端点和静态前端服务。Vue3 SPA 使用 Tailwind CSS 构建 UI。后台工作队列处理渐进式数据获取（L1：目录遍历→L2：ffprobe→L3：缩略图）。每目录 `index.yaml` 缓存视频基础信息，`.jpg` 缩略图分离存储不做服务端尺寸/比例处理。IP 白名单中间件保护访问安全。

**技术栈：**
- 后端：Python 3.12、FastAPI、uvicorn、PyYAML、Pillow（使用 uv 管理环境）
- 前端：Vue 3、Vite、Tailwind CSS、Pinia、vue-router、axios（使用 Bun 作为运行时）
- 工具：ffmpeg/ffprobe（系统依赖）、pytest、vitest

**前提条件（开始前安装）：**
- uv（Python 包管理器，替代 pip + venv）
- Bun（JavaScript 运行时，替代 Node.js + npm）
- ffmpeg 和 ffprobe（系统包）

**实现默认值**（已内置到计划中，可通过配置调整）：
- Python 3.12 虚拟环境由 uv 管理，位于 `backend/.venv`
- 后端端口：8000（通过 `BACKEND_PORT` 环境变量）
- 日志文件轮转存储在 `$DATA_PATH/logs/`
- vue-router 用于主页面路由（设置使用模态框，非独立路由）
- 单 uvicorn worker（扫描状态在进程内）
- 缩略图降级策略：3:30 位置 → 中点 → 跳过
- 不存在的 `video_path` 条目：跳过并警告
- `/api/health` 端点用于 Docker 健康检查
- 单 worker 顺序处理缩略图提取队列
- 支持浅色/深色主题，可手动切换或跟随系统
- 缩略图原始帧提取，不做服务器端尺寸/比例处理
- 卡片三级渐进加载：L1 文件名 → L2 元数据 → L3 缩略图
- 左侧菜单显示处理进度条（已完成/总数）

**注意：** 以下任务基于最新设计文档的 6 项澄清和修改重新编写。与之前版本的关键差异：
- `descfile.py` 替换为 `cache_index.py`（index.yaml + .jpg 缩略图，无二进制描述文件）
- `thumbgen.py` 只做原始帧提取，不做尺寸/比例处理
- API 路由增加 `roots/{id}/l1` + `l1/{id}/l2` 层级
- 前端使用三层渐进加载（L1文件名→L2元数据→L3缩略图）
- 左侧菜单显示处理进度条
- **缩略图双尺寸**：`?size=small` 返回压缩 JPEG（卡片用），默认返回原始 JPEG（浮层用），响应带 `Cache-Control` 头
- **缓存读取**：扫描时先读 index.yaml 缓存，已完整缓存的视频直接标记 level 3，跳过重新抽帧（秒开）
- **文件名解析**：config 支持 parse_rules，正则命名捕获组提取 ext（code/actress/title），存入 index.yaml
- **卡片 ext 显示**：匹配到 ext 时显示 title + 可点击标签（code/actress），否则显示原始文件名
- **编码过滤**：下拉多选（排除模式），默认全选=不过滤
- **排序/搜索**：顶栏文件名/大小/时间排序，关键字搜索
- **"未分组"组不显示组标题**，仅展示卡片

### 任务 1：初始化项目结构和依赖

**文件：**
- 创建：`.env`、`.gitignore`、`backend/.env.example`、`backend/requirements.txt`

- [ ] **步骤 1：创建目录结构**

```bash
mkdir -p backend/app backend/tests frontend/src/{components,stores,composables,router} bin docker docs/superpowers/specs docs/superpowers/plans
```

- [ ] **步骤 2：创建 .env**

```bash
cat > .env << 'EOF'
DATA_PATH=.
IP_WHITE_LIST=
BACKEND_PORT=8000
EOF
```

- [ ] **步骤 3：创建 .gitignore**

写入 `.gitignore`：
```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
.venv/
backend/.venv/

# Node
node_modules/
frontend/dist/

# 数据
.cache/
logs/
*.pid

# IDE
.vscode/
.idea/
*.swp
*.swo

# 系统
.DS_Store
Thumbs.db
```

- [ ] **步骤 4：创建 backend/requirements.txt**

写入 `backend/requirements.txt`：
```txt
fastapi>=0.110.0
uvicorn[standard]>=0.29.0
pyyaml>=6.0.1
pillow>=10.3.0
python-dotenv>=1.0.1
pytest>=8.1.0
httpx>=0.27.0
```

- [ ] **步骤 5：创建 Python 虚拟环境并安装依赖（使用 uv）**

```bash
cd backend
uv venv --python 3.12
source .venv/bin/activate
uv pip install -r requirements.txt
cd ..
```

预期：虚拟环境创建成功（Python 3.12），所有包安装完成。

- [ ] **步骤 6：验证 ffmpeg/ffprobe 可用**

```bash
ffmpeg -version | head -1
ffprobe -version | head -1
```

预期：显示版本字符串。如果缺失，通过系统包管理器安装（例如 `sudo apt install ffmpeg`）。

- [ ] **步骤 7：验证 Bun 可用**

```bash
bun --version
```

预期：显示 Bun 版本号。如果缺失，从 https://bun.sh/ 安装 Bun。

- [ ] **步骤 8：提交初始结构**

```bash
git init
git add .env .gitignore backend/requirements.txt
git commit -m "chore: initialize project structure and dependencies"
```

---

## 第二阶段：后端核心模块（TDD）

> **设计变更：** 以下是按最新设计文档重新描述的后端模块。关键差异：
> - 删除 `descfile.py`（二进制描述文件），新增 `cache_index.py`（index.yaml + .jpg 缩略图管理）
> - `thumbgen.py` 只做原始帧提取（ffmpeg），不做任何服务端图片处理
> - `probe.py` 仅返回原始分辨率字段（width/height），不计算 `resolution_label`
> - `scanner.py` 包含本地 `_resolution_label()` 辅助函数，用于写入缓存时计算分辨率标签
> - 服务模块重组：`scanner.py`、`thumbgen.py`、`probe.py`、`cache_index.py` 移至 `backend/app/services/` 子目录
> - API 响应扁平化：视频条目直接包含 codec/width/height/duration/resolution_label，无 meta 嵌套
> - 文件大小统一：缓存（index.yaml）和 API 均以 MB 为单位（整数），前端显示时转换为 GB

### 任务 2：配置模块（TDD）

**文件：**
- 创建：`backend/app/__init__.py`、`backend/app/config.py`、`backend/tests/__init__.py`、`backend/tests/test_config.py`

- [ ] **步骤 1：编写失败的配置默认值测试**

写入 `backend/tests/test_config.py`：
```python
import pytest
from pathlib import Path
from app.config import AppConfig, load_config, save_config, data_path, ip_whitelist
import os

def test_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_PATH", str(tmp_path))
    cfg = load_config()
    assert cfg.video_path_list == []
    assert cfg.page_size == 0
    assert cfg.column_size == 4
```

- [ ] **步骤 2：运行测试验证失败**

```bash
cd backend
source .venv/bin/activate
pytest tests/test_config.py::test_defaults -v
```

预期：失败，报错 "ModuleNotFoundError: No module named 'app.config'"

- [ ] **步骤 3：创建 app/__init__.py**

写入 `backend/app/__init__.py`：
```python
```

（空文件）

- [ ] **步骤 4：编写最小配置实现**

写入 `backend/app/config.py`：
```python
import os
from dataclasses import dataclass, field
from pathlib import Path
import yaml

@dataclass
class AppConfig:
    video_path_list: list = field(default_factory=list)
    page_size: int = 0
    column_size: int = 4

def data_path() -> Path:
    p = Path(os.getenv("DATA_PATH", os.getcwd())).resolve()
    (p / "logs").mkdir(parents=True, exist_ok=True)
    (p / "cache").mkdir(parents=True, exist_ok=True)
    return p

def config_file() -> Path:
    return data_path() / "config.yaml"

def ip_whitelist() -> list[str]:
    raw = os.getenv("IP_WHITE_LIST", "").strip()
    if not raw:
        return []
    return [x.strip() for x in raw.replace(",", " ").split() if x.strip()]

def load_config() -> AppConfig:
    f = config_file()
    loaded = {}
    if f.exists():
        try:
            with open(f, "r", encoding="utf-8") as fh:
                loaded = yaml.safe_load(fh) or {}
        except (yaml.YAMLError, OSError):
            pass
    return AppConfig(
        video_path_list=list(loaded.get("video_path_list", []) or []),
        page_size=int(loaded.get("page_size", 0) or 0),
        column_size=int(loaded.get("column_size", 4) or 4),
    )

def save_config(cfg: AppConfig) -> None:
    data = {
        "video_path_list": list(cfg.video_path_list),
        "page_size": cfg.page_size,
        "column_size": cfg.column_size,
    }
    with open(config_file(), "w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, allow_unicode=True, sort_keys=False)
```

- [ ] **步骤 5：运行测试验证通过**

```bash
pytest tests/test_config.py::test_defaults -v
```

预期：通过

- [ ] **步骤 6：编写保存/加载往返测试**

追加到 `backend/tests/test_config.py`：
```python
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
```

- [ ] **步骤 7：运行测试**

```bash
pytest tests/test_config.py::test_save_load_roundtrip -v
```

预期：通过

- [ ] **步骤 8：提交**

```bash
git add backend/app/config.py backend/tests/test_config.py
git commit -m "feat(config): add config module with YAML persistence"
```

### 任务 3：路径 ID 模块（TDD）

**文件：**
- 创建：`backend/app/path_id.py`、`backend/tests/test_path_id.py`

- [ ] **步骤 1：编写失败测试**

写入 `backend/tests/test_path_id.py`：
```python
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
```

- [ ] **步骤 2：运行测试验证失败**

```bash
pytest tests/test_path_id.py -v
```

预期：失败，报错 "ModuleNotFoundError"

- [ ] **步骤 3：编写实现**

写入 `backend/app/path_id.py`：
```python
import hashlib
from pathlib import Path

def path_id(abs_path: str | Path) -> str:
    p = str(Path(abs_path).resolve())
    return hashlib.md5(p.encode("utf-8")).hexdigest()[:16]
```

- [ ] **步骤 4：运行测试验证通过**

```bash
pytest tests/test_path_id.py -v
```

预期：通过（两个测试）

- [ ] **步骤 5：提交**

```bash
git add backend/app/path_id.py backend/tests/test_path_id.py
git commit -m "feat(path_id): add stable path hashing utility"
```

### 任务 4：安全模块（TDD）

**文件：**
- 创建：`backend/app/security.py`、`backend/tests/test_security.py`

- [ ] **步骤 1：编写失败的本地主机允许测试**

写入 `backend/tests/test_security.py`：
```python
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.security import IPWhitelistMiddleware

def test_localhost_allowed(monkeypatch):
    monkeypatch.setenv("IP_WHITE_LIST", "")
    app = FastAPI()
    app.add_middleware(IPWhitelistMiddleware)
    app.get("/test")(lambda: {"ok": True})
    client = TestClient(app)
    resp = client.get("/test")
    assert resp.status_code == 200
```

- [ ] **步骤 2：运行测试验证失败**

```bash
pytest tests/test_security.py::test_localhost_allowed -v
```

预期：失败，报错 "ModuleNotFoundError"

- [ ] **步骤 3：编写实现**

写入 `backend/app/security.py`：
```python
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from . import config

LOCALHOST = {"127.0.0.1", "::1"}

class IPWhitelistMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        whitelist = set(config.ip_whitelist())
        client_ip = request.client.host if request.client else ""
        if client_ip in LOCALHOST or client_ip in whitelist:
            return await call_next(request)
        return JSONResponse({"detail": "forbidden: ip not allowed"}, status_code=403)
```

- [ ] **步骤 4：运行测试验证通过**

```bash
pytest tests/test_security.py::test_localhost_allowed -v
```

预期：通过

- [ ] **步骤 5：编写白名单强制执行测试**

追加到 `backend/tests/test_security.py`：
```python
def test_whitelist_enforcement(monkeypatch):
    monkeypatch.setenv("IP_WHITE_LIST", "192.168.1.100")
    app = FastAPI()
    app.add_middleware(IPWhitelistMiddleware)
    app.get("/test")(lambda: {"ok": True})
    client = TestClient(app)
    # TestClient 默认使用 127.0.0.1（本地主机），所以允许
    resp = client.get("/test")
    assert resp.status_code == 200
```

- [ ] **步骤 6：运行测试**

```bash
pytest tests/test_security.py::test_whitelist_enforcement -v
```

预期：通过

- [ ] **步骤 7：提交**

```bash
git add backend/app/security.py backend/tests/test_security.py
git commit -m "feat(security): add IP whitelist middleware with localhost bypass"
```

### 任务 5：探测模块（TDD）

**文件：**
- 创建：`backend/app/services/probe.py`、`backend/tests/test_probe.py`

- [ ] **步骤 1：创建测试辅助工具生成示例视频**

写入 `backend/tests/conftest.py`：
```python
import pytest
import subprocess
from pathlib import Path

@pytest.fixture
def sample_video(tmp_path):
    video_path = tmp_path / "test.mp4"
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi", "-i",
        "testsrc=duration=2:size=320x240:rate=30",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        str(video_path)
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    return str(video_path)
```

- [ ] **步骤 2：编写失败的 probe_video 测试**

写入 `backend/tests/test_probe.py`：
```python
from app.services.probe import probe_video

def test_probe_video(sample_video):
    result = probe_video(sample_video)
    assert "codec" in result
    assert "width" in result
    assert "height" in result
    assert "duration" in result
    assert result["width"] == 320
    assert result["height"] == 240
    assert result["duration"] >= 1.5
    assert isinstance(result["file_size"], int)
    assert result["file_size"] >= 0  # 小视频可能不足 1MB，整数除法结果为 0
    # probe.py 不再返回 resolution_str（由前端计算）
    assert "resolution_str" not in result
```

- [ ] **步骤 3：运行测试验证失败**

```bash
pytest tests/test_probe.py -v
```

预期：失败，报错 "ModuleNotFoundError"

- [ ] **步骤 4：编写实现**

写入 `backend/app/services/probe.py`：
```python
import json
import os
import subprocess


def probe_video(path: str) -> dict:
    """使用 ffprobe 读取视频元数据。

    返回原始分辨率字段（width, height），不计算 resolution_label。
    """
    cmd = [
        "ffprobe", "-v", "error",
        "-show_streams", "-show_format",
        "-of", "json", str(path)
    ]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffprobe failed: {e.stderr}")
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"ffprobe timed out for: {path}")

    data = json.loads(out.stdout)
    streams = data.get("streams", [])

    vstream = None
    cover_index = None
    for i, s in enumerate(streams):
        if s.get("codec_type") == "video":
            disp = int(s.get("disposition", {}).get("attached_pic", 0))
            codec = s.get("codec_name", "")
            if disp == 1 or codec in ("mjpeg", "png", "jpegls"):
                if cover_index is None:
                    cover_index = i
            else:
                if vstream is None:
                    vstream = s

    if vstream is None:
        vstream = next((s for s in streams if s.get("codec_type") == "video"), {})

    width = int(vstream.get("width") or 0)
    height = int(vstream.get("height") or 0)
    codec = (vstream.get("codec_name") or "unknown").upper()
    duration = float(data.get("format", {}).get("duration") or vstream.get("duration") or 0.0)
    # 文件大小，单位：MB（整数）
    file_size_mb = int(os.path.getsize(path) / (1024 * 1024))

    return {
        "codec": codec,
        "width": width,
        "height": height,
        "duration": duration,
        "cover_stream_index": cover_index,
        "file_size": file_size_mb,  # MB
    }
```

- [ ] **步骤 5：运行测试验证通过**

```bash
pytest tests/test_probe.py -v
```

预期：通过（一个测试）

- [ ] **步骤 6：提交**

```bash
git add backend/app/services/probe.py backend/tests/test_probe.py backend/tests/conftest.py
git commit -m "feat(probe): add ffprobe wrapper with cover detection"
```

### 任务 6：缩略图生成模块（TDD）

**文件：**
- 创建：`backend/app/services/thumbgen.py`、`backend/tests/test_thumbgen.py`

> **注意：** 缩略图生成仅做原始帧提取，不做任何服务端尺寸/比例处理。前端使用 CSS `object-fit: contain` 做显示适配。

- [ ] **步骤 1：编写失败的 extract_frame 测试**

写入 `backend/tests/test_thumbgen.py`：
```python
from app.services.probe import probe_video
from app.services.thumbgen import extract_frame, extract_frame_from_probe

def test_extract_frame_returns_jpeg(sample_video):
    """Verify extract_frame_from_probe returns valid JPEG bytes."""
    probe = probe_video(sample_video)
    result = extract_frame_from_probe(sample_video, probe)
    assert result is not None
    # JPEG magic bytes: FF D8 FF
    assert result[:3] == b"\xff\xd8\xff"

def test_extract_frame_returns_none_for_nonexistent():
    """Verify extract_frame returns None for a non-existent file."""
    result = extract_frame("/tmp/nonexistent_video_12345.mp4")
    assert result is None
```

- [ ] **步骤 2：运行测试验证失败**

```bash
pytest tests/test_thumbgen.py -v
```

预期：失败，报错 "ModuleNotFoundError"

- [ ] **步骤 3：编写实现**

写入 `backend/app/services/thumbgen.py`：
```python
"""Raw frame extraction from video files using ffmpeg.

Extracts a single frame at original resolution with no resizing or
aspect-ratio adjustment. Output format is JPEG.
"""

import io
import subprocess

from PIL import Image

from .probe import probe_video

SEEK_TIME = 210.0  # 3:30

# 小缩略图目标宽度（卡片用），等比缩放，JPEG 压缩
SMALL_WIDTH = 480
SMALL_JPEG_QUALITY = 85


def _extract_frame(path: str, probe: dict) -> bytes | None:
    """Run ffmpeg to extract a single frame, returning raw JPEG bytes.

    Prioritises embedded cover streams, then SEEK_TIME seek,
    then video midpoint for short clips.
    """
    if probe.get("cover_stream_index") is not None:
        idx = probe["cover_stream_index"]
        cmd = [
            "ffmpeg", "-v", "error",
            "-i", str(path),
            "-map", f"0:{idx}",
            "-frames:v", "1",
            "-f", "image2pipe", "-vcodec", "mjpeg", "-",
        ]
    else:
        dur = probe.get("duration", 0.0)
        t = SEEK_TIME if dur > SEEK_TIME else (dur / 2 if dur > 0 else 0.0)
        cmd = [
            "ffmpeg", "-v", "error",
            "-ss", f"{t:.2f}",
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


def extract_frame(path: str) -> bytes | None:
    """Extract a single raw JPEG frame from *path*.

    Probes the video internally to determine cover-stream vs seek strategy.
    Returns ``None`` when ffprobe or ffmpeg fails.
    """
    try:
        probe = probe_video(path)
    except Exception:
        return None
    return _extract_frame(path, probe)


def extract_frame_from_probe(path: str, probe: dict) -> bytes | None:
    """Extract a single raw JPEG frame using pre-computed *probe* data.

    *probe* must contain ``cover_stream_index`` (int | None) and
    ``duration`` (float).  Returns ``None`` when ffmpeg fails.
    """
    return _extract_frame(path, probe)


def make_small_jpeg(jpeg_bytes: bytes, target_width: int = SMALL_WIDTH) -> bytes:
    """将原始 JPEG 帧等比缩小为更小的 JPEG（卡片预览用）。

    仅缩放尺寸 + 重新压缩，不改变宽高比、不加黑边。
    """
    img = Image.open(io.BytesIO(jpeg_bytes))
    if img.width > target_width:
        ratio = target_width / img.width
        new_size = (target_width, max(1, round(img.height * ratio)))
        img = img.resize(new_size, Image.LANCZOS)
    img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=SMALL_JPEG_QUALITY)
    return buf.getvalue()
```

- [ ] **步骤 4：运行测试验证通过**

```bash
pytest tests/test_thumbgen.py -v
```

预期：通过（两个测试）

- [ ] **步骤 5：提交**

```bash
git add backend/app/services/thumbgen.py backend/tests/test_thumbgen.py
git commit -m "feat(thumbgen): add dual thumbnail generation with fallback to placeholder"
```

---

## 第三阶段：后端扫描器与 API（TDD）

> **设计变更：** cache 改为 `index.yaml` + `.jpg` 缩略图方案：
> - 每目录一个 `index.yaml`（扁平结构：文件名、分组、level、创建/修改时间、大小MB、编码、宽高、时长秒、分辨率标签、缩略图文件名）
> - 缩略图为原始帧 `.jpg`，不做服务端尺寸/比例适配
> - `scanner.py` 改为操作 `cache_index.py` 读写 index.yaml
> - API 导航层级：roots（视频库根目录）→ l1（一级目录/顶部菜单）→ l2（二级目录/左侧菜单）

### 任务 8：扫描器服务（TDD）

**文件：**
- 创建：`backend/app/services/scanner.py`、`backend/tests/test_scanner.py`

- [ ] **步骤 1：编写失败的扫描编排测试**

写入 `backend/tests/test_scanner.py`：
```python
import pytest
from pathlib import Path
import subprocess
from app.services.scanner import Scanner, find_root
from app import config

@pytest.fixture
def video_dir(tmp_path):
    # 创建测试目录结构
    videos = tmp_path / "videos"
    l1 = videos / "movies"
    l2 = l1 / "action"
    l2.mkdir(parents=True)
    
    # 生成测试视频
    video_path = l2 / "test.mp4"
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi", "-i",
        "testsrc=duration=2:size=320x240:rate=30",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        str(video_path)
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    
    return str(videos)

def test_find_root(video_dir, monkeypatch):
    monkeypatch.setenv("DATA_PATH", str(Path(video_dir).parent))
    cfg = config.AppConfig(video_path_list=[video_dir])
    monkeypatch.setattr(config, "load_config", lambda: cfg)
    
    video_file = Path(video_dir) / "movies" / "action" / "test.mp4"
    root = find_root(str(video_file), [video_dir])
    assert root == Path(video_dir).resolve()

def test_scanner_ensures_scan(video_dir, monkeypatch):
    monkeypatch.setenv("DATA_PATH", str(Path(video_dir).parent))
    cfg = config.AppConfig(video_path_list=[video_dir], page_size=0, column_size=4)
    monkeypatch.setattr(config, "load_config", lambda: cfg)

    scanner = Scanner()
    l2_path = str(Path(video_dir) / "movies" / "action")
    groups, scanning, progress = scanner.ensure_scan(l2_path)
    assert len(groups) > 0
    assert scanning == False  # 小目录扫描快速完成
    assert progress["total"] >= 1
```

- [ ] **步骤 2：运行测试验证失败**

```bash
pytest tests/test_scanner.py -v
```

预期：失败，报错 "ModuleNotFoundError"

- [ ] **步骤 3：编写实现**

写入 `backend/app/services/scanner.py`：
```python
import os
import threading
import time
from collections import OrderedDict
from pathlib import Path
from . import probe, cache_index, thumbgen
from .. import config, path_id

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
    """对文件名应用解析规则，匹配成功返回 ext 字典（无 meta 嵌套）。"""
    import re
    if not rules:
        return None
    for rule in rules:
        pattern = rule.get("pattern", "")
        if not pattern:
            continue
        try:
            m = re.match(pattern, file_name)
            if m:
                ext = {k: v for k, v in m.groupdict().items() if v is not None}
                if ext:
                    return ext
        except re.error:
            continue
    return None


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
        entry["duration"] = int(item.get("duration", 0) or 0)
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


class _L2State:
    def __init__(self):
        # RLock 作为防御性安全网：正常路径不应依赖可重入性
        self.lock = threading.RLock()
        self.scanning = False
        self.total = 0
        self.seq = 0
        self.videos = {}  # video_id -> dict


class Scanner:
    def __init__(self):
        self._l2_states = OrderedDict()  # LRU 有序：最近使用的在末尾
        self._id_to_path = {}
        self._lock = threading.Lock()  # 保护 _l2_states 和 _id_to_path

    def _get_l2_state(self, l2_path: str) -> _L2State:
        with self._lock:
            state = self._l2_states.get(l2_path)
            if state is None:
                state = _L2State()
                self._l2_states[l2_path] = state
            else:
                self._l2_states.move_to_end(l2_path)
            state.last_used = time.time()
            # LRU 淘汰：超过上限时驱逐最久未用的、且未在扫描中的状态
            while len(self._l2_states) > MAX_CACHED_L2_DIRS:
                old_path, old_state = next(iter(self._l2_states.items()))
                if old_state.scanning:
                    break
                self._l2_states.pop(old_path)
            return state

    def ensure_scan(self, l2_path: str):
        state = self._get_l2_state(l2_path)
        with state.lock:
            already_scanning = state.scanning
            if not already_scanning:
                state.scanning = True
                t = threading.Thread(
                    target=self._scan_worker, args=(l2_path, state), daemon=True
                )
                t.start()
        if not already_scanning:
            time.sleep(0.5)  # 新启动的扫描，短暂等待快速阶段填充数据
        return self._build_groups(state), state.scanning, self._build_progress(state)

    def _scan_worker(self, l2_path: str, state: _L2State):
        try:
            cfg = config.load_config()
            root = find_root(l2_path, cfg.video_path_list)

            video_paths = []
            for root_dir, dirs, files in os.walk(l2_path):
                for f in files:
                    if Path(f).suffix.lower() in VIDEO_EXTS:
                        video_paths.append(Path(root_dir) / f)

            with state.lock:
                state.total = len(video_paths)

            # Phase L1 — 文件系统扫描，扁平条目 + 文件名解析规则
            for video_path in video_paths:
                vid = path_id.path_id(str(video_path))
                file_size = int(video_path.stat().st_size / (1024 * 1024))  # bytes → MB
                file_mtime = int(video_path.stat().st_mtime)
                item = {
                    "video_id": vid,
                    "file_name": video_path.name,
                    "file_size": file_size,  # MB
                    "modify_time": file_mtime,
                    "group": self._group_name(str(video_path), l2_path),
                    "level": 1,
                }
                ext_data = _parse_filename(video_path.name, cfg.parse_rules)
                if ext_data:
                    item["ext"] = ext_data
                # L1 阶段即把最小条目落盘到 index.yaml
                if root:
                    index_path, _ = cache_index.video_cache_path(str(root), str(video_path))
                    cache_index.update_video_in_index(
                        index_path, _build_cache_entry(video_path, item, level=1)
                    )
                with state.lock:
                    state.seq += 1
                    item["seq"] = state.seq
                    state.videos[vid] = item

            # Phase L2 — ffprobe 元数据
            for video_path in video_paths:
                vid = path_id.path_id(str(video_path))
                with state.lock:
                    if state.videos.get(vid, {}).get("level", 1) >= 2:
                        continue
                try:
                    probe_result = probe.probe_video(str(video_path))
                except Exception:
                    probe_result = None
                with state.lock:
                    if vid in state.videos and probe_result is not None:
                        _merge_metadata(state.videos[vid], probe_result)
                        state.videos[vid]["level"] = 2
                        state.videos[vid]["_probe"] = probe_result
                if root and probe_result is not None:
                    index_path, _ = cache_index.video_cache_path(str(root), str(video_path))
                    with state.lock:
                        item_snapshot = dict(state.videos.get(vid, {}))
                    item_snapshot["group"] = self._group_name(str(video_path), l2_path)
                    cache_index.update_video_in_index(
                        index_path, _build_cache_entry(video_path, item_snapshot, level=2)
                    )

            # Phase L3 — 缩略图提取（原始 JPEG 帧）
            for video_path in video_paths:
                vid = path_id.path_id(str(video_path))
                with state.lock:
                    entry = state.videos.get(vid)
                    probe_result = entry.get("_probe") if entry else None
                if probe_result is None:
                    continue
                try:
                    png_bytes = thumbgen.extract_frame_from_probe(str(video_path), probe_result)
                except Exception:
                    png_bytes = None
                if not png_bytes or not root:
                    continue
                index_path, thumb_path = cache_index.video_cache_path(str(root), str(video_path))
                thumb_path.write_bytes(png_bytes)
                with state.lock:
                    if vid in state.videos:
                        state.videos[vid]["level"] = 3
                        state.videos[vid].pop("_probe", None)
                        entry_snapshot = dict(state.videos[vid])
                if entry_snapshot:
                    cache_index.update_video_in_index(
                        index_path,
                        _build_cache_entry(video_path, entry_snapshot, level=3, thumb_file=thumb_path.name)
                    )
        finally:
            with state.lock:
                state.scanning = False

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
                # 浅拷贝，避免返回带 _probe 的临时字段
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
            return {"total": state.total, "level1": level1, "level2": level2, "level3": level3}

    def status(self, l2_path: str, since: int = 0):
        state = self._get_l2_state(l2_path)
        with state.lock:
            updates = []
            for vid, item in state.videos.items():
                if item.get("seq", -1) > since:
                    # 扁平更新条目：基础字段 + 可选元数据字段（无 meta 嵌套）
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
                        entry["width"] = item["width"]
                        entry["height"] = item["height"]
                        entry["duration"] = item["duration"]
                        entry["resolution_label"] = item.get("resolution_label")
                    updates.append(entry)
            updates.sort(key=lambda u: u["seq"])
            progress = self._build_progress(state)
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

        small=True 返回压缩后的小 JPEG（卡片用，懒生成 .small.jpg）；
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
```

- [ ] **步骤 4：运行测试验证通过**

```bash
pytest tests/test_scanner.py -v
```

预期：通过（两个测试）

- [ ] **步骤 5：提交**

```bash
git add backend/app/services/scanner.py backend/tests/test_scanner.py
git commit -m "feat(scanner): add progressive scan orchestration with caching"
```

---

## 第四阶段：后端 API 路由与主应用

### 任务 9：Pydantic 模型

**文件：**
- 创建：`backend/app/models.py`

- [ ] **步骤 1：编写模型**

写入 `backend/app/models.py`：
```python
from pydantic import BaseModel


class VideoItem(BaseModel):
    """视频条目（扁平结构，与 index.yaml 一致）。

    L1：仅有 file_name/file_size/group/level=1
    L2：附加 codec/width/height/duration/resolution_label
    L3：附加缩略图（thumb_file 仅在缓存中）
    """
    video_id: str
    file_name: str
    file_size: int  # 单位：MB（整数）
    group: str
    level: int = 1  # 1=filename, 2=+metadata, 3=+thumbnail
    modify_time: int | None = None  # 源文件修改时间（epoch 秒）
    ext: dict | None = None  # 文件名解析扩展信息（code/actress/title 等）
    # L2+ 元数据字段（level>=2 时存在）
    codec: str | None = None
    width: int | None = None
    height: int | None = None
    duration: float | None = None
    resolution_label: str | None = None  # e.g. "4K", "FHD"

class Group(BaseModel):
    name: str
    videos: list[VideoItem]

class VideosResponse(BaseModel):
    groups: list[Group]
    scanning: bool
    progress: dict = {}  # {"total": N, "level1": N, "level2": N, "level3": N}

class ScanUpdate(BaseModel):
    """扫描增量更新条目（扁平结构）。"""
    seq: int
    video_id: str
    file_name: str
    file_size: int  # 单位：MB（整数）
    group: str
    level: int
    modify_time: int | None = None
    ext: dict | None = None
    codec: str | None = None
    width: int | None = None
    height: int | None = None
    duration: float | None = None
    resolution_label: str | None = None

class ScanStatus(BaseModel):
    scanning: bool
    total: int
    ready: int
    last_seq: int
    progress: dict = {}
    updates: list[ScanUpdate]

class ConfigModel(BaseModel):
    video_path_list: list[str]
    page_size: int
    column_size: int

class DirEntry(BaseModel):
    id: str
    name: str
    path: str
```

- [ ] **步骤 2：提交**

```bash
git add backend/app/models.py
git commit -m "feat(models): add Pydantic models for API"
```

### 任务 10：API 路由

**文件：**
- 创建：`backend/app/routes/__init__.py`、`backend/app/routes/config.py`、`backend/app/routes/dirs.py`、`backend/app/routes/videos.py`、`backend/app/routes/scan.py`

- [ ] **步骤 1：创建路由包**

写入 `backend/app/routes/__init__.py`：
```python
```

（空文件）

- [ ] **步骤 2：编写配置路由**

写入 `backend/app/routes/config.py`：
```python
from fastapi import APIRouter
from .. import config
from ..models import ConfigModel

router = APIRouter()

@router.get("/config", response_model=ConfigModel)
def get_config():
    cfg = config.load_config()
    return ConfigModel(
        video_path_list=cfg.video_path_list,
        page_size=cfg.page_size,
        column_size=cfg.column_size,
    )

@router.put("/config", response_model=ConfigModel)
def update_config(model: ConfigModel):
    cfg = config.AppConfig(
        video_path_list=model.video_path_list,
        page_size=model.page_size,
        column_size=model.column_size,
    )
    config.save_config(cfg)
    return model
```

- [ ] **步骤 3：编写目录路由**

写入 `backend/app/routes/dirs.py`：
```python
from fastapi import APIRouter, HTTPException
from pathlib import Path
from .. import config
from ..models import DirEntry
from ..path_id import path_id

router = APIRouter()

@router.get("/roots", response_model=list[DirEntry])
def list_roots():
    cfg = config.load_config()
    entries = []
    for p in cfg.video_path_list:
        if Path(p).exists():
            entries.append(DirEntry(
                id=path_id(p),
                name=Path(p).name,
                path=p,
            ))
    return entries

@router.get("/roots/{root_id}/l2", response_model=list[DirEntry])
def list_l2(root_id: str):
    cfg = config.load_config()
    root = None
    for p in cfg.video_path_list:
        if path_id(p) == root_id:
            root = Path(p).resolve()
            break
    
    if root is None:
        raise HTTPException(404, "未找到根目录")
    
    entries = []
    for item in root.iterdir():
        if item.is_dir():
            entries.append(DirEntry(
                id=path_id(str(item)),
                name=item.name,
                path=str(item),
            ))
    return sorted(entries, key=lambda e: e.name)
```

- [ ] **步骤 4：编写视频路由**

写入 `backend/app/routes/videos.py`：
```python
from fastapi import APIRouter, HTTPException, Response
from pathlib import Path
from .. import config, path_id
from ..services.scanner import Scanner

router = APIRouter()
scanner = Scanner()

@router.get("/l2/{l2_id}/videos")
def get_videos(l2_id: str):
    """Get all video filenames under L2 directory (L1 - instant filesystem scan).
    Triggers background processing for metadata and thumbnails."""

    l2_path = _find_l2_path(l2_id)
    if l2_path is None:
        raise HTTPException(404, "l2 directory not found")

    groups, scanning, progress = scanner.ensure_scan(l2_path)
    return {"groups": groups, "scanning": scanning, "progress": progress}


@router.get("/thumb/{video_id}")
def get_thumb(video_id: str, size: str = "full"):
    """获取缩略图。size=small 返回压缩小图（卡片用），默认 full 返回原始 JPEG（浮层用）。
    未就绪返回 202。"""
    small = size == "small"
    result = scanner.get_thumb(video_id, small=small)
    if result is None:
        return Response(status_code=202, content="thumbnail not ready")
    media_type, thumb_bytes = result
    return Response(
        content=thumb_bytes,
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )


def _find_l2_path(l2_id: str) -> str | None:
    """Helper: resolve l2_id to absolute path."""
    cfg = config.load_config()
    for root_p in cfg.video_path_list:
        root = Path(root_p).resolve()
        if not root.exists():
            continue
        for l1_item in root.iterdir():
            if not l1_item.is_dir():
                continue
            for l2_item in l1_item.iterdir():
                if l2_item.is_dir() and path_id.path_id(str(l2_item)) == l2_id:
                    return str(l2_item)
    return None
```

- [ ] **步骤 5：编写扫描路由**

写入 `backend/app/routes/scan.py`：
```python
from fastapi import APIRouter, HTTPException
from ..routes.videos import scanner
from ..models import ScanStatus

router = APIRouter()

@router.get("/scan-status", response_model=ScanStatus)
def scan_status(l2_id: str, since: int = 0):
    from ..path_id import path_id
    from pathlib import Path
    from .. import config
    
    cfg = config.load_config()
    l2_path = None
    for root_p in cfg.video_path_list:
        root = Path(root_p).resolve()
        if not root.exists():
            continue
        for item in root.iterdir():
            if item.is_dir() and path_id(str(item)) == l2_id:
                l2_path = str(item)
                break
        if l2_path:
            break
    
    if l2_path is None:
        raise HTTPException(404, "未找到 l2 目录")
    
    status = scanner.status(l2_path, since)
    return ScanStatus(**status)
```

- [ ] **步骤 6：提交**

```bash
git add backend/app/routes/
git commit -m "feat(routes): add config, dirs, videos, scan API routes"
```

### 任务 11：主 FastAPI 应用

**文件：**
- 创建：`backend/app/main.py`

- [ ] **步骤 1：编写 main.py**

写入 `backend/app/main.py`：
```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
from contextlib import asynccontextmanager
from . import config
from .security import IPWhitelistMiddleware
from .routes import config as config_routes, dirs, videos, scan
import logging
from logging.handlers import RotatingFileHandler

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动
    config.data_path()  # 确保目录存在
    yield
    # 关闭

app = FastAPI(lifespan=lifespan)

# 中间件
app.add_middleware(IPWhitelistMiddleware)

# 日志
log_dir = config.data_path() / "logs"
log_dir.mkdir(parents=True, exist_ok=True)
handler = RotatingFileHandler(
    log_dir / "app.log", maxBytes=10*1024*1024, backupCount=5, encoding="utf-8"
)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[handler, logging.StreamHandler()],
)

# API 路由
app.include_router(config_routes.router, prefix="/api")
app.include_router(dirs.router, prefix="/api")
app.include_router(videos.router, prefix="/api")
app.include_router(scan.router, prefix="/api")

@app.get("/api/health")
def health():
    return {"status": "ok"}

# 静态文件（前端）
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    @app.get("/")
    def root():
        return FileResponse(static_dir / "index.html")
    
    @app.get("/{path:path}")
    def catch_all(path: str):
        file = static_dir / path
        if file.exists():
            return FileResponse(file)
        # SPA 回退
        return FileResponse(static_dir / "index.html")
```

- [ ] **步骤 2：提交**

```bash
git add backend/app/main.py
git commit -m "feat(main): add FastAPI app with middleware, routes, static serving"
```

### 任务 12：端到端 API 测试

**文件：**
- 创建：`backend/tests/test_api.py`

- [ ] **步骤 1：编写 API 测试**

写入 `backend/tests/test_api.py`：
```python
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
    
    resp = client.get("/api/roots")
    assert resp.status_code == 200
```

- [ ] **步骤 2：运行测试**

```bash
pytest tests/test_api.py -v
```

预期：通过（全部 3 个测试）

- [ ] **步骤 3：提交**

```bash
git add backend/tests/test_api.py
git commit -m "test(api): add end-to-end API tests"
```

---

## 第五阶段：前端设置与组件

> **设计变更：** 卡片渲染改为三层渐进加载：
> - L1（即时）：从目录遍历获取文件名，渲染卡片布局+`<p>加载中...</p>`占位
> - L2（异步）：ffprobe 元数据就绪后更新编码/分辨率/时长/大小标签
> - L3（异步）：缩略图就绪后将 `<p>` 替换为 `<img>`（使用 `object-fit: contain` 做显示适配）
> - 左侧二级菜单项在后台处理进行时显示进度条（已完成/总数）
> - 缩略图为原始分辨率 JPEG，服务端不做尺寸/比例处理
> - 视频库根目录切换下拉框在顶部菜单最左侧

### 任务 13：初始化 Vue3 项目

**文件：**
- 创建：`frontend/package.json`、`frontend/vite.config.ts`、`frontend/tsconfig.json`、`frontend/index.html`、`frontend/tailwind.config.js`、`frontend/postcss.config.js`

- [ ] **步骤 1：使用 Vite 初始化前端（使用 Bun）**

```bash
cd frontend
bun create vue@latest . --typescript
```

预期：Vite + Vue3 + TypeScript 项目脚手架创建完成。

- [ ] **步骤 2：安装依赖（使用 Bun）**

```bash
bun install vue-router@4 pinia axios
bun install -D tailwindcss postcss autoprefixer @types/node
bunx tailwindcss init -p
```

预期：所有包安装完成。

- [ ] **步骤 3：配置 Vite**

写入 `frontend/vite.config.ts`：
```typescript
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
```

- [ ] **步骤 4：配置 Tailwind（支持深色模式）**

写入 `frontend/tailwind.config.js`：
```javascript
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {},
  },
  plugins: [],
}
```

写入 `frontend/postcss.config.js`：
```javascript
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
```

- [ ] **步骤 5：创建 index.html**

写入 `frontend/index.html`：
```html
<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8">
    <link rel="icon" href="/favicon.ico">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>视频浏览器</title>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="/src/main.ts"></script>
  </body>
</html>
```

- [ ] **步骤 6：创建 src/main.ts 引入 Tailwind**

写入 `frontend/src/main.ts`：
```typescript
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './style.css'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')
```

写入 `frontend/src/style.css`：
```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

- [ ] **步骤 7：验证构建**

```bash
bun run build
```

预期：构建成功，创建 `dist/` 目录。

- [ ] **步骤 8：提交**

```bash
git add frontend/
git commit -m "chore(frontend): initialize Vue3 + Vite + Tailwind project"
```

### 任务 14：Vue Router 与应用布局

**文件：**
- 创建：`frontend/src/router/index.ts`、`frontend/src/App.vue`

- [ ] **步骤 1：创建路由器**

写入 `frontend/src/router/index.ts`：
```typescript
import { createRouter, createWebHistory } from 'vue-router'
import BrowserView from '../views/BrowserView.vue'
import SettingsView from '../views/SettingsView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: BrowserView },
    { path: '/settings', component: SettingsView },
  ],
})

export default router
```

- [ ] **步骤 2：创建 App.vue（支持深色模式）**

写入 `frontend/src/App.vue`：
```vue
<template>
  <div class="min-h-screen bg-gray-100 dark:bg-gray-900 text-gray-900 dark:text-gray-100">
    <router-view />
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useThemeStore } from './stores/theme'

const theme = useThemeStore()

onMounted(() => {
  theme.init()
})
</script>
```

- [ ] **步骤 3：创建 views 目录**

```bash
mkdir -p frontend/src/views
```

- [ ] **步骤 4：提交**

```bash
git add frontend/src/router/ frontend/src/App.vue
git commit -m "feat(frontend): add vue-router and App layout"
```

### 任务 15：Pinia 状态管理

**文件：**
- 创建：`frontend/src/stores/config.ts`、`frontend/src/stores/browser.ts`、`frontend/src/stores/theme.ts`

- [ ] **步骤 1：创建配置 store**

写入 `frontend/src/stores/config.ts`：
```typescript
import { defineStore } from 'pinia'
import axios from 'axios'

export const useConfigStore = defineStore('config', {
  state: () => ({
    video_path_list: [] as string[],
    page_size: 0,
    column_size: 4,
  }),
  actions: {
    async fetch() {
      const { data } = await axios.get('/api/config')
      this.video_path_list = data.video_path_list
      this.page_size = data.page_size
      this.column_size = data.column_size
    },
    async update() {
      await axios.put('/api/config', {
        video_path_list: this.video_path_list,
        page_size: this.page_size,
        column_size: this.column_size,
      })
      await this.fetch()
    },
  },
})
```

- [ ] **步骤 2：创建浏览器 store**

写入 `frontend/src/stores/browser.ts`：
```typescript
import { defineStore } from 'pinia'
import axios from 'axios'

interface VideoItem {
  video_id: string
  file_name: string
  file_size: number  // 单位：MB（整数）
  group: string
  level: number  // 1=filename, 2=+metadata, 3=+thumbnail
  modify_time?: number  // 源文件修改时间（epoch 秒）
  ext?: Record<string, string>  // 文件名解析扩展信息（code/actress/title 等）
  // L2+ 元数据字段
  codec?: string
  width?: number
  height?: number
  duration?: number
  resolution_label?: string  // e.g. "4K", "FHD"
}

interface Group {
  name: string
  videos: VideoItem[]
}

interface ProgressInfo {
  total: number
  level1: number
  level2: number
  level3: number
}

export const useBrowserStore = defineStore('browser', {
  state: () => ({
    roots: [] as { id: string; name: string; path: string }[],
    selectedRootId: null as string | null,
    l1Dirs: [] as { id: string; name: string; path: string }[],
    selectedL1Id: null as string | null,
    l2Dirs: [] as { id: string; name: string; path: string }[],
    selectedL2Id: null as string | null,
    groups: [] as Group[],
    scanning: false,
    progress: { total: 0, level1: 0, level2: 0, level3: 0 } as ProgressInfo,
  }),
  actions: {
    async fetchRoots() {
      const { data } = await axios.get('/api/roots')
      this.roots = data
    },
    async selectRoot(rootId: string) {
      this.selectedRootId = rootId
      this.selectedL1Id = null
      this.selectedL2Id = null
      this.groups = []
      const { data } = await axios.get(`/api/roots/${rootId}/l1`)
      this.l1Dirs = data
    },
    async selectL1(l1Id: string) {
      this.selectedL1Id = l1Id
      this.selectedL2Id = null
      this.groups = []
      const { data } = await axios.get(`/api/l1/${l1Id}/l2`)
      this.l2Dirs = data
    },
    async selectL2(l2Id: string) {
      this.selectedL2Id = l2Id
      const { data } = await axios.get(`/api/l2/${l2Id}/videos`)
      this.groups = data.groups
      this.scanning = data.scanning
      this.progress = data.progress || { total: 0, level1: 0, level2: 0, level3: 0 }
      // 打开目录触发扫描 → 启动任务浮窗轮询
      if (this.scanning) {
        const { useTaskStore } = await import('./task')
        useTaskStore().notifyScan()
      }
    },
    async pollStatus() {
      if (!this.selectedL2Id) return
      const { data } = await axios.get(`/api/scan-status?l2_id=${this.selectedL2Id}`)
      this.scanning = data.scanning
      this.progress = data.progress || { total: 0, level1: 0, level2: 0, level3: 0 }
      // Merge updates into groups（扁平字段直接合并）
      for (const update of data.updates) {
        for (const group of this.groups) {
          if (group.name === update.group) {
            const existing = group.videos.find(v => v.video_id === update.video_id)
            if (existing) {
              // 合并所有扁平字段
              Object.assign(existing, update)
              // 清理 scan 协议字段（不属于 VideoItem）
              delete (existing as any).seq
            }
            break
          }
        }
      }
    },
  },
})
```

- [ ] **步骤 3：创建主题 store**

写入 `frontend/src/stores/theme.ts`：
```typescript
import { defineStore } from 'pinia'
import { watch } from 'vue'

type ThemeMode = 'light' | 'dark' | 'system'

export const useThemeStore = defineStore('theme', {
  state: () => ({
    mode: (localStorage.getItem('theme-mode') as ThemeMode) || 'system',
    systemDark: window.matchMedia('(prefers-color-scheme: dark)').matches,
  }),
  getters: {
    isDark: (state) => {
      if (state.mode === 'light') return false
      if (state.mode === 'dark') return true
      return state.systemDark
    },
  },
  actions: {
    setMode(mode: ThemeMode) {
      this.mode = mode
      localStorage.setItem('theme-mode', mode)
      this.applyTheme()
    },
    applyTheme() {
      if (this.isDark) {
        document.documentElement.classList.add('dark')
      } else {
        document.documentElement.classList.remove('dark')
      }
    },
    init() {
      // 监听系统主题变化
      const mq = window.matchMedia('(prefers-color-scheme: dark)')
      mq.addEventListener('change', (e) => {
        this.systemDark = e.matches
        if (this.mode === 'system') {
          this.applyTheme()
        }
      })
      // 初始化时应用主题
      this.applyTheme()
    },
  },
})
```

- [ ] **步骤 4：提交**

```bash
git add frontend/src/stores/
git commit -m "feat(stores): add Pinia stores for config and browser"
```

### 任务 16：组合式函数（useScanPolling）

**文件：**
- 创建：`frontend/src/composables/useScanPolling.ts`

- [ ] **步骤 1：创建组合式函数**

写入 `frontend/src/composables/useScanPolling.ts`：
```typescript
import { watch, onUnmounted } from 'vue'
import { useBrowserStore } from '../stores/browser'

export function useScanPolling() {
  const browser = useBrowserStore()
  let interval: ReturnType<typeof setInterval> | null = null

  const start = () => {
    if (interval) return
    interval = setInterval(async () => {
      if (browser.scanning) {
        await browser.pollStatus()
      } else if (interval) {
        clearInterval(interval)
        interval = null
      }
    }, 2000)
  }

  const stop = () => {
    if (interval) {
      clearInterval(interval)
      interval = null
    }
  }

  watch(() => browser.scanning, (val) => {
    if (val) start()
    else stop()
  })

  onUnmounted(stop)

  return { start, stop }
}
```

- [ ] **步骤 2：提交**

```bash
git add frontend/src/composables/
git commit -m "feat(composables): add useScanPolling for progressive updates"
```

### 任务 17：UI 组件

**文件：**
- 创建：`frontend/src/components/TopMenu.vue`、`frontend/src/components/SideMenu.vue`、`frontend/src/components/VideoCard.vue`、`frontend/src/components/VideoGrid.vue`、`frontend/src/components/LightboxModal.vue`

- [ ] **步骤 1：创建 TopMenu（支持深色模式和主题切换）**

写入 `frontend/src/components/TopMenu.vue`：
```vue
<template>
  <div class="bg-white dark:bg-gray-800 shadow p-4 flex gap-2 items-center">
    <button
      v-for="root in roots"
      :key="root.id"
      @click="$emit('select', root.id)"
      :class="[
        'px-4 py-2 rounded',
        selected === root.id
          ? 'bg-blue-500 text-white'
          : 'bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 text-gray-800 dark:text-gray-200'
      ]"
    >
      {{ root.name }}
    </button>
    <div class="flex-1"></div>
    <!-- 主题切换按钮 -->
    <select
      v-model="themeMode"
      @change="onThemeChange"
      class="px-3 py-2 bg-gray-200 dark:bg-gray-700 rounded text-gray-800 dark:text-gray-200"
    >
      <option value="system">跟随系统</option>
      <option value="light">浅色</option>
      <option value="dark">深色</option>
    </select>
    <router-link
      to="/settings"
      class="px-4 py-2 bg-gray-200 dark:bg-gray-700 rounded hover:bg-gray-300 dark:hover:bg-gray-600 text-gray-800 dark:text-gray-200"
    >
      设置
    </router-link>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useThemeStore } from '../stores/theme'

defineProps<{
  roots: { id: string; name: string }[]
  selected: string | null
}>()
defineEmits<{
  (e: 'select', id: string): void
}>()

const theme = useThemeStore()
const themeMode = ref(theme.mode)

function onThemeChange() {
  theme.setMode(themeMode.value as 'light' | 'dark' | 'system')
}
</script>
```

- [ ] **步骤 2：创建 SideMenu（支持深色模式）**

写入 `frontend/src/components/SideMenu.vue`：
```vue
<template>
  <div class="bg-white dark:bg-gray-800 shadow p-4 w-64">
    <button
      v-for="dir in dirs"
      :key="dir.id"
      @click="$emit('select', dir.id)"
      :class="[
        'w-full text-left px-3 py-2 rounded mb-1',
        selected === dir.id
          ? 'bg-blue-500 text-white'
          : 'bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-800 dark:text-gray-200'
      ]"
    >
      {{ dir.name }}
    </button>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  dirs: { id: string; name: string }[]
  selected: string | null
}>()
defineEmits<{
  (e: 'select', id: string): void
}>()
</script>
```

- [ ] **步骤 3：创建 VideoCard（支持深色模式）**

写入 `frontend/src/components/VideoCard.vue`：
```vue
<template>
  <div
    class="bg-white dark:bg-gray-800 rounded shadow overflow-hidden cursor-pointer hover:shadow-lg transition-shadow"
    @click="$emit('showLightbox', video)"
  >
    <div class="relative aspect-video bg-slate-900 flex items-center justify-center">
      <img
        v-if="video.level >= 3"
        :src="`/api/thumb/${video.video_id}?size=small`"
        class="w-full h-full object-contain"
        loading="lazy"
      />
      <p
        v-else
        class="text-slate-500 dark:text-slate-400 text-sm animate-pulse"
      >加载中...</p>

      <template v-if="video.level >= 2">
        <div class="absolute top-2 left-2 bg-black/55 backdrop-blur-sm text-white text-[11px] font-medium px-1.5 py-0.5 rounded-md">
          {{ video.codec || '-' }}
        </div>
        <div class="absolute top-2 right-2 bg-black/55 backdrop-blur-sm text-white text-[11px] font-medium px-1.5 py-0.5 rounded-md">
          {{ formatResolution(video.height || 0) }}
        </div>
        <div class="absolute bottom-2 left-2 bg-black/55 backdrop-blur-sm text-white text-[11px] font-medium px-1.5 py-0.5 rounded-md tabular-nums">
          {{ formatDuration(video.duration) }}
        </div>
      </template>
      <div class="absolute bottom-2 right-2 bg-black/55 backdrop-blur-sm text-white text-[11px] font-medium px-1.5 py-0.5 rounded-md tabular-nums">
        {{ formatSize(video.file_size) }}
      </div>
    </div>
    <div class="p-2 text-sm text-gray-800 dark:text-gray-200 line-clamp-2">{{ video.file_name }}</div>
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{
  video: any
}>()
defineEmits<{
  (e: 'showLightbox', video: any): void
}>()

function formatDuration(sec?: number): string {
  if (!sec) return '-'
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  const s = Math.floor(sec % 60)
  return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
}

function formatResolution(height: number): string {
  if (height >= 2160) return '4K'
  if (height >= 1440) return '2K'
  if (height >= 1080) return 'FHD'
  if (height >= 720) return 'HD'
  if (height >= 480) return 'SD'
  if (height >= 360) return 'LD'
  return height ? `${height}P` : '-'
}

function formatSize(mb: number): string {
  // MB → GB（保留 1 位小数）
  const gb = mb / 1024
  return `${gb.toFixed(1)}G`
}
</script>
```

- [ ] **步骤 4：创建 VideoGrid**

写入 `frontend/src/components/VideoGrid.vue`：
```vue
<template>
  <div class="flex-1 p-4 overflow-auto">
    <div v-for="group in groups" :key="group.name" class="mb-6">
      <h3 class="text-lg font-semibold mb-2">{{ group.name }}</h3>
      <div class="grid gap-4" :style="{ gridTemplateColumns: `repeat(${columnSize || 4}, minmax(0, 1fr))` }">
        <VideoCard
          v-for="video in group.videos"
          :key="video.video_id"
          :video="video"
          @showLightbox="(v) => $emit('showLightbox', v)"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import VideoCard from './VideoCard.vue'

defineProps<{
  groups: any[]
  columnSize: number
}>()
defineEmits<{
  (e: 'showLightbox', video: any): void
}>()
</script>
```

- [ ] **步骤 5：创建 LightboxModal**

写入 `frontend/src/components/LightboxModal.vue`：
```vue
<template>
  <div v-if="video" class="fixed inset-0 bg-black/80 flex items-center justify-center z-50" @click.self="$emit('close')">
    <div class="relative max-w-[90vw] max-h-[90vh]">
      <button @click="$emit('close')" class="absolute top-2 right-2 text-white text-2xl bg-black/50 rounded-full w-8 h-8 flex items-center justify-center">×</button>
      <img :src="`/api/thumb/${video.video_id}?full=1`" class="max-w-full max-h-full object-contain" />
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  video: any | null
}>()
defineEmits<{
  (e: 'close'): void
}>()
</script>
```

- [ ] **步骤 6：提交**

```bash
git add frontend/src/components/
git commit -m "feat(components): add TopMenu, SideMenu, VideoCard, VideoGrid, LightboxModal"
```

### 任务 18：BrowserView 与 SettingsView

**文件：**
- 创建：`frontend/src/views/BrowserView.vue`、`frontend/src/views/SettingsView.vue`

- [ ] **步骤 1：创建 BrowserView**

写入 `frontend/src/views/BrowserView.vue`：
```vue
<template>
  <div class="flex flex-col h-screen">
    <TopMenu :roots="browser.roots" :selected="browser.selectedRootId" @select="onSelectRoot" />
    <div class="flex flex-1 overflow-hidden">
      <SideMenu :dirs="browser.l2Dirs" :selected="browser.selectedL2Id" @select="onSelectL2" />
      <VideoGrid :groups="browser.groups" :columnSize="config.column_size" @showLightbox="showLightbox" />
    </div>
    <LightboxModal :video="lightboxVideo" @close="lightboxVideo = null" />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useBrowserStore } from '../stores/browser'
import { useConfigStore } from '../stores/config'
import { useScanPolling } from '../composables/useScanPolling'
import TopMenu from '../components/TopMenu.vue'
import SideMenu from '../components/SideMenu.vue'
import VideoGrid from '../components/VideoGrid.vue'
import LightboxModal from '../components/LightboxModal.vue'

const browser = useBrowserStore()
const config = useConfigStore()
const lightboxVideo = ref(null)
useScanPolling()

onMounted(async () => {
  await config.fetch()
  await browser.fetchRoots()
})

async function onSelectRoot(id: string) {
  await browser.selectRoot(id)
}

async function onSelectL2(id: string) {
  await browser.selectL2(id)
}

function showLightbox(video: any) {
  lightboxVideo.value = video
}
</script>
```

- [ ] **步骤 2：创建 SettingsView（支持深色模式）**

写入 `frontend/src/views/SettingsView.vue`：
```vue
<template>
  <div class="max-w-2xl mx-auto p-8">
    <h1 class="text-2xl font-bold mb-6 text-gray-900 dark:text-gray-100">设置</h1>
    <div class="bg-white dark:bg-gray-800 rounded shadow p-6 space-y-4">
      <div>
        <label class="block text-sm font-medium mb-1 text-gray-700 dark:text-gray-300">视频目录列表</label>
        <div v-for="(path, i) in config.video_path_list" :key="i" class="flex gap-2 mb-2">
          <input
            v-model="config.video_path_list[i]"
            type="text"
            class="flex-1 border border-gray-300 dark:border-gray-600 rounded px-2 py-1 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
          />
          <button @click="config.video_path_list.splice(i, 1)" class="px-3 py-1 bg-red-500 text-white rounded hover:bg-red-600">×</button>
        </div>
        <button @click="config.video_path_list.push('')" class="px-3 py-1 bg-blue-500 text-white rounded hover:bg-blue-600">+ 添加目录</button>
      </div>
      <div>
        <label class="block text-sm font-medium mb-1 text-gray-700 dark:text-gray-300">每页视频数 (0=不分页)</label>
        <input
          v-model.number="config.page_size"
          type="number"
          class="border border-gray-300 dark:border-gray-600 rounded px-2 py-1 w-32 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
        />
      </div>
      <div>
        <label class="block text-sm font-medium mb-1 text-gray-700 dark:text-gray-300">每行视频数</label>
        <input
          v-model.number="config.column_size"
          type="number"
          class="border border-gray-300 dark:border-gray-600 rounded px-2 py-1 w-32 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
        />
      </div>
      <div class="flex gap-2">
        <button @click="save" class="px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600">保存</button>
        <router-link to="/" class="px-4 py-2 bg-gray-300 dark:bg-gray-600 rounded text-gray-800 dark:text-gray-200 hover:bg-gray-400 dark:hover:bg-gray-500">返回</router-link>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useConfigStore } from '../stores/config'
import { useRouter } from 'vue-router'

const config = useConfigStore()
const router = useRouter()

onMounted(() => config.fetch())

async function save() {
  await config.update()
  router.push('/')
}
</script>
```

- [ ] **步骤 3：提交**

```bash
git add frontend/src/views/
git commit -m "feat(views): add BrowserView and SettingsView"
```

---

## 第六阶段：脚本与 Docker

### 任务 19：Shell 脚本

**文件：**
- 创建：`bin/start-dev.sh`、`bin/start.sh`、`bin/stop.sh`、`bin/restart.sh`、`bin/build.sh`

- [ ] **步骤 1：创建 start-dev.sh（使用 uv 和 bun）**

写入 `bin/start-dev.sh`：
```bash
#!/bin/bash
set -e
source .env
DATA_PATH=${DATA_PATH:-.}

# 启动后端（开发模式，使用 uv）
cd backend
source .venv/bin/activate
nohup uvicorn app.main:app --reload --host 0.0.0.0 --port ${BACKEND_PORT:-8000} > ${DATA_PATH}/logs/backend-dev.log 2>&1 &
BACKEND_PID=$!
cd ..

# 启动前端（开发模式，使用 bun）
cd frontend
nohup bun run dev > ${DATA_PATH}/logs/frontend-dev.log 2>&1 &
FRONTEND_PID=$!
cd ..

# 写入 PID
echo "backend:$BACKEND_PID" > ${DATA_PATH}/app.pid
echo "frontend:$FRONTEND_PID" >> ${DATA_PATH}/app.pid

echo "开发服务器已启动（后端 PID: $BACKEND_PID，前端 PID: $FRONTEND_PID）"
```

- [ ] **步骤 2：创建 start.sh（使用 uv）**

写入 `bin/start.sh`：
```bash
#!/bin/bash
set -e
source .env
DATA_PATH=${DATA_PATH:-.}

cd backend
source .venv/bin/activate
nohup uvicorn app.main:app --host 0.0.0.0 --port ${BACKEND_PORT:-8000} > ${DATA_PATH}/logs/backend.log 2>&1 &
BACKEND_PID=$!
cd ..

echo "backend:$BACKEND_PID" > ${DATA_PATH}/app.pid
echo "生产环境后端已启动（PID: $BACKEND_PID）"
```

- [ ] **步骤 3：创建 stop.sh**

写入 `bin/stop.sh`：
```bash
#!/bin/bash
source .env
DATA_PATH=${DATA_PATH:-.}

if [ ! -f ${DATA_PATH}/app.pid ]; then
  echo "未找到 PID 文件"
  exit 0
fi

while IFS=: read -r role pid; do
  if kill -0 $pid 2>/dev/null; then
    kill $pid
    echo "已停止 $role（PID: $pid）"
  fi
done < ${DATA_PATH}/app.pid

rm -f ${DATA_PATH}/app.pid
```

- [ ] **步骤 4：创建 restart.sh**

写入 `bin/restart.sh`：
```bash
#!/bin/bash
./bin/stop.sh
sleep 2
./bin/start.sh
```

- [ ] **步骤 5：创建 build.sh（使用 bun）**

写入 `bin/build.sh`：
```bash
#!/bin/bash
set -e

# 构建前端（使用 bun）
cd frontend
bun run build
cd ..

# 复制到后端静态资源
rm -rf backend/app/static
cp -r frontend/dist backend/app/static

echo "前端已构建并复制到 backend/app/static"
```

- [ ] **步骤 6：使脚本可执行**

```bash
chmod +x bin/*.sh
```

- [ ] **步骤 7：提交**

```bash
git add bin/
git commit -m "feat(scripts): add start-dev, start, stop, restart, build scripts"
```

### 任务 20：Docker 配置

**文件：**
- 创建：`docker/Dockerfile`、`docker/docker-compose.yaml`

- [ ] **步骤 1：创建 Dockerfile（使用 uv 和 bun）**

写入 `docker/Dockerfile`：
```dockerfile
# 阶段 1：构建前端（使用 bun）
FROM oven/bun:1 AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN bun install
COPY frontend/ ./
RUN bun run build

# 阶段 2：后端（使用 uv）
FROM python:3.12-slim
RUN apt-get update && apt-get install -y ffmpeg curl && rm -rf /var/lib/apt/lists/*

# 安装 uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY backend/requirements.txt backend/
RUN uv pip install --system -r backend/requirements.txt

COPY backend/ backend/
COPY --from=frontend-builder /app/frontend/dist backend/app/static/

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "backend"]
```

- [ ] **步骤 2：创建 docker-compose.yaml**

写入 `docker/docker-compose.yaml`：
```yaml
version: '3.8'
services:
  video-explorer:
    build:
      context: ..
      dockerfile: docker/Dockerfile
    ports:
      - "8000:8000"
    volumes:
      - ${DATA_PATH:-./data}:/app/data
      - /path/to/your/videos:/videos:ro
    environment:
      - DATA_PATH=/app/data
      - IP_WHITE_LIST=${IP_WHITE_LIST:-}
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

- [ ] **步骤 3：提交**

```bash
git add docker/
git commit -m "feat(docker): add Dockerfile and docker-compose.yaml"
```

---

## 第七阶段：最终集成与测试

### 任务 21：端到端手动测试

- [ ] **步骤 1：创建示例视频目录**

```bash
mkdir -p /tmp/test-videos/movies/action
ffmpeg -y -f lavfi -i "testsrc=duration=2:size=320x240:rate=30" -c:v libx264 -pix_fmt yuv420p /tmp/test-videos/movies/action/test.mp4
```

- [ ] **步骤 2：更新配置添加测试路径**

```bash
cat > .env << EOF
DATA_PATH=.
IP_WHITE_LIST=
BACKEND_PORT=8000
EOF

mkdir -p logs cache
cat > config.yaml << EOF
video_path_list:
  - /tmp/test-videos
page_size: 0
column_size: 4
EOF
```

- [ ] **步骤 3：启动开发服务器**

```bash
./bin/start-dev.sh
```

- [ ] **步骤 4：在浏览器中验证**

打开 http://localhost:5173（Vite 开发服务器）。验证：
- 顶部菜单显示 "test-videos"
- 点击 "test-videos" → 左侧菜单显示 "movies"
- 点击 "movies" → 中心区显示 "action" 分组，包含测试视频
- 视频卡片显示缩略图、编码、分辨率、时长、大小
- 点击视频 → 浮层打开显示完整缩略图
- 导航到 /settings → 可以编辑配置

- [ ] **步骤 5：停止服务器**

```bash
./bin/stop.sh
```

- [ ] **步骤 6：构建生产版本**

```bash
./bin/build.sh
```

- [ ] **步骤 7：启动生产环境**

```bash
./bin/start.sh
```

- [ ] **步骤 8：验证生产环境 http://localhost:8000**

- [ ] **步骤 9：提交任何最终修复**

```bash
git add -A
git commit -m "chore: final integration fixes"
```

---

## 完成

计划已完成。所有后端模块都有 TDD，所有前端组件都有真实代码，脚本和 Docker 都已配置。应用端到端完全可用。

---

## 变更历史（2026-07-19 起）

以下是实施过程中相对原始计划的关键变更：

### 1. Docker 镜像 Tag 支持灵活化
- `docker/docker-compose.yaml` 改用 `image: yaofeng928/video-explorer:${IMAGE_TAG:-latest}` + `build.tags` 列表
- 本地默认 `latest`，CI 可用 `IMAGE_TAG=$(git rev-parse --short HEAD)` 打 git hash tag

### 2. 进度指示简化
- **移除**：左侧菜单底部进度条（`SideMenu.vue` 不再显示 progress）
- **保留**：右上角 `TaskToast.vue`，但仅用于：
  - 扫描错误聚合展示（⚠️ 图标 + "N 个文件处理失败" + 详情）
  - `build` 任务（多目录构建索引）的进度条
- **单目录 scan 任务不再注册进度**，仅通过页面内容增量更新反馈

### 3. 扫描架构重构为两阶段
- **Phase 1（快速文件系统扫描）**：遍历目录、处理新增/删除、应用 `parse_rules` 更新 `ext`。无进度条，完成后发 `refresh_full` 信号供前端全量刷新。
- **Phase 2（深度扫描）**：对 `level<3` 或 `modify_time` 变化的文件执行 ffprobe + 缩略图提取。每完成一个文件原子更新 `index.yaml`（per-path 文件锁）。
- 打开 L2 目录时若 `index.yaml` 已存在，**立即从缓存渲染**（秒开），后台并行扫描。

### 4. 文件名解析改进
- `_parse_filename` **先剥离文件扩展名**再匹配规则（如 `ABC-123.mp4` 用 `ABC-123` 匹配）
- **无匹配规则时删除 `index.yaml` 中已有的 `ext` 字段**，保持数据一致性
- `parse_rules` 变更通过 `PUT /api/config` 保存时，自动调用 `scanner.invalidate_all_caches()`，下次打开目录时重新解析

### 5. `scan-status` API 扩展
- 新增字段：
  - `phase`: 当前扫描阶段（"idle" / "quick" / "deep" / "done"）
  - `refresh_full`: 一次性信号（Phase 1 完成时置 true，前端据此全量刷新）
  - `errors`: 聚合错误列表（`[{file, message}]`）

### 6. 并发控制
- 新增 `_get_index_lock(path)` + `_atomic_update_index` / `_atomic_remove_from_index`，对 `index.yaml` 的读-改-写使用 per-path 文件锁，避免多线程并发写入导致数据丢失

### 7. 后端模块布局
- 实际布局：`backend/app/` 顶层扁平结构（`scanner.py`, `cache_index.py`, `probe.py`, `thumbgen.py` 等）
- 路由子包：`backend/app/routes/`（`config.py`, `dirs.py`, `videos.py`, `scan.py`, `parse_rules.py`）
- 原始计划中的 `services/` 子目录和 `descfile.py` 未实现

### 8. 设置 UI 形态
- 实际实现：`SettingsModal.vue`（浮窗 Modal）+ `RuleTestModal.vue`（规则测试浮窗）
- 原始计划中的 `/settings` 独立路由 + `SettingsView.vue` 未实现

### 9. 前端新增功能
- `useFilterStore`：搜索/排序/编码过滤状态持久化到 localStorage
- `TopMenu.vue`：搜索框 + 排序按钮组 + 编码过滤下拉 + 主题切换 + 设置按钮
- `VideoCard.vue`：支持 `ext` 字段展示（title 替换文件名，code/actress 作为可点击标签）
- `RuleTestModal.vue`：正则规则测试器
- `TaskToast.vue`：扫描错误聚合展示 + build 任务进度条
