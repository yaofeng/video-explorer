# 扫描路径代码问题分析报告

日期：2026-07-19

---

## 问题 1：左下和右上进度条不同步

### 根本原因

两个进度条读取的是**两套完全独立的数据源**，且语义定义不同：

| 维度 | 左下进度条 (SideMenu) | 右上进度条 (TaskToast) |
|------|----------------------|----------------------|
| 接口 | `/api/scan-status?l2_id=...` | `/api/tasks` |
| 后端方法 | `scanner.status()` | `scanner.get_tasks()` |
| `total` 单位 | 视频文件数 (`state.total`) | scan 任务=视频数；**build 任务=L2 目录数** |
| 分子定义 | `level==2` 的视频数 (**不含 L3**) | `level>=2` 的视频数 (**含 L3**) |
| 轮询周期 | 2 秒 | 1 秒 |
| 作用范围 | 仅当前选中 L2 目录 | 全局所有任务 |

### 关键代码位置

- **左下条分子分母**：`frontend/src/components/SideMenu.vue:25, 30` → 显示 `progress.level2 / progress.total`
- **左下条 progress 算法**：`backend/app/services/scanner.py:548-562` — 用 `elif` 链，`level==2` 和 `level==3` 分开计数
- **右上条 done 算法**：`backend/app/services/scanner.py:388-389` — `processed = sum(1 for v in ... if v.get("level", 1) >= 2)`
- **生命周期差异**：scan 完成后右上条有 2 秒"完成态绿色残留"（`frontend/src/stores/task.ts:31-32`），左下条立即消失

### 具体症状

1. **分子反向减少**：L3 阶段开始后，视频从 level 2 升到 level 3，左下条的 `level2` 计数反而下降（因为用 `elif`），而右上条的 `done` 只增不减。两条进度条视觉上"打架"。
2. **build 场景分母完全不同**：右上条显示"12/50 目录"，左下条显示"120/500 视频"，量纲不一致。
3. **更新频率不同**：2 秒 vs 1 秒，视觉上跳动节奏也不同步。

### 修复方向

统一分子定义（都用 `level>=2`）；build 任务在 UI 文案上明确标注"目录数"以区分。

---

## 问题 2：命名解析规则修改后不会重新解析文件名

### 根本原因

**两层短路机制**叠加，让 parse_rules 变化被完全忽略：

#### 短路 A：内存层 (`ensure_scan` 快速返回)

```python
# scanner.py:213-219
if not already_scanning and state.fully_scanned:
    cur_mtime = int(Path(l2_path).stat().st_mtime)
    short_circuit = cur_mtime <= state.last_source_mtime
```

**判定条件只看目录 mtime**，完全不考虑 parse_rules 是否变化。`_L2State` 没有任何 parse_rules 版本/hash 字段。

#### 短路 B：磁盘层（L0 缓存预填充）

```python
# scanner.py:300-319
if int(cached.get("modify_time", 0)) < source_mtime:
    continue  # 源文件更新才继续
if cached.get("level", 1) >= 3 and cached.get("thumb_file") and thumb_path.exists():
    item = {...}
    if "ext" in cached:
        item["ext"] = cached["ext"]   # ← 直接复用旧 ext
    fully_cached_vids.add(vid)        # ← 加入跳过名单
```

只要视频 `modify_time` 没变且 level>=3 且有缩略图，就：
- 从 `index.yaml` 直接加载旧 `ext` 字段
- 加入 `fully_cached_vids` 集合
- 在 L1 阶段被 `continue` 跳过（`scanner.py:328-329`）

**`_parse_filename` 只在 L1 阶段调用**（`scanner.py:345`），L0 命中的视频永远走不到这一步。

#### 后端没有通知机制

- `config.save_config()` 只写文件，无回调/事件
- `PUT /api/config` 路由直接返回，scanner 完全感知不到变更
- 前端 `SettingsModal.save()` 只做 PUT + 关闭弹窗，不触发任何重建动作

### 关键代码位置

