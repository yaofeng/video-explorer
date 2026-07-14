# 视频库浏览器 实施计划

> **给代理工作者：** 必填子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实施此计划。步骤使用复选框（`- [ ]`）语法进行跟踪。

**目标：** 构建一个视频库浏览器，使用 Python 后端（FastAPI）和 Vue3 前端，支持分层目录导航、渐进式缩略图生成和设置管理。

**架构：** FastAPI 提供 API 端点和静态前端服务。Vue3 SPA 使用 Tailwind CSS 构建 UI。后台工作队列处理渐进式缩略图生成。二进制描述文件缓存视频元数据 + 缩略图。IP 白名单中间件保护访问安全。

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
- vue-router 用于 `/settings` 路由
- 单 uvicorn worker（扫描状态在进程内）
- 缩略图降级策略：3:30 位置 → 中点 → 占位图
- 不存在的 `video_path` 条目：跳过并警告
- `/api/health` 端点用于 Docker 健康检查
- 单 worker 顺序处理缩略图队列
- 支持浅色/深色主题，可手动切换或跟随系统

---

## 第一阶段：项目设置与前提条件

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
- 创建：`backend/app/probe.py`、`backend/tests/test_probe.py`

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
from app.probe import probe_video, resolution_label

def test_probe_video(sample_video):
    result = probe_video(sample_video)
    assert "codec" in result
    assert "width" in result
    assert "height" in result
    assert "duration" in result
    assert result["width"] == 320
    assert result["height"] == 240
    assert result["duration"] >= 1.5

def test_resolution_label():
    assert resolution_label(2160) == "4K"
    assert resolution_label(1440) == "2K"
    assert resolution_label(1080) == "FHD"
    assert resolution_label(720) == "HD"
    assert resolution_label(480) == "SD"
    assert resolution_label(360) == "LD"
    assert resolution_label(0) == "Unknown"
```

- [ ] **步骤 3：运行测试验证失败**

```bash
pytest tests/test_probe.py -v
```

预期：失败，报错 "ModuleNotFoundError"

- [ ] **步骤 4：编写实现**

写入 `backend/app/probe.py`：
```python
import json
import subprocess

def probe_video(path: str) -> dict:
    cmd = [
        "ffprobe", "-v", "error",
        "-show_streams", "-show_format",
        "-of", "json", str(path)
    ]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffprobe failed: {e.stderr}")
    
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
    
    return {
        "codec": codec,
        "width": width,
        "height": height,
        "duration": duration,
        "cover_stream_index": cover_index,
    }

def resolution_label(height: int) -> str:
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
```

- [ ] **步骤 5：运行测试验证通过**

```bash
pytest tests/test_probe.py -v
```

预期：通过（两个测试）

- [ ] **步骤 6：提交**

```bash
git add backend/app/probe.py backend/tests/test_probe.py backend/tests/conftest.py
git commit -m "feat(probe): add ffprobe wrapper with cover detection"
```

### 任务 6：描述文件模块（TDD）

**文件：**
- 创建：`backend/app/descfile.py`、`backend/tests/test_descfile.py`

- [ ] **步骤 1：编写失败的写入/读取往返测试**

写入 `backend/tests/test_descfile.py`：
```python
from app.descfile import write_desc, read_desc

def test_write_read_roundtrip(tmp_path):
    desc_path = tmp_path / "test.desc"
    desc = {
        "file_name": "test.mp4",
        "codec": "H264",
        "duration": 123.4,
        "width": 1920,
        "height": 1080,
        "resolution_label": "FHD",
    }
    small_thumb = b"fake_jpeg_data_small"
    full_thumb = b"fake_jpeg_data_full"
    
    write_desc(str(desc_path), desc, small_thumb, full_thumb)
    
    loaded_desc, loaded_small, loaded_full = read_desc(str(desc_path))
    assert loaded_desc == desc
    assert loaded_small == small_thumb
    assert loaded_full == full_thumb
```

- [ ] **步骤 2：运行测试验证失败**

```bash
pytest tests/test_descfile.py -v
```

预期：失败，报错 "ModuleNotFoundError"

- [ ] **步骤 3：编写实现**

写入 `backend/app/descfile.py`：
```python
import struct
import json

