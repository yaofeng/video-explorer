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

**保存时格式**：
```yaml
video_path_list:    # 视频目录绝对路径列表
  - /path/to/videos
page_size: 0        # 每页视频数，0=不分页全部展示
column_size: 4      # 每行视频卡片数量
parse_rules:        # 文件名解析规则（可选）
  - name: "JAV"
    pattern: "^(?P<code>[A-Za-z]+-[0-9]+)-?(?P<actress>[A-Z][a-z]+(?: [A-Z][a-z]+)*)?"
```

`parse_rules` 使用正则命名捕获组提取视频扩展信息。**匹配前先剥离原始扩展名**（如 `ABC-123.mp4` 用 `ABC-123` 匹配）。匹配成功的字段存入 `index.yaml` 的 `ext` 字段；**无规则匹配时，删除该视频原有的 `ext` 字段**（保持 `index.yaml` 一致性）。

`parse_rules` 变更通过 `PUT /api/config` 保存时，后端自动调用 `scanner.invalidate_all_caches()` 清除内存缓存，下次打开目录时重新应用新规则解析文件名。

提供 API 读写配置；前端有设置浮窗编辑这些值。

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
- **直接位于二级目录下的视频归入"未分组"组，该组不显示组标题**（仅展示卡片）

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
│   │   │   ├── dune.jpg              # 缩略图（原始分辨率 JPEG）
│   │   │   └── ...
│   │   └── action/
│   │       ├── index.yaml
│   │       └── ...
│   └── tv/
│       └── ...
```

### 5.2 index.yaml 格式

每个目录下的 `index.yaml` 保存该目录直接包含（不含递归子目录）的所有视频基础信息，**扁平结构**（无 meta 嵌套层级）：

```yaml
videos:
  - file_name: "dune.mkv"           # 文件名
    group: "未分组"                  # 分组名
    level: 3                         # 处理层级：1=文件名 2=+元数据 3=+缩略图
    create_time: 1720900000          # 创建时间，epoch 秒（整数）
    modify_time: 1720900000.9        # 修改时间，epoch 秒（浮点）
    file_size: 8192                  # 文件大小，单位 MB（整数）
    codec: "HEVC"                    # 编码（level>=2 才有）
    width: 3840                      # 宽（level>=2 才有）
    height: 2160                     # 高（level>=2 才有）
    duration: 9123                   # 时长，单位秒（整数，level>=2 才有）
    resolution_label: "4K"           # 分辨率标签（level>=2 才有）
    thumb_file: "dune.jpg"           # 缩略图文件名（level=3 才有）
    ext:                             # 文件名解析扩展信息（可选）
      code: "ABC-123"
      actress: "Yua Mikami"
  - file_name: "blade-runner.mkv"
    group: "科幻"
    level: 3
    create_time: 1720900100
    modify_time: 1720900100.5
    file_size: 6553
    codec: "H264"
    width: 1920
    height: 1080
    duration: 7421
    resolution_label: "FHD"
    thumb_file: "blade-runner.jpg"
