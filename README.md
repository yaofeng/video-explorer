# video-explorer

一个视频库浏览器：FastAPI 后端扫描视频目录、按目录缓存元数据（`index.yaml`）与原始帧 JPEG 缩略图；Vue 3 + Tailwind 前端按 `根 → L1（顶级菜单）→ L2（左侧菜单）→ 叶子分组卡片` 三层层级浏览，采用三阶段渐进加载（L1 文件名 → L2 ffprobe 元数据 → L3 缩略图）。本项目仅做浏览，不含播放/预览。

## 目录结构

```
backend/    FastAPI 后端
  app/
    main.py              入口；路由装配；静态文件 SPA 兜底
    config.py            配置（config.yaml）读写，原子落盘
    security.py          IP 白名单中间件
    paths.py             id→路径 解析（带 TTL 缓存）
    safe_regex.py        用户正则带超时安全匹配
    models.py            Pydantic 模型（扁平 VideoItem）
    services/
      scanner.py         三阶段扫描编排（L1/L2/L3）+ 任务进度
      probe.py           ffprobe 封装
      thumbgen.py        原始帧 JPEG 抽取 + 小图压缩
      cache_index.py     index.yaml 读写（原子写、批量 upsert）
    routes/              config / dirs / videos / scan / parse_rules
frontend/   Vue 3 + Vite + Tailwind 前端
docker/     Dockerfile + docker-compose（CIFS 挂载 NAS）
bin/        运维脚本（build / start / start-dev / stop / restart）
```

## 配置

后端通过环境变量配置（可写入 `backend/.env`）：

| 变量 | 说明 | 默认 |
|---|---|---|
| `DATA_PATH` | 数据目录（config.yaml / cache / logs） | 当前工作目录 |
| `IP_WHITE_LIST` | 允许访问 API 的客户端 IP（空格/逗号分隔；localhost 始终放行） | 空（仅本地） |

视频库根目录列表、每页大小、列数、文件名解析规则在前端「设置」中编辑，持久化到 `DATA_PATH/config.yaml`。

## 本地开发

```bash
# 后端
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8002

# 前端（另一个终端）
cd frontend
bun install
bun run dev
```

或直接用脚本（自动切到仓库根）：

```bash
bin/start-dev.sh   # 同时拉起前后端（开发模式）
bin/stop.sh
```

## 测试

```bash
cd backend
pytest -q           # 需要系统已安装 ffmpeg/ffprobe
```

```bash
cd frontend
bun run typecheck   # vue-tsc 类型检查
bun run build       # 类型检查 + 生产构建
```

## Docker 部署

镜像为多阶段构建（bun 构建前端 → python 运行后端）。NAS 通过 CIFS 只读挂载到 `/videos`：

```bash
cd docker
cp .env.example .env        # 填入 SMB 凭据与 IP 白名单
docker compose up -d
```

服务监听容器内 8000，映射到宿主 8002。健康检查走 `/api/health`（已豁免 IP 白名单）。

## 安全说明

- 仅白名单内 / 本地 IP 可访问 API（`/api/health` 除外）。
- SPA 静态文件兜底做了路径包含校验，防止 `..` 路径遍历。
- 用户提交的文件名解析正则在带超时的沙箱线程中执行，避免 ReDoS。
- 缓存与配置写入均为原子操作（临时文件 + `os.replace`），防中途崩溃损坏。
