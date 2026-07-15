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

`video_path_list` 中的每个配置项是一个**视频库根目录**，其下的子目录才是顶部菜单的一级目录：

```
video_path_list:
  - /mnt/media/movies       # 视频库根目录 A
  - /mnt/media/tv           # 视频库根目录 B
```

- **视频库根目录**：通过顶部菜单左侧的下拉框切换不同的视频库根目录
- **一级目录**：视频库根目录下的直接子目录，对应顶部一级菜单
- **二级目录**：一级目录下的直接子目录，对应左侧二级菜单
- **二级目录下更深层的视频** → 中心区，**按叶子目录分组**

**叶子目录定义**：从二级目录出发，沿含视频文件的路径深入，第一个"含视频文件或其子目录含视频文件"的终点目录。

### 4.2 导航结构图示

```
┌──────────────────────────────────────────────────┐
│ [库A ▼]  [动作]  [科幻]  [喜剧]  [动画]   [设置]  │
│  ╰── 左侧下拉   ╰── 顶部一级菜单（视频库根目录的子目录）
├──────────┬───────────────────────────────────────┤
│ 二级菜单  │  中心区                                │
│ [子1] ██ │  ── 组: 4K电影/科幻 ──                 │
│ [子2] ██ │  [卡片][卡片][卡片][卡片]               │
│ [子3] ██ │  ── 组: 4K电影/动作 ──                 │
│  进度条   │  [卡片][卡片][卡片][卡片]               │
└──────────┴───────────────────────────────────────┘
```

- 顶部菜单最左侧是视频库根目录切换下拉框
- 下拉框右侧是一级目录按钮
- 一级目录右侧是设置按钮
- 左侧二级菜单项在扫描进行时底部显示进度条

- 中心区每个组对应一个叶子目录
- 组标题 = 叶子目录相对于二级目录的路径（如 `4K电影/科幻`）
- **直接位于二级目录下的视频归入"未分组"组**，组标题为二级目录名或"未分组"

## 5. 视频缓存 (cache)

### 5.1 存储结构

cache 目录第一级为 `video_path_list` 中配置项的标识（目录名 + 全路径 md5 后 4 位），后续层级镜像原视频目录结构：

```
$DATA_PATH/cache/
├── <video库根目录名>-<路径md5后4位>/    # 例：movies-a1b2
│   ├── index.yaml                     # 该根目录下所有视频的基础信息索引
│   ├── movies/                        # 一级目录（镜像原结构）
│   │   ├── index.yaml                 # 该目录下所有视频的基础信息
│   │   ├── sci-fi/
│   │   │   ├── index.yaml             # 叶子目录基础信息
│   │   │   ├── dune.mkv.png           # 缩略图
│   │   │   └── ...
│   │   └── action/
│   │       ├── index.yaml
│   │       └── ...
│   └── tv/
│       └── ...
```

### 5.2 index.yaml 格式

每个目录下的 `index.yaml` 保存该目录直接包含（不含递归子目录）的所有视频基础信息：

```yaml
videos:
  - file_name: "dune.mkv"           # 文件名
    file_size_gb: 8.0                # 文件大小，单位 GB
    resolution: "3840x2160"          # 原始分辨率
    codec: "HEVC"                    # H264 / HEVC / ...
    create_time: 1720900000          # 创建时间，epoch 秒
    modify_time: 1720900000.0        # 修改时间，epoch 秒
    thumb_file: "dune.mkv.png"       # 缩略图文件名
  - file_name: "blade-runner.mkv"
    file_size_gb: 6.4
    resolution: "1920x1080"
    codec: "H264"
    create_time: 1720900100
    modify_time: 1720900100.0
    thumb_file: "blade-runner.mkv.png"
```

扫描时先快速填充 `index.yaml`（仅文件系统探知大小/时间），再异步逐个提取缩略图并更新 `index.yaml` 中的 `thumb_file` 字段。

### 5.3 缩略图存储

- 每个视频对应一个同名的 `.png` 缩略图文件
- 缩略图为从视频中提取的**原始帧**，不做尺寸/比例处理（处理在前端显示时完成）
- 提取来源：优先使用视频内嵌封面；无封面则抽 `00:03:30` 附近的帧（短于 3:30 取中点）；失败则跳过

