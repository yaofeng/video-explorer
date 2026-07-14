# 视频库浏览器 设计文档

日期: 2026-07-14

## 1. 项目概述

一个视频文件浏览器，像文件浏览器一样浏览视频，**不做预览/播放**。

技术栈：
- 后端：Python 3.12 + FastAPI + uvicorn（使用 uv 管理环境）
- 前端：Vue 3 + Vite + Tailwind CSS（使用 Bun 作为 Node.js 运行时）
- 部署：后端单进程托管前端构建产物
- 媒体探测：ffmpeg / ffprobe（系统依赖）

目录结构：
```
video-explorer/
├── backend/        # 后端代码
├── frontend/       # 前端代码 (Vue3 + Vite + Tailwind)
├── bin/            # start-dev.sh / start.sh / stop.sh / restart.sh / build.sh
├── docker/         # Dockerfile / docker-compose.yaml
├── .env            # 环境变量
└── docs/           # 设计文档
```

## 2. 环境变量 (.env)

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DATA_PATH` | 数据目录，含 config.yaml、logs、cache | 当前目录 |
| `IP_WHITE_LIST` | IP 白名单(逗号分隔)，空=仅 localhost | (空) |

`DATA_PATH` 目录结构：
```
$DATA_PATH/
├── config.yaml     # 持久化配置
├── logs/           # 运行日志
└── cache/          # 视频描述文件 + 缩略图
```

localhost (127.0.0.1 / ::1) 始终放行，与白名单策略无关。

## 3. 设置功能 (config.yaml)

所有配置持久化到 `$DATA_PATH/config.yaml`。

```yaml
video_path_list:    # 视频目录绝对路径列表
  - /path/to/videos
page_size: 0        # 每页视频数，0=不分页全部展示
column_size: 4      # 每行视频卡片数量
```

提供 API 读写配置；前端有设置页面编辑这三个值。

## 4. 目录层级模型

视频目录按层级映射为 UI 菜单：
- 一级目录 → 顶部一级菜单
- 二级目录 → 左侧二级菜单
- 二级目录下更深层的视频 → 中心区，**按叶子目录分组**

**叶子目录定义**：从二级目录出发，沿含视频文件的路径深入，第一个"含视频文件或其子目录含视频文件"的终点目录。

### 4.1 分组规则

- 中心区每个组对应一个叶子目录
- 组标题 = 叶子目录相对于二级目录的路径（如 `4K电影/科幻`）
- **直接位于二级目录下的视频归入"未分组"组**，组标题为二级目录名或"未分组"

## 5. 视频描述文件 (cache)

### 5.1 存储结构

cache 目录结构与文件名与视频目录保持一致：
```
$DATA_PATH/cache/
└── <video_path 的相对层级镜像>/
    └── <原文件名>.<ext>       # 描述文件（含卡片小缩略图 + 高清缩略图），二进制
```

**例**：视频 `/videos/movies/sci-fi/dune.mkv`，若根为 `/videos`，
- 描述文件：`$DATA_PATH/cache/movies/sci-fi/dune.mkv`（包含小图和高清图）

### 5.2 描述文件格式

采用二进制格式，布局如下：

```
[MAGIC:4B] = "VDC2"
[VERSION:4B] = uint32 LE = 2
[DESC_OFFSET:4B] = uint32 LE，描述段偏移
[DESC_LEN:4B] = uint32 LE，描述段长度
[SMALL_THUMB_OFFSET:4B] = uint32 LE，小缩略图偏移
[SMALL_THUMB_LEN:4B] = uint32 LE，小缩略图长度
[FULL_THUMB_OFFSET:4B] = uint32 LE，高清缩略图偏移
[FULL_THUMB_LEN:4B] = uint32 LE，高清缩略图长度
[HEADER_PADDING:4B] = 保留，凑齐 36B 头部