- **内存短路**：`backend/app/services/scanner.py:213-219`
- **L0 缓存命中跳过**：`backend/app/services/scanner.py:300-319, 328-329`
- **_parse_filename 调用点**：`backend/app/services/scanner.py:345`（唯一调用）
- **config 保存无通知**：`backend/app/config.py:61-82`、`backend/app/routes/config.py:19-33`
- **前端保存逻辑**：`frontend/src/stores/config.ts:19-27`、`frontend/src/components/SettingsModal.vue:212-215`

### 具体症状

修改 `parse_rules` 后：
- 已完全扫描的目录（`fully_scanned=True`）直接被内存短路返回旧数据
- 即便绕过内存短路，L0 缓存也会把旧 `ext` 当成 level 3 直接复用
- 用户必须手动删除 cache 目录才能触发重新解析

### 修复方向

1. 计算 parse_rules 的 hash 指纹
2. 在 `index.yaml` 中存储 `parse_rules_hash`
3. L0 阶段判断 hash 不匹配时，不加入 `fully_cached_vids`，让其进入 L1 重新解析
4. `PUT /api/config` 后通知 scanner 清除 `fully_scanned` 标记或更新 hash

---

## 问题 3：扫描目录后页面过时内容没有更新

### 根本原因（两个致命 Bug）

#### Bug 1：L2/L3 升级不递增 seq（最严重）

```python
# scanner.py:383-388 (Phase L2) — 没有 state.seq += 1
with state.lock:
    _merge_metadata(state.videos[vid], probe_result)
    state.videos[vid]["level"] = 2
    state.videos[vid]["_probe"] = probe_result

# scanner.py:437-442 (Phase L3) — 没有 state.seq += 1
with state.lock:
    state.videos[vid]["level"] = 3
    state.videos[vid].pop("_probe", None)
```

**seq 只在 L0（`scanner.py:316`）和 L1（`scanner.py:350`）阶段递增**。L2/L3 阶段原地修改 item 的 `level` 和元数据，但**不递增 seq**。

而 `status()` 用 `item.get("seq", -1) > since` 过滤更新（`scanner.py:524`）：

```python
for vid, item in state.videos.items():
    if item.get("seq", -1) > since:    # ← L2/L3 升级的 item seq 没变，被过滤掉
        entry = {...}
        updates.append(entry)
```

**后果**：任何在首次 `pollStatus(since=0)` 之后才完成 L2/L3 处理的视频，其元数据和缩略图升级**永远不会推送给前端**。

#### Bug 2：删除的视频不通知前端

```python
# scanner.py:256-261 — 孤儿清理直接移除，无 tombstone
stale_vids = [vid for vid in state.videos if vid not in existing_vids]
for vid in stale_vids:
    state.videos.pop(vid, None)    # ← 不递增 seq，不发删除通知
```

- 后端 `status()` 只遍历**现存的** `state.videos`，被删除的视频不在 updates 里
- 前端 `pollStatus()` 只有"新增/更新"逻辑，**没有删除分支**（`frontend/src/stores/browser.ts:95-123`）
- `cache_index.remove_video_from_index` 函数定义了但**从未被调用**

### 时序分析示例

假设 3 个视频 A、B、C：

| 时刻 | 后端状态 | 前端 lastSeq | 前端可见 |
|------|---------|-------------|---------|
| T=0 | selectL2 返回全量快照，A/B/C 都是 L1（seq=1/2/3） | 0 | A、B、C 的 L1 数据 |
| T=2 | 首次 poll(since=0)。A 已升 L2（seq 仍=1），B 仍 L1（seq=2） | → 3 | A 的 L2 数据可见 |
| T=4 | C 在 T=3 升 L3，但 seq 仍=3。poll(since=3) → **无更新**（3 不大于 3） | 3 | **C 永远停在 L1** |
| T=6+ | 后续所有 L2/L3 升级都不推送 | 3 | 卡片永远不刷新 |

### 附带问题：扫描结束无最终全量刷新

```typescript
// useScanPolling.ts:15-17
} else if (interval) {
  clearInterval(interval)     // ← 直接停止，无最终 pollStatus
  interval = null
}
```