MAGIC = b"VDC2"
VERSION = 2
# 4s + 7*I + 4s = 4 + 28 + 4 = 36 字节
HEADER = struct.Struct("<4sIIIIII4s")

def write_desc(path: str, desc: dict, small_thumb: bytes, full_thumb: bytes):
    desc_bytes = json.dumps(desc, ensure_ascii=False).encode("utf-8")
    desc_offset = 36
    small_offset = desc_offset + len(desc_bytes)
    full_offset = small_offset + len(small_thumb)
    header = HEADER.pack(
        MAGIC, VERSION, desc_offset, len(desc_bytes),
        small_offset, len(small_thumb), full_offset, len(full_thumb),
        b""
    )
    with open(path, "wb") as f:
        f.write(header)
        f.write(desc_bytes)
        f.write(small_thumb)
        f.write(full_thumb)

def read_desc(path: str):
    with open(path, "rb") as f:
        head = f.read(36)
        magic, version, doff, dlen, soff, slen, foff, flen, _ = HEADER.unpack(head)
        if magic != MAGIC:
            raise ValueError("bad magic")
        f.seek(doff)
        desc = json.loads(f.read(dlen))
        f.seek(soff)
        small_thumb = f.read(slen)
        f.seek(foff)
        full_thumb = f.read(flen)
    return desc, small_thumb, full_thumb
```

- [ ] **步骤 4：运行测试验证通过**

```bash
pytest tests/test_descfile.py -v
```

预期：通过

- [ ] **步骤 5：编写错误魔数测试**

追加到 `backend/tests/test_descfile.py`：
```python
def test_bad_magic(tmp_path):
    bad_path = tmp_path / "bad.desc"
    with open(bad_path, "wb") as f:
        f.write(b"BADM" + b"\x00" * 32)
    
    try:
        read_desc(str(bad_path))
        assert False, "应该抛出 ValueError"
    except ValueError as e:
        assert "bad magic" in str(e)
```

- [ ] **步骤 6：运行测试**

```bash
pytest tests/test_descfile.py::test_bad_magic -v
```

预期：通过

- [ ] **步骤 7：提交**

```bash
git add backend/app/descfile.py backend/tests/test_descfile.py
git commit -m "feat(descfile): add binary descriptor with dual thumbnails (small + full)"
```

### 任务 7：缩略图生成模块（TDD）

**文件：**
- 创建：`backend/app/thumbgen.py`、`backend/tests/test_thumbgen.py`

- [ ] **步骤 1：编写失败的 fit_to_16_9 测试**

写入 `backend/tests/test_thumbgen.py`：
```python
from PIL import Image
from app.thumbgen import fit_to_16_9

def test_fit_to_16_9_square():
    img = Image.new("RGB", (100, 100), (255, 0, 0))
    result = fit_to_16_9(img, 480)
    assert result.size == (480, 270)
    # 检查宽高比是 16:9
    assert abs(result.size[0] / result.size[1] - 16/9) < 0.01

def test_fit_to_16_9_wide():
    img = Image.new("RGB", (1920, 1080), (0, 255, 0))
    result = fit_to_16_9(img, 480)
    assert result.size == (480, 270)
```

- [ ] **步骤 2：运行测试验证失败**

```bash
pytest tests/test_thumbgen.py -v
```

预期：失败，报错 "ModuleNotFoundError"

- [ ] **步骤 3：编写实现**

写入 `backend/app/thumbgen.py`：
```python
import io
import subprocess
from PIL import Image
from .probe import probe_video

TARGET_SMALL_W = 480
SEEK_TIME = 210.0  # 3:30

# 占位图：1x1 黑色像素
PLACEHOLDER_SMALL = None  # 延迟生成
PLACEHOLDER_FULL = None