### 5.4 扫描与更新策略

打开一个二级目录时触发扫描：

1. **遍历该二级目录下所有叶子目录**，收集视频文件
2. 对每个视频，检查 cache：
   - `index.yaml` 不存在 → **新建**，填充基础信息
   - 视频文件的 `modify_time` 晚于 `index.yaml` 记录值 → **更新**
   - 视频文件已不存在于目录中 → 从 `index.yaml` 移除，删除对应缩略图
3. 缩略图异步生成，逐文件完成后更新 `index.yaml` 并通知前端

## 6. 渐进式展示机制 (轮询)

### 6.1 流程

1. 前端打开二级目录 → `GET /api/l2/{l2_id}/videos`
   - 后端立即返回：由**目录扫描**得到的视频文件名列表（来自文件系统遍历），按叶子目录分组——**无需 ffprobe，秒级完成**
   - 同时启动后台任务：逐个提取缩略图，补全 `index.yaml` 中缺失的信息
2. 前端根据文件名列表**立即渲染卡片布局和文件名**，缩略图区域用 `<p>加载中...</p>` 占位（不用 `<img>`）
3. 后台处理完一个视频的基础信息（ffprobe 元数据）→ 更新 `index.yaml` → 前端轮询获取更新
4. 后台生成完一个缩略图 → 前端下一次轮询时获取缩略图 URL → 将 `<p>` 替换为 `<img>`
5. 前端轮询接口：`GET /api/scan-status?l2_id=&since=`

### 6.2 数据分层

视频数据分为三层，逐层获取：

| 层级 | 内容 | 获取方式 | 时间 |
|------|------|----------|------|
| L1 | 文件名、文件大小、所在分组 | 文件系统遍历（目录扫描） | 即时 |
| L2 | 分辨率、编码、时长 | ffprobe 元数据 | 秒级/每文件 |
| L3 | 缩略图 | ffmpeg 抽帧/封面提取 | 较慢/每文件 |

### 6.3 接口设计