即便修复了 seq 递增 bug，扫描完成时最后一次 pollStatus 和 `scanning=false` 之间仍可能有未拉取的升级。

### 关键代码位置

- **L2 阶段不 bump seq**：`backend/app/services/scanner.py:383-388`
- **L3 阶段不 bump seq**：`backend/app/services/scanner.py:437-442`
- **seq 过滤逻辑**：`backend/app/services/scanner.py:524`
- **孤儿清理无 tombstone**：`backend/app/services/scanner.py:256-261`
- **前端合并逻辑无删除分支**：`frontend/src/stores/browser.ts:95-123`
- **轮询停止无最终刷新**：`frontend/src/composables/useScanPolling.ts:15-17`
- **remove_video_from_index 未使用**：`backend/app/services/cache_index.py:103-107`

### 具体症状

- 视频元数据（编码、分辨率、时长）在卡片上不更新
- 缩略图生成完成后，卡片仍显示"加载中..."占位符
- 已删除的视频继续显示在页面上，直到手动重新点击目录

### 修复方向

1. **Phase L2/L3 修改 item 后必须递增 seq**：
   ```python
   with state.lock:
       state.videos[vid]["level"] = 2
       state.seq += 1
       state.videos[vid]["seq"] = state.seq
   ```

2. **删除时发 tombstone 或全量刷新**：
   - 方案 A：删除时递增 seq 并在 updates 中标记 `deleted=True`
   - 方案 B：扫描完成后做一次全量 groups 替换

3. **扫描结束时做最终 pollStatus**：在 `useScanPolling` 中，`scanning` 变 false 时先执行一次 `pollStatus` 再停止

---

## 问题 4：docker-compose 能否指定构建后镜像 tag

### 当前状态

`docker/docker-compose.yaml:3` **已经指定了**：

```yaml
services:
  video-explorer:
    image: yaofeng928/video-explorer:latest      # ← 已指定镜像名 + tag
    build:
      context: ..
      dockerfile: docker/Dockerfile
```

`docker compose build` 时，构建产物会被打上 `yaofeng928/video-explorer:latest` 标签。

### 如果想灵活指定不同 tag（如 git hash / 版本号）

**推荐方案：环境变量 + build.tags**

```yaml
services:
  video-explorer:
    image: yaofeng928/video-explorer:${IMAGE_TAG:-latest}
    build:
      context: ..
      dockerfile: docker/Dockerfile
      tags:
        - yaofeng928/video-explorer:latest
```

使用方式：
```bash
# 本地默认打 latest
docker compose -f docker/docker-compose.yaml build

# CI 打 git hash
IMAGE_TAG=$(git rev-parse --short HEAD) docker compose -f docker/docker-compose.yaml build
docker compose -f docker/docker-compose.yaml push
```

**`image:` vs `build.tags:` 的区别**：
- `image:` 决定 `docker compose up` 运行时使用哪个镜像
- `build.tags:` 在构建时额外打的标签列表（可同时打多个：latest + git-hash + semver）

如果只配置 `build:` 而不写 `image:`，Docker Compose 会用 `<project_name>-<service_name>:latest` 自动生成名字（如 `docker-video-explorer:latest`），不便于推送。

### 当前无需修改

现有配置已满足基本需求。如需 CI 灵活打 tag，再引入环境变量方案。

---

## 问题优先级汇总

| 问题 | 严重度 | 影响 | 修复复杂度 |
|------|-------|------|-----------|
| **3. 页面过时内容（seq 不递增）** | **致命** | 元数据/缩略图永远不更新，用户体验极差 | 中（需在 L2/L3 阶段加 seq bump） |
| **2. parse_rules 不重解析** | 高 | 修改规则后必须手动删缓存 | 中（需加 hash 指纹 + 通知机制） |
| **1. 进度条不同步** | 中 | 视觉混乱，用户困惑 | 低（统一语义定义） |
| **4. docker tag** | 低 | 当前已可用，灵活度不够 | 低（可选优化） |

**建议优先修复问题 3**，这是最严重的功能性 bug。