[描述段 DESC_LEN 字节] = JSON UTF-8:
{
  "file_name": "dune.mkv",
  "file_path": "/videos/movies/sci-fi/dune.mkv",
  "file_size": 8589934592,           # 字节
  "mtime": 1720900000.0,             # 源文件修改时间，epoch 秒
  "duration": 9123.4,                # 秒
  "codec": "HEVC",                   # H264 / HEVC / ...
  "width": 3840,
  "height": 2160,
  "resolution_label": "4K",          # 4K/FHD/HD/SD/LD
  "has_cover": true                  # 是否使用内嵌封面
}

**分辨率标签规则**（按视频高度判定）：
- h ≥ 2160 → `4K`
- h ≥ 1440 → `2K`
- h ≥ 1080 → `FHD`
- h ≥ 720  → `HD`
- h ≥ 480  → `SD`
- h ≥ 360  → `LD`
- 其他     → `<h>P`（如 `240P`）

[小缩略图 SMALL_THUMB_LEN 字节] = JPEG 二进制（卡片预览用）
[高清缩略图 FULL_THUMB_LEN 字节] = JPEG 二进制（浮层查看用）
```

固定 36B 头部 → 解析时直接按偏移读取 JSON 段、小缩略图段和高清缩略图段，互不干扰。

### 5.3 缩略图生成规则

帧来源（卡片小图与高清图共用同一帧来源）：
1. **优先使用视频内嵌封面**（ffprobe 读取 attachment/cover 流）
2. 若无封面，**抽帧**：取 `00:03:30` 附近的帧（取时长内 3:30 位置；视频短于 3:30 则取中点）
3. 若抽帧失败，使用**占位图**（纯色或默认图标）

16:9 等比适配（卡片小图与高清图都遵循）：
- 原图为 16:9 → 直接用
- 原图非 16:9 → 等比缩小后居中填充到 16:9 画布（黑边填充）
- **不拉伸、不截取**

两档输出（**都存储在同一个描述文件中**）：
- **卡片小图**：JPEG，固定宽度 **480px**，16:9 = 270px。扫描时随描述文件一起生成。
- **高清图**：JPEG，宽度取**视频原始分辨率**（不超原宽，封面来源则取封面原宽），16:9 等比适配后输出。扫描时一起生成，避免懒生成带来的延迟。

> 封面来源的高清图受限于封面本身的分辨率（内嵌封面通常较低），无法超越原始封面画质。

### 5.4 扫描与更新策略

打开一个二级目录时触发扫描：

1. **遍历该二级目录下所有叶子目录**，收集视频文件
2. 对每个视频，检查 cache：
   - 描述文件不存在 → **新建**
   - 描述文件存在但源文件 mtime 晚于描述文件 mtime → **更新**
   - 描述文件存在且 mtime 不变 → **沿用**
3. 对 cache 中"源文件已不存在"的描述文件 → **删除**

扫描分两阶段：
- **快速阶段**：ffprobe 读元数据（编码/时长/分辨率/大小），秒级完成
- **慢速阶段**：逐个生成缩略图（抽帧/封面提取较慢）

## 6. 渐进式展示机制 (轮询)

### 6.1 流程

1. 前端打开二级目录 → `GET /api/l2/{l2_id}/videos` 
   - 后端立即返回：该目录下所有视频的**元数据**（来自已有描述文件或快速 ffprobe），按叶子目录分组
   - 同时启动后台扫描任务（补建/更新/删除描述文件 + 生成缩略图）
2. 前端渲染卡片骨架，`<img>` 指向 `/api/thumb/<视频id>`
3. 缩略图未就绪 → 后端返回 **202 + 占位图**；前端 img `onerror`/定时重试
4. 后台生成完一个缩略图 → 下次轮询/请求该 id 时返回 200 + JPEG

### 6.2 接口设计

`dir_id` = 目录绝对路径的稳定哈希（md5 前 16 位），全局唯一。
`video_id` = 视频文件绝对路径的稳定哈希（md5 前 16 位）。

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/config` | 读取配置 |
| PUT | `/api/config` | 更新配置 |
| GET | `/api/roots` | 列出 video_path_list（= 一级目录，顶部菜单）|
| GET | `/api/roots/{root_id}/l2` | 一级目录下的二级目录（左侧菜单）|
| GET | `/api/l2/{l2_id}/videos` | 二级目录下所有视频（按叶子目录分组）+ 触发后台扫描 |
| GET | `/api/thumb/{video_id}` | 卡片小缩略图（200 JPEG / 202 占位 / 304）|
| GET | `/api/thumb/{video_id}?full=1` | 高清缩略图（扫描时已生成，从描述文件读取）|
| GET | `/api/scan-status?l2_id=` | 扫描进度 + 新就绪缩略图 video_id 列表 |