`dir_id` = 目录绝对路径的稳定哈希（md5 前 16 位），全局唯一。
`video_id` = 视频文件绝对路径的稳定哈希（md5 前 16 位）。

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/config` | 读取配置 |
| PUT | `/api/config` | 更新配置 |
| GET | `/api/roots` | 列出 video_path_list（视频库根目录）|
| GET | `/api/roots/{root_id}/l1` | 根目录下的一级目录（顶部菜单）|
| GET | `/api/l1/{l1_id}/l2` | 一级目录下的二级目录（左侧菜单）|
| GET | `/api/l2/{l2_id}/videos` | 二级目录下所有视频文件名（分组）+ 触发后台处理 |
| GET | `/api/thumb/{video_id}` | 缩略图 PNG（200 PNG / 202 未就绪）|
| GET | `/api/scan-status?l2_id=&since=` | 处理进度 + 新就绪项列表 |

**导航数据流**：
`/api/roots` → 选视频库根目录 → `/api/roots/{root}/l1`（顶部菜单）→ `/api/l1/{l1}/l2`（左侧菜单）→ `/api/l2/{l2}/videos`（中心区）。

所有 id 均可反查到绝对路径并校验是否落在 video_path_list 内，越权返回 403。

### 6.4 缓存与并发

- `index.yaml` + 缩略图 `.png` 文件为磁盘缓存，进程重启不丢失
- 后台处理任务用单 worker 队列 + 文件锁防重复
- 缩略图请求与生成解耦：未就绪返回 202

## 7. 前端设计 (Vue3 + Tailwind)

### 7.1 页面结构

```
┌──────────────────────────────────────────────────┐
│ [库A ▼]  [动作]  [科幻]  [喜剧]  [动画]   [设置]  │
├──────────┬───────────────────────────────────────┤
│ 二级菜单  │  中心区                                │
│ [子1] ██ │  ── 组: 4K电影/科幻 ──                 │
│ [子2] ██ │  [卡片][卡片][卡片][卡片]               │
│ [子3]    │  ── 组: 4K电影/动作 ──                 │
│          │  [卡片][卡片][卡片][卡片]               │
└──────────┴───────────────────────────────────────┘
```

- 顶栏最左侧：视频库根目录下拉切换框
- 下拉框右侧：一级目录按钮组
- 最右侧：设置按钮
- 左侧二级菜单：当前选中的项，在后台处理进行时显示进度条

### 7.2 视频卡片

```
┌─────────────────────────┐
│ [HEVC]        [FHD]     │  ← 编码左上 / 分辨率标签右上
│                         │
│   缩略图/加载占位符      │
│                         │
│ [02:30:00]   [8.0G]     │  ← 时长左下 / 大小右下
├─────────────────────────┤
│ 文件名称(两行展示,省略)  │
└─────────────────────────┘
```

**渐进式加载流程**：
1. **L1（即时）**：卡片布局、文件名、占位 `<p>加载中...</p>` 立即渲染
2. **L2（异步）**：ffprobe 元数据就绪后，分辨率标签、编码、时长更新到卡片角落
3. **L3（异步）**：缩略图就绪后，将 `<p>加载中...</p>` 替换为 `<img>` 显示图片

**缩略图显示规则**：
- 缩略图由后端提取**原始帧**（源文件分辨率、不做任何处理），以 `.png` 格式存储
- 前端 `<img>` 使用 CSS `object-fit: contain` 配合 16:9 容器做显示适配——不拉伸、不裁剪
- 缩略图未就绪时用 `<p class="text-gray-500">加载中...</p>` 占位，尺寸与卡片缩略图区域一致
- 文件名两行，超出省略号
- 编码/分辨率/时长/大小为半透明胶囊标签，叠在缩略图四角
- 卡片网格列数 = `column_size`（Tailwind 动态 grid-cols）
- 分页：当 `page_size > 0` 时启用，**分页作用于每个组内**（各组独立分页）；`page_size = 0` 时全部展示不分页

### 7.3 状态管理

- 轻量：Pinia store 管理目录树、当前选中、视频列表、处理进度、缩略图就绪状态
- 轮询逻辑封装在 composable `useScanPolling`
- 缩略图加载用 `<p>加载中...</p>` 占位，数据就绪后替换为 `<img>`，配合扫描状态主动刷新就绪项
- 左侧二级菜单项在处理进度进行时，底部显示进度条（已完成数/总数）

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
│   ├── dirs.py          # /api/roots, /api/roots/{id}/l1, /api/l1/{id}/l2
│   ├── videos.py        # /api/l2/{id}/videos, /api/thumb/{id}
│   └── scan.py          # /api/scan-status
├── services/
│   ├── scanner.py       # 目录扫描、index.yaml 新建/更新/删除
│   ├── thumbgen.py      # 缩略图提取（ffmpeg 原始帧）
│   ├── probe.py         # ffprobe 封装(元数据读取)
│   └── cache_index.py   # index.yaml 读写，缩略图文件管理
├── models.py            # Pydantic 模型 (Video, Dir, Config)
├── path_id.py           # video_id/dir_id 稳定哈希映射
└── logging_setup.py     # 日志配置
```

### 8.1 职责边界

- `probe.py` 只管调 ffprobe 拿元数据，不知道缓存
- `cache_index.py` 只管 index.yaml 的读写和缩略图文件管理，不知道扫描
- `scanner.py` 协调 probe + cache_index + thumbgen，管增量更新
- `routes/` 只做 HTTP 层，业务逻辑全在 services
- 缩略图不做服务器端尺寸/比例处理——前端 CSS 适配即可

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

- `cache_index.py`：index.yaml 读写往返测试、缩略图文件管理
- `scanner.py`：增量更新(modify_time 变化触发更新)、删除孤立文件
- `thumbgen.py`：封面优先、抽帧位置、异常处理
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
- 缩略图手动重新生成 UI（缓存重建通过删除 cache 目录实现）
- 目录变更的实时监听（inotify）—— 用打开即扫描的增量策略替代
- 高清图浮层（点击卡片展示原始尺寸缩略图在 Lightbox 中展示即可）
