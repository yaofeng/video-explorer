import { defineStore } from 'pinia'
import axios from 'axios'

interface VideoItem {
  video_id: string
  file_name: string
  file_size: number
  group: string
  level: number  // 1=filename, 2=+metadata, 3=+thumbnail
  meta: {
    codec: string
    duration: number
    width: number
    height: number
    resolution_str: string
    file_size: number
  } | null
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
      // Merge updates into groups
      for (const update of data.updates) {
        for (const group of this.groups) {
          if (group.name === update.group) {
            const existing = group.videos.find(v => v.video_id === update.video_id)
            if (existing) {
              existing.level = update.level
              if (update.meta) {
                existing.meta = update.meta
              }
            }
            break
          }
        }
      }
    },
  },
})