**导航数据流**：
`/api/roots` 选一级目录 → `/api/roots/{root}/l2` 选二级目录 → `/api/l2/{l2}/videos` 出中心区。

所有 id 均可反查到绝对路径并校验是否落在 video_path_list 内，越权返回 403。

### 6.3 缓存与并发

- 描述文件即磁盘缓存，进程重启不丢失
- 后台扫描任务用单 worker 队列 + 文件锁防重复
- 缩略图请求与生成解耦：请求来了若正在生成则短暂等待或返回占位

## 7. 前端设计 (Vue3 + Tailwind)

### 7.1 页面结构

```
┌─────────────────────────────────────────────┐
│ 顶部一级菜单  [目录A][目录B][目录C]  [设置]    │
├──────────┬──────────────────────────────────┤
│ 二级菜单  │  中心区                           │
│ [子1]    │  ── 组: 4K电影/科幻 ──            │
│ [子2]    │  [卡片][卡片][卡片][卡片]          │
│ [子3]    │  ── 组: 4K电影/动作 ──            │
│          │  [卡片][卡片][卡片][卡片]          │
└──────────┴──────────────────────────────────┘
```

### 7.2 视频卡片

```
┌─────────────────────────┐
│ [HEVC]        [1080P]   │  ← 编码左上 / 分辨率右上
│                         │
│      缩略图 16:9         │
│                         │
│ [02:30:00]   [8.0G]     │  ← 时长左下 / 大小右下
├─────────────────────────┤
│ 文件名称(两行展示,省略)  │
└─────────────────────────┘
```

- 缩略图固定 16:9 容器，`object-fit: contain`（黑底填充，不拉伸不裁切）
- 文件名两行，超出省略号
- 编码/分辨率/时长/大小为半透明胶囊标签，叠在缩略图四角
- 卡片网格列数 = `column_size`（Tailwind 动态 grid-cols）
- 分页：当 `page_size > 0` 时启用，**分页作用于每个组内**（各组独立分页）；`page_size = 0` 时全部展示不分页

### 7.3 状态管理

- 轻量：Pinia store 管理目录树、当前选中、视频列表、缩略图就绪状态
- 轮询逻辑封装在 composable `useScanPolling`
- 缩略图加载用 `<img>` + 重试，配合扫描状态主动刷新就绪项

### 7.4 主题切换

支持**浅色主题**和**深色主题**，并提供以下切换机制：
- **手动切换**：用户在设置页面或顶部菜单可选择"浅色"、"深色"或"跟随系统"
- **跟随系统**：默认模式，根据操作系统/浏览器的 `prefers-color-scheme` 媒体查询自动切换
- **持久化**：用户选择保存到 `localStorage`，下次打开自动应用

**技术实现**：
- Tailwind CSS 配置 `darkMode: 'class'`，通过 `<html>` 标签的 `class="dark"` 控制
- Pinia store `useThemeStore` 管理当前主题状态（`light` / `dark` / `system`）
- 监听系统主题变化（`matchMedia`），在 `system` 模式下自动响应
- 所有组件使用 Tailwind 的 `dark:` 前缀定义深色样式

### 7.5 设置页面

- 路由 `/settings`，顶部菜单右侧"设置"按钮进入
- 表单字段：`video_path_list`（动态增删的目录路径数组）、`page_size`、`column_size`
- 提交 → `PUT /api/config` → 后端写回 `$DATA_PATH/config.yaml`
- 路径校验：目录必须存在且可读；重复路径去重

### 7.6 前后端联调（开发模式）

