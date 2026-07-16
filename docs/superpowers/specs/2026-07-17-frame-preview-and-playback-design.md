# 视频帧预览 + 播放功能 设计文档

日期: 2026-07-17

## 1. 功能概述

在现有视频浏览器的 Lightbox 浮层中新增两项功能：

1. **视频帧预览**：点击视频卡片时，除显示封面外，后端对整个视频等间隔抽取 20 帧。用户可通过右键在大图上循环切换帧预览，大图下方以小图条形式展示全部 20 帧缩略图。
2. **视频播放按钮**：小图条下方新增两个纯图标按钮——浏览器新标签页播放、调用本地 IINA 播放器播放。

## 2. 方案选型

**帧提取方案**：批量抽取 + 独立缓存文件（方案 B）。

- 每视频 20 帧存为独立 JPEG 文件，缓存在 NAS
- 首次打开浮层时异步触发抽帧，已抽取过的视频秒开
- 与现有 `thumbgen.py` 的懒生成 + 缓存模式一致

选择理由：
- 零重复抽帧开销（NAS 不反复读同一文件）
- 浏览器可独立缓存每帧
- 前端实现简单（无需雪碧图 CSS）
- 磁盘代价可控（每视频 ~600KB）

## 3. 后端设计

### 3.1 新增文件

`backend/app/services/framegen.py` — 帧抽取服务

### 3.2 抽帧策略

- 20 帧**等间隔**分布在视频时间轴上
- 第 i 帧时间点：`t_i = duration × (i + 0.5) / 20`（避免首尾黑帧）
- 短于 20 秒的视频：按实际时长均匀分布
- 帧尺寸为**原始分辨率**（与封面缩略图一致），前端 CSS 适配显示

### 3.3 ffmpeg 命令

```python
# 单帧抽取（复用现有 thumbgen 的 probe 结果）
ffmpeg -v error -ss {t:.2f} -i {path} -frames:v 1 -f image2pipe -vcodec mjpeg -
```

### 3.4 帧存储结构

扩展现有 cache 目录，在视频同名目录下新增 `.frames/` 子目录：

```
cache/<root-hash>/movies/sci-fi/
├── index.yaml
├── dune.jpg              # 现有封面缩略图
├── dune.small.jpg        # 现有小缩略图
├── dune.frames/          # 新增：帧目录
│   ├── status.json       # {"total": 20, "ready_count": 12, "generating": true}
│   ├── frame_00.jpg
│   ├── frame_01.jpg
│   └── ...frame_19.jpg
```

### 3.5 `status.json` 格式

```json
{
  "total": 20,
  "ready_count": 12,
  "generating": true,
  "width": 3840,
  "height": 2160
}
```

> API 响应（3.8）与 `status.json` 字段名一致（`ready_count`），读取时直接透传，无需转换。

### 3.6 并发控制

- 使用 `ThreadPoolExecutor(max_workers=2)` 后台线程池
- 避免同时抽多个视频打满 NAS I/O
- 同一视频的重复请求：生成中 → 返回 202；已完成 → 返回 200

### 3.7 新增 API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/frames/{video_id}` | 返回 20 帧就绪状态和每帧 URL |
| POST | `/api/frames/{video_id}/generate` | 触发批量抽帧（异步），立即返回 202 |
| GET | `/api/frames/{video_id}/{frame_index}` | 返回单帧 JPEG（0~19），带缓存头 |
| GET | `/api/video/{video_id}` | 视频文件流式代理（支持 Range） |

### 3.8 帧状态查询响应格式

`GET /api/frames/{video_id}`：

```json
{
  "status": "generating",
  "total": 20,
  "ready_count": 12,
  "frame_urls": [
    "/api/frames/abc123/0",
    "/api/frames/abc123/1",
    null,
    ...
  ]
}
```

- `status` 取值：`"not_started"` | `"generating"` | `"ready"`
- `frame_urls` 中 `null` 表示该帧尚未就绪

### 3.9 帧文件响应

`GET /api/frames/{video_id}/{frame_index}`：

- 就绪：返回 JPEG bytes + `Cache-Control: public, max-age=86400`
- 未就绪：返回 202

### 3.10 视频流式代理

`GET /api/video/{video_id}`：

- 使用 `StreamingResponse` 支持 HTTP Range 请求
- 流式传输 chunk 大小：`64KB`（平衡内存占用与 I/O 效率）
- 安全校验：复用 `_id_to_path` 映射 + `find_root` 校验路径在 `video_path_list` 内，越界返回 403
- IP 白名单中间件自动生效

**响应头：**

```
Content-Type: video/mp4 | video/x-matroska | ...（按后缀推断）
Accept-Ranges: bytes
Content-Length: {file_size}
Cache-Control: private, max-age=3600
```

**Range 请求**：`Range: bytes=start-end` → 206 Partial Content

**MIME 类型映射：**

```python
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
```

## 4. 前端设计

### 4.1 Lightbox 浮层布局

```
┌──────────────────────────────────┐
│ ✕ 关闭按钮                       │
│ 视频标题 + 元信息（HEVC/4K/时长） │
├──────────────────────────────────┤
│ ┌──────────────────────────────┐ │
│ │                              │ │
│ │     大图（当前帧）             │ │
│ │                   右键切换→   │ │
│ │   7/20                       │ │
│ └──────────────────────────────┘ │
├──────────────────────────────────┤
│ [1][2][3][4][5][6][▓7▓][8]...   │ ← 小图条（横向滚动）
├──────────────────────────────────┤
│        ▶浏览器    ▶IINA          │ ← 纯图标按钮
└──────────────────────────────────┘
```