```

**字段说明**：
- `file_size`：单位 **MB（兆）**，整数（`int(字节数 / 1048576)`）
- `duration`：单位 **秒**，整数（`int(秒数)`）
- `create_time`：源文件创建时间（`st_ctime`）
- `modify_time`：源文件修改时间（`st_mtime`），用于缓存有效性判断
- 无 `meta` 嵌套层级，元数据字段直接平铺
- 无 `file_size_gb`、无 `resolution_str` 字段

扫描时先快速填充 `index.yaml`（level=1，仅文件系统探知大小/时间），再异步提取元数据（level=2）和缩略图（level=3），逐步更新。

### 5.3 缩略图存储

- 每个视频对应一个同名 `.jpg` 缩略图文件（视频文件名去掉原始扩展名 + `.jpg`）
- 缩略图为从视频中提取的**原始帧**，不做尺寸/比例处理（处理在前端显示时完成）
- 提取来源：优先使用视频内嵌封面；无封面则抽 `00:03:30` 附近的帧（短于 3:30 取中点）；失败则跳过

### 5.4 扫描与更新策略

打开一个二级目录时触发扫描，扫描分为**两个阶段**：

**Phase 1 — 快速文件系统扫描（无进度指示）**

1. **预加载**：若 `index.yaml` 已存在，立即从缓存加载视频条目到内存，前端可立即渲染（秒开）。
2. **遍历目录**：收集该二级目录下所有视频文件。
3. **处理删除**：内存中存在但磁盘已不存在的文件 → 从 `index.yaml` 移除，删除对应缩略图。
4. **处理新增/更新**：对每个视频文件：
   - 若缓存有效（`modify_time` 未变）：仅更新 `ext` 字段（应用最新 `parse_rules`）。
   - 否则：创建 L1 条目（文件系统信息 + `ext`）。
5. **完成后**：向后端状态写入 `refresh_full=True` 信号，前端据此全量刷新（处理删除/新增/分组变化）。

**Phase 2 — 深度扫描（ffprobe + 缩略图）**

1. 对每个需要更新的文件（level<3 或 `modify_time` 变化）：
   - 调用 `ffprobe` 提取元数据 → 升级到 L2 → 原子更新 `index.yaml`
   - 提取缩略图 → 升级到 L3 → 原子更新 `index.yaml`
2. **每完成一个文件**就原子更新 `index.yaml`（使用 per-index_path 文件锁防并发冲突），并通过增量协议推送给前端。
3. **扫描错误**不改变显示内容，聚合后通过 `errors` 字段返回，前端在右上角 TaskToast 中显示。

**并发控制**：`index.yaml` 的读-改-写操作使用 per-path 文件锁（`_get_index_lock`）保证原子性，避免多线程同时写入导致数据丢失。

**缓存失效**：
- `parse_rules` 通过 `PUT /api/config` 修改时，后端调用 `scanner.invalidate_all_caches()` 清除内存中的 `fully_scanned` 标记。
- 下次打开目录时，scanner 会重新执行 Phase 1（应用新的 `parse_rules` 重新解析文件名）。
- `parse_rules` 的哈希值（`parse_rules_hash`）记录在 `_L2State` 中，作为缓存短路判定条件之一。

## 6. 渐进式展示机制 (轮询)

### 6.1 流程

1. 前端打开二级目录 → `GET /api/l2/{l2_id}/videos`
   - 若 `index.yaml` 已存在，后端**立即从缓存返回**当前视频列表（可能包含 L1/L2/L3 混合数据），前端可立即渲染——**秒开**
   - 若 `index.yaml` 不存在，返回空列表，前端显示加载中占位符
   - 同时启动后台两阶段扫描
2. **Phase 1（快速扫描）**完成后，后端置 `refresh_full=True`，前端下一次轮询检测到此信号后全量刷新（处理删除/新增/分组变化）
3. **Phase 2（深度扫描）**期间，每完成一个文件的 ffprobe/缩略图就原子更新 `index.yaml`，并通过 `scan-status` 的 `updates` 增量推送给前端，前端合并到页面
4. 前端轮询接口：`GET /api/scan-status?l2_id=&since=`，响应包含：
   - `phase`: 当前阶段（"idle" / "quick" / "deep" / "done"）
   - `refresh_full`: 一次性信号（Phase 1 完成时置 true）
   - `errors`: 聚合错误列表（供 TaskToast 显示）
   - `updates`: 增量更新条目（seq > since 的）
5. 扫描错误（如 ffprobe 失败）不改变显示内容，聚合后在右上角 TaskToast 中展示

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
| GET | `/api/thumb/{video_id}` | 原始 JPEG 缩略图（浮层用，200 / 202 未就绪）|
| GET | `/api/thumb/{video_id}?size=small` | 压缩小图 JPEG（卡片用，480px 宽，懒生成并缓存）|
| GET | `/api/scan-status?l2_id=&since=` | 处理进度 + 新就绪项列表 + `phase` + `refresh_full` + `errors` |
| POST | `/api/roots/{root_id}/build` | 为整个视频库构建索引（扫描所有 L2 子目录），后台执行 |
| GET | `/api/tasks` | 当前运行中的索引任务进度（供前端浮窗显示）|

**导航数据流**：
`/api/roots` → 选视频库根目录 → `/api/roots/{root}/l1`（顶部菜单）→ `/api/l1/{l1}/l2`（左侧菜单）→ `/api/l2/{l2}/videos`（中心区）。

所有 id 均可反查到绝对路径并校验是否落在 video_path_list 内，越权返回 403。

缩略图响应带 `Cache-Control: public, max-age=86400` 头，浏览器缓存复用。`size=small` 首次请求时从原始 JPEG 生成 480px 宽小图并缓存为 `.small.jpg`，后续直接读缓存。

### 6.4 缓存与并发

- `index.yaml` + 缩略图 `.jpg` 文件为磁盘缓存，进程重启不丢失
- 后台处理任务用单 worker 队列 + 文件锁防重复
- 缩略图请求与生成解耦：未就绪返回 202

## 7. 前端设计 (Vue3 + Tailwind)

### 7.1 页面结构

```
┌──────────────────────────────────────────────────┐
│ [库A ▼]  [动作]  [科幻]  [喜剧]  [动画]   [设置]  │
├──────────┬───────────────────────────────────────┤
│ 二级菜单  │  中心区                                │
│ [子1]    │  ── 组: 4K电影/科幻 ──      [⚠️ 错误] │
│ [子2]    │  [卡片][卡片][卡片][卡片]    [🔨 构建] │
│ [子3]    │  ── 组: 4K电影/动作 ──                │
│          │  [卡片][卡片][卡片][卡片]               │
└──────────┴───────────────────────────────────────┘
```

- 顶栏最左侧：视频库根目录下拉切换框
- 下拉框右侧：一级目录按钮组
- 最右侧：设置按钮
- 左侧二级菜单：**纯目录列表**（不含进度条，进度/错误统一由右上角 Toast 显示）
- 右上角浮窗：扫描错误（聚合计数）+ 构建索引任务进度条

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
- 缩略图由后端提取**原始帧**（源文件分辨率、不缩放不裁剪），以 `.jpg`（JPEG）格式存储
- 卡片显示请求 `?size=small`，后端懒生成 480px 宽小 JPEG（约 20-30KB）并缓存
- 浮层显示请求原始 JPEG（完整分辨率）
- 前端 `<img>` 使用 CSS `object-fit: contain` 配合 16:9 容器做显示适配——不拉伸、不裁剪
- 缩略图响应带 `Cache-Control` 头，浏览器缓存复用，切换目录不重复下载
- 缩略图未就绪时用 `<p class="text-gray-500">加载中...</p>` 占位，尺寸与卡片缩略图区域一致
- 文件名两行，超出省略号
- 编码/分辨率/时长/大小为半透明胶囊标签，叠在缩略图四角
- 卡片网格列数 = `column_size`（Tailwind 动态 grid-cols）
- 分页：当 `page_size > 0` 时启用，**分页作用于每个组内**（各组独立分页）；`page_size = 0` 时全部展示不分页

### 7.3 状态管理

- 轻量：Pinia store 管理目录树、当前选中、视频列表、扫描阶段、错误信息
- 轮询逻辑封装在 composable `useScanPolling`
- 缩略图加载用 `<p>加载中...</p>` 占位，数据就绪后替换为 `<img>`，配合扫描状态主动刷新就绪项
- `browser` store 维护 `phase`（扫描阶段）、`errors`（聚合错误）、`refresh_full` 信号
- 当 `refresh_full=true` 时，前端全量重新请求 `/api/l2/{id}/videos` 处理删除/新增
- 扫描期间页面内容通过增量 `updates` 逐步升级（L1→L2→L3），无需进度条

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

### 7.5 设置浮窗

- 设置以**浮窗（Modal）**形式展示，不再是独立路由页面
- 顶部菜单右侧齿轮图标按钮触发浮窗打开；点击遮罩或"取消"/"×"关闭
- 表单字段：`video_path_list`（动态增删的目录路径数组）、`page_size`、`column_size`
- **文件名解析规则**：`parse_rules` 列表，每项包含规则名（`name`）和正则模式（`pattern`），使用命名捕获组（如 `(?P<code>...)`、`(?P<actress>...)`）提取扩展信息
- 保存 → `PUT /api/config` → 后端写回 `$DATA_PATH/config.yaml` → 关闭浮窗
- 每个视频目录后有"构建索引"图标按钮（锤子图标），点击后台扫描该视频库所有 L2 子目录

### 7.6 顶部菜单工具栏

顶部菜单右侧提供以下工具按钮（从左到右排列）：

| 工具 | 说明 |
|------|------|
| 🔍 搜索框 | 输入关键字按文件名过滤，× 按钮清除 |
| 排序按钮组 | 三图标：文件名 A-Z / 文件大小 ↓ / 修改时间 ↓；同字段再点切换方向 |
| 🔽 编码过滤 | 漏斗图标下拉多选（H264/HEVC/AV1/其他），默认全选=不过滤 |
| 💻☀️🌙 主题切换 | 跟随系统/浅色/深色 |
| ⚙️ 设置 | 齿轮图标，打开设置浮窗 |

所有筛选排序状态持久化到 `localStorage`，刷新页面不丢失。

### 7.7 右上角 Toast 通知

页面右上角浮窗（`TaskToast.vue`）统一展示两类信息：

**A. 扫描错误（聚合计数）**

- 数据来源：`GET /api/scan-status` 的 `errors` 字段
- 由 `browser` store 维护，`TaskToast` 直接读取
- 显示样式：⚠️ 图标 + "N 个文件处理失败" + 前 5 条错误详情（可滚动查看）
- 用户可点击 × 手动关闭错误列表
- 每次扫描开始时（`selectL2`）错误列表自动清空

**B. 构建索引任务进度**

- 数据来源：`GET /api/tasks`（仅返回 build 任务，scan 任务不再注册进度）
- 由 `useTaskStore` 轮询（1s 间隔）
- 显示样式：🔨 图标 + 进度条 + "完成/总数"
- 任务完成后保持 2 秒"满格绿"再隐藏

**注意**：单目录扫描（scan 任务）**不再显示进度条**，仅通过页面内容增量更新反馈进度。错误通过上述 A 类展示。

### 7.8 视频卡片（文件名解析版）

文件名解析**先剥离原始扩展名**再匹配规则（如 `ABC-123.mp4` 用 `ABC-123` 匹配）。当匹配成功时，卡片不显示原始文件名，改为：

```
┌─────────────────────────┐
│ [HEVC]        [FHD]     │
│                         │
│   缩略图 / 加载占位符    │
│                         │
│ [02:30:00]   [8.0G]     │
├─────────────────────────┤
│ 影片标题（单行,省略）   │
│ [code: ABC-123] 📋      │  ← 可点击标签（复制到剪贴板）
│ [actress: Yua Mikami] 📋│
└─────────────────────────┘
```

- 未匹配规则的视频仍然显示原始文件名
- ext 字段（code/actress/title 等）来自 `parse_rules` 正则命名的捕获组
- 标签点击复制到剪贴板

### 7.9 前后端联调（开发模式）

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
- 构建分两阶段：Bun 阶段构建前端，Python 阶段跑后端

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