- `vite.config.ts` 配置 dev server 代理：`/api` → `http://localhost:8000`
- `start-dev.sh` 同时启动 `vite` 与 `uvicorn`，前端从 Vite dev server 取页面、API 走代理

## 8. 后端模块划分 (backend/)

```
backend/
├── main.py              # FastAPI app 入口、生命周期、静态资源挂载
├── config.py            # 配置读写 (config.yaml)、.env 加载
├── security.py          # IP 白名单中间件
├── routes/
│   ├── config.py        # /api/config
│   ├── dirs.py          # /api/roots, /api/roots/{id}/l2
│   ├── videos.py        # /api/l2/{id}/videos, /api/thumb/{id}
│   └── scan.py          # /api/scan-status
├── services/
│   ├── scanner.py       # 目录扫描、描述文件 新建/更新/删除
│   ├── thumbgen.py      # 缩略图生成(封面提取/抽帧/16:9适配)
│   ├── probe.py         # ffprobe 封装(元数据读取)
│   └── descfile.py      # 描述文件二进制 读写/解析
├── models.py            # Pydantic 模型 (Video, Dir, Config)
├── path_id.py           # video_id/dir_id 稳定哈希映射
└── logging_setup.py     # 日志配置
```

### 8.1 职责边界

- `probe.py` 只管调 ffprobe 拿元数据，不知道缓存
- `descfile.py` 只管描述文件二进制编解码，不知道扫描
- `scanner.py` 协调 probe + descfile + thumbgen，管增量更新
- `routes/` 只做 HTTP 层，业务逻辑全在 services

## 9. 启动与脚本 (bin/)

| 脚本 | 功能 |
|------|------|
| `start-dev.sh` | nohup 启动前端 vite dev + 后端 uvicorn dev，写 `app.pid`(含前后端) |
| `start.sh` | nohup 启动后端(生产，uvicorn)，写 `app.pid` |
| `stop.sh` | 读 `app.pid` 停止相关进程 |
| `restart.sh` | stop + start.sh |
| `build.sh` | 构建前端 → 复制到 backend 静态资源目录 |

约定：
- pid 文件统一放 **`$DATA_PATH/app.pid`**，每行一个 PID，行首标注角色(`frontend:`/`backend:`)
- 日志统一写 `$DATA_PATH/logs/`，脚本启动前 source `.env`

## 10. Docker (docker/)

- `Dockerfile`：基于 python slim，装 ffmpeg，装前端构建产物
- `docker-compose.yaml`：挂载视频目录 + DATA_PATH，映射端口
- 构建分两阶段：node 阶段构建前端，python 阶段跑后端

## 11. 错误处理

- ffprobe 失败 → 标记该视频元数据不可用，卡片显示"读取失败"，不阻塞其他视频
- 缩略图生成失败 → 沿用占位图，日志记录
- 路径越权访问（video_id 不属于 video_path_list）→ 403
- config.yaml 损坏 → 载入默认配置 + 日志告警

## 12. 测试策略

- `descfile.py`：二进制读写往返测试、边界(空缩略图/超大 JSON)
- `scanner.py`：增量更新(mtime 变化触发更新)、删除孤立描述文件
- `thumbgen.py`：16:9 适配各种输入比例、封面优先、抽帧位置
- `security.py`：白名单放行/拒绝、localhost 始终放行、空名单拒绝所有
- 路由层：用 FastAPI TestClient 端到端验证 API

## 13. 前置条件 / 待办

- **uv**：Python 包管理器和虚拟环境工具（替代 pip + venv），需安装 uv
- **Bun**：JavaScript 运行时（替代 Node.js + npm），用于前端构建/dev，需安装 Bun
- ffmpeg/ffprobe：后端依赖，需在运行环境可用
- .gitignore：应加入 `.superpowers/`（若使用视觉伴侣）

## 14. 范围之外 (YAGNI)

- 视频播放/预览（明确不做）
- 用户认证/多用户（IP 白名单已够）
- 视频搜索/全文检索
- 缩略图手动重新生成 UI
- 目录变更的实时监听（inotify）—— 用打开即扫描的增量策略替代