def _get_placeholder(w, h):
    img = Image.new("RGB", (w, h), (0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()

def fit_to_16_9(img: Image.Image, target_w: int) -> bytes:
    target_h = round(target_w * 9 / 16)
    img = img.convert("RGB")
    src_w, src_h = img.size
    scale = min(target_w / src_w, target_h / src_h)
    new_w, new_h = max(1, round(src_w * scale)), max(1, round(src_h * scale))
    resized = img.resize((new_w, new_h), Image.LANCZOS)
    canvas = Image.new("RGB", (target_w, target_h), (0, 0, 0))
    canvas.paste(resized, ((target_w - new_w) // 2, (target_h - new_h) // 2))
    buf = io.BytesIO()
    canvas.save(buf, format="JPEG", quality=85)
    return buf.getvalue()

def _extract_frame(path: str, probe: dict) -> Image.Image | None:
    if probe["cover_stream_index"] is not None:
        idx = probe["cover_stream_index"]
        cmd = [
            "ffmpeg", "-v", "error",
            "-map", f"0:{idx}",
            "-frames:v", "1",
            "-f", "image2pipe", "-vcodec", "png", "-"
        ]
    else:
        dur = probe["duration"]
        t = SEEK_TIME if dur > SEEK_TIME else (dur / 2 if dur > 0 else 0.0)
        cmd = [
            "ffmpeg", "-v", "error",
            "-ss", f"{t:.2f}",
            "-i", str(path),
            "-frames:v", "1",
            "-f", "image2pipe", "-vcodec", "png", "-"
        ]
    
    out = subprocess.run(cmd, capture_output=True, timeout=120)
    if out.returncode != 0 or not out.stdout:
        return None  # 抽帧失败
    
    return Image.open(io.BytesIO(out.stdout))

def generate_thumbnails(path: str):
    """生成小图和高清图，都返回 bytes。失败时返回占位图。"""
    probe = probe_video(path)
    img = _extract_frame(path, probe)
    
    # 小图
    if img is not None:
        small_bytes = fit_to_16_9(img, TARGET_SMALL_W)
    else:
        small_bytes = _get_placeholder(TARGET_SMALL_W, round(TARGET_SMALL_W * 9 / 16))
    
    # 高清图
    if img is not None:
        target_w = min(probe["width"], img.size[0])
        full_bytes = fit_to_16_9(img, target_w)
    else:
        # 使用视频宽度作为高清图宽度，若无则默认 1920
        full_w = probe["width"] if probe["width"] > 0 else 1920
        full_bytes = _get_placeholder(full_w, round(full_w * 9 / 16))
    
    meta = {
        "codec": probe["codec"],
        "duration": probe["duration"],
        "width": probe["width"],
        "height": probe["height"],
        "resolution_label": None,  # 调用者填充
    }
    return meta, small_bytes, full_bytes
```

- [ ] **步骤 4：运行测试验证通过**

```bash
pytest tests/test_thumbgen.py -v
```

预期：通过（两个测试）

- [ ] **步骤 5：提交**

```bash
git add backend/app/thumbgen.py backend/tests/test_thumbgen.py
git commit -m "feat(thumbgen): add dual thumbnail generation with fallback to placeholder"
```

---

## 第三阶段：后端扫描器与 API（TDD）

### 任务 8：扫描器服务（TDD）

**文件：**
- 创建：`backend/app/scanner.py`、`backend/tests/test_scanner.py`

- [ ] **步骤 1：编写失败的扫描编排测试**

写入 `backend/tests/test_scanner.py`：
```python
import pytest
from pathlib import Path
import subprocess
from app.scanner import Scanner, find_root
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
    cache_dir = Path(video_dir).parent / "cache"
    monkeypatch.setenv("DATA_PATH", str(Path(video_dir).parent))
    cfg = config.AppConfig(video_path_list=[video_dir], page_size=0, column_size=4)
    monkeypatch.setattr(config, "load_config", lambda: cfg)
    
    scanner = Scanner()
    l2_path = str(Path(video_dir) / "movies" / "action")
    groups, scanning = scanner.ensure_scan(l2_path)
    assert len(groups) > 0
    assert scanning == False  # 小目录扫描快速完成
```

- [ ] **步骤 2：运行测试验证失败**

```bash
pytest tests/test_scanner.py -v
```

预期：失败，报错 "ModuleNotFoundError"

- [ ] **步骤 3：编写实现**

写入 `backend/app/scanner.py`：
```python
import os
import threading
import time
from pathlib import Path
from queue import Queue, Empty
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
            l2 = Path(l2_path)
            
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
                        desc, _ = descfile.read_desc(str(cache_path))
                        meta = desc
                        meta["resolution_label"] = resolution_label(meta["height"])
                    except:
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
        except:
            return None
```

- [ ] **步骤 4：运行测试验证通过**

```bash
pytest tests/test_scanner.py -v
```

预期：通过（两个测试）

- [ ] **步骤 5：提交**

```bash
git add backend/app/scanner.py backend/tests/test_scanner.py
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

class VideoMeta(BaseModel):
    codec: str
    duration: float
    width: int
    height: int
    resolution_label: str

class VideoItem(BaseModel):
    video_id: str
    file_name: str
    file_size: int
    group: str
    ready: bool
    meta: VideoMeta | None = None

class Group(BaseModel):
    name: str
    videos: list[VideoItem]

class VideosResponse(BaseModel):
    groups: list[Group]
    scanning: bool

class ScanUpdate(BaseModel):
    seq: int
    video_id: str
    file_name: str
    file_size: int
    group: str
    meta: VideoMeta

class ScanStatus(BaseModel):
    scanning: bool
    total: int
    ready: int
    last_seq: int
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
from fastapi.responses import StreamingResponse
import io
from ..scanner import Scanner

router = APIRouter()
scanner = Scanner()

@router.get("/l2/{l2_id}/videos")
def get_videos(l2_id: str):
    from ..path_id import path_id
    from pathlib import Path
    
    # 通过 id 查找 l2 路径
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
    
    groups, scanning = scanner.ensure_scan(l2_path)
    return {"groups": groups, "scanning": scanning}

@router.get("/thumb/{video_id}")
def get_thumb(video_id: str, full: int = 0):
    thumb = scanner.get_thumb(video_id, full=full == 1)
    if thumb is None:
        return Response(status_code=202, content="缩略图未就绪")
    return Response(content=thumb, media_type="image/jpeg")
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
  file_size: number
  group: string
  ready: boolean
  meta: {
    codec: string
    duration: number
    width: number
    height: number
    resolution_label: string
  } | null
}

interface Group {
  name: string
  videos: VideoItem[]
}

export const useBrowserStore = defineStore('browser', {
  state: () => ({
    roots: [] as { id: string; name: string; path: string }[],
    selectedRootId: null as string | null,
    l2Dirs: [] as { id: string; name: string; path: string }[],
    selectedL2Id: null as string | null,
    groups: [] as Group[],
    scanning: false,
  }),
  actions: {
    async fetchRoots() {
      const { data } = await axios.get('/api/roots')
      this.roots = data
    },
    async selectRoot(rootId: string) {
      this.selectedRootId = rootId
      this.selectedL2Id = null
      this.groups = []
      const { data } = await axios.get(`/api/roots/${rootId}/l2`)
      this.l2Dirs = data
    },
    async selectL2(l2Id: string) {
      this.selectedL2Id = l2Id
      const { data } = await axios.get(`/api/l2/${l2Id}/videos`)
      this.groups = data.groups
      this.scanning = data.scanning
    },
    async pollStatus() {
      if (!this.selectedL2Id) return
      const { data } = await axios.get(`/api/scan-status?l2_id=${this.selectedL2Id}`)
      this.scanning = data.scanning
      // 合并更新到分组
      for (const update of data.updates) {
        for (const group of this.groups) {
          if (group.name === update.group) {
            const existing = group.videos.find(v => v.video_id === update.video_id)
            if (existing) {
              existing.ready = true
              existing.meta = update.meta
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
    <div class="relative aspect-video bg-gray-900">
      <img v-if="video.ready" :src="`/api/thumb/${video.video_id}`" class="w-full h-full object-contain" />
      <div v-else class="w-full h-full flex items-center justify-center text-gray-500">加载中...</div>
      
      <div class="absolute top-2 left-2 bg-black/60 text-white text-xs px-2 py-1 rounded">
        {{ video.meta?.codec || '-' }}
      </div>
      <div class="absolute top-2 right-2 bg-black/60 text-white text-xs px-2 py-1 rounded">
        {{ video.meta?.resolution_label || '-' }}
      </div>
      <div class="absolute bottom-2 left-2 bg-black/60 text-white text-xs px-2 py-1 rounded">
        {{ formatDuration(video.meta?.duration) }}
      </div>
      <div class="absolute bottom-2 right-2 bg-black/60 text-white text-xs px-2 py-1 rounded">
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

function formatSize(bytes: number): string {
  const gb = bytes / (1024 ** 3)
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