### 4.2 组件变更

**`LightboxModal.vue`**（大幅改造）：

- 顶部：视频标题 + 元信息标签（复用 VideoCard 的格式化函数）
- 大图区：`<img>` 显示当前帧，`@contextmenu.prevent` 拦截右键切换
- 帧计数器：左上角 `7 / 20`
- 右键提示：右下角半透明提示文字
- 小图条：20 个 `<img>` 横向排列，`overflow-x: auto`
- 播放按钮区：两个纯图标按钮（SVG），悬浮 tooltip 提示

**新增 `useFramePreview.ts`** composable：

```typescript
function useFramePreview(videoId: Ref<string>) {
  const frames = ref<(string | null)[]>(Array(20).fill(null))
  const currentFrame = ref(0)
  const status = ref<'not_started' | 'generating' | 'ready'>('not_started')

  function nextFrame()        // 右键：循环切换 (currentFrame + 1) % 20
  function selectFrame(i: number)  // 左键小图：跳转到第 i 帧
  function startGeneration() // POST /api/frames/{id}/generate + 轮询

  return { frames, currentFrame, status, nextFrame, selectFrame, startGeneration }
}
```

### 4.3 交互行为

| 操作 | 行为 |
|------|------|
| 点击视频卡片 | 打开 Lightbox，显示封面，自动触发帧抽取 |
| 右键大图 | 大图切换到下一帧（循环 1→2→...→20→1），小图条高亮跟随 |
| 左键点小图 | 大图跳转到该帧，高亮框移动 |
| 未就绪帧小图 | 灰色 loading 占位，就绪后替换为 JPEG |
| 点击 ▶浏览器 | `window.open('/api/video/{id}')` 新标签页 |
| 点击 ▶IINA | `window.location.href = 'iina://open?url=' + encodeURIComponent(video_url)` |

### 4.4 小图条行为

- 帧就绪后懒加载显示 JPEG（`<img loading="lazy">`）
- 当前帧高亮：紫色边框（`border-indigo-500`）+ 阴影（`shadow-lg shadow-indigo-500/40`）
- 溢出时横向滚动，当前帧自动 `scrollIntoView({ behavior: 'smooth', inline: 'center' })`
- 小图尺寸：宽 80px，16:9 比例

### 4.5 播放按钮

- 纯 SVG 图标按钮（播放三角形），无文字
- 浏览器播放图标：普通播放三角
- IINA 播放图标：播放三角 + IINA logo 或不同颜色区分
- 按钮样式：圆角矩形背景，hover 时缩放 + 亮度提升
- tooltip：`title="浏览器播放"` / `title="IINA 播放"`

## 5. 数据流

```
用户点击卡片
    │
    ├─→ 打开 Lightbox
    │    ├─→ 大图初始显示封面缩略图（/api/thumb/{id}）
    │    ├─→ 小图条 20 格全部显示 loading 占位
    │    └─→ POST /api/frames/{id}/generate → 202 Accepted
    │
    └─→ 后端线程池开始抽帧（20 帧等间隔）
         │
         └─→ 前端轮询 GET /api/frames/{id}（每 2s）
              │
              ├─→ 帧就绪 → 小图条对应位置替换为 JPEG
              │
              ├─→ 第 0 帧就绪 → 大图自动从封面切换为 frame_0
              │
              └─→ status = "ready" → 停止轮询，全部 20 帧就绪

用户右键大图
    │
    └─→ currentFrame = (currentFrame + 1) % 20
         ├─→ 大图 <img> src 更新
         └─→ 小图条高亮框移动 + scrollIntoView

用户点击播放按钮
    │
    ├─→ 浏览器：window.open('/api/video/{id}')
    │
    └─→ IINA：window.location = 'iina://open?url=...'
```

## 6. 错误处理

- 帧抽取失败：`status.json` 中 `generating = false` + `ready_count < total`，前端显示「部分帧抽取失败」提示
- 视频文件不存在或不可读：`/api/video/{id}` 返回 404
- 视频路径越权：`/api/video/{id}` 返回 403
- IINA 未安装：`iina://` 协议无法唤起，浏览器忽略（无反馈），可考虑 fallback 提示
- 浏览器不支持视频格式：浏览器原生播放器显示错误，用户可改用 IINA

## 7. 文件变更清单

**新增文件：**
- `backend/app/services/framegen.py` — 帧抽取服务
- `backend/app/routes/frames.py` — 帧相关路由
- `backend/app/routes/video.py` — 视频流代理路由
- `frontend/src/composables/useFramePreview.ts` — 帧预览状态管理

**修改文件：**
- `backend/app/main.py` — 注册新路由
- `backend/app/routes/__init__.py` — 导出新路由（如需要）
- `frontend/src/components/LightboxModal.vue` — 大幅改造

## 8. 范围之外

- 帧抽取的手动重新触发 UI（删除 `.frames/` 目录即可重建）
- 视频在线播放器的自定义 UI（使用浏览器原生播放器）
- 帧预览的快捷键支持（后续可扩展）
- 帧抽取进度百分比显示（仅显示就绪/未就绪）
