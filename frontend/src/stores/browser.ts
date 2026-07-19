import { defineStore } from 'pinia'
import axios from 'axios'

/**
 * 扁平视频条目（与后端 index.yaml / API 结构一致）。
 */
interface VideoItem {
  video_id: string
  file_name: string
  file_size: number  // 单位：MB（整数）
  group: string
  level: number  // 1=filename, 2=+metadata, 3=+thumbnail
  modify_time?: number
  ext?: Record<string, string>
  codec?: string
  width?: number
  height?: number
  duration?: number
  resolution_label?: string
}

interface Group {
  name: string
  videos: VideoItem[]
}

export interface ScanError {
  file: string
  message: string
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
    // 扫描阶段："idle" | "quick" | "deep" | "done"
    phase: 'idle' as string,
    // 聚合错误信息
    errors: [] as ScanError[],
    // 上次轮询收到的最大 seq
    lastSeq: 0,
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
      this.lastSeq = 0
      this.errors = []
      this.phase = 'idle'
      const { data } = await axios.get(`/api/l2/${l2Id}/videos`)
      this.groups = data.groups
      this.scanning = data.scanning
      // 打开目录触发扫描 → 启动任务浮窗轮询（build 任务仍显示进度）
      if (this.scanning) {
        const { useTaskStore } = await import('./task')
        useTaskStore().notifyScan()
      }
    },
    async pollStatus() {
      if (!this.selectedL2Id) return
      const { data } = await axios.get(
        `/api/scan-status?l2_id=${this.selectedL2Id}&since=${this.lastSeq}`,
      )
      this.scanning = data.scanning
      this.phase = data.phase || 'idle'

      // Phase 1 完成：后端发 refresh_full 信号 → 全量刷新（处理删除/新增）
      if (data.refresh_full) {
        await this._refreshGroups()
      }

      // 合并增量更新（L2/L3 升级）
      for (const update of data.updates) {
        let placed = false
        for (const group of this.groups) {
          if (group.name === update.group) {
            const existing = group.videos.find(v => v.video_id === update.video_id)
            if (existing) {
              Object.assign(existing, update)
              delete (existing as any).seq
              placed = true
            } else {
              const { seq, ...item } = update
              group.videos.push(item as VideoItem)
              placed = true
            }
            break
          }
        }
        if (!placed) {
          const { seq, ...item } = update
          this.groups.push({ name: update.group, videos: [item as VideoItem] })
        }
        if (typeof update.seq === 'number' && update.seq > this.lastSeq) {
          this.lastSeq = update.seq
        }
      }

      if (typeof data.last_seq === 'number' && data.last_seq > this.lastSeq) {
        this.lastSeq = data.last_seq
      }

      // 错误聚合
      if (Array.isArray(data.errors) && data.errors.length > 0) {
        this.errors = data.errors
      }
    },
    async _refreshGroups() {
      // Phase 1 完成后全量重新拉取（处理删除/新增/分组变化）
      if (!this.selectedL2Id) return
      try {
        const { data } = await axios.get(`/api/l2/${this.selectedL2Id}/videos`)
        this.groups = data.groups
        this.lastSeq = 0  // 重置增量游标
      } catch {
        // 全量拉取失败时保留现有数据
      }
    },
    clearErrors() {
      this.errors = []
    },
  },
})
