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
