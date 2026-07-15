import { defineStore } from 'pinia'

export type SortField = 'file_name' | 'file_size' | 'modify_time'
export type SortDirection = 'asc' | 'desc'

export const ALL_CODECS = ['H264', 'HEVC', 'AV1', 'OTHER']

function load<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key)
    return raw ? JSON.parse(raw) : fallback
  } catch {
    return fallback
  }
}

function save(key: string, val: unknown) {
  localStorage.setItem(key, JSON.stringify(val))
}

/** 排除模式：excludedCodecs 记录用户取消勾选的编码（默认全选） */
export const useFilterStore = defineStore('filter', {
  state: () => ({
    search: load<string>('filter_search', ''),
    sortField: load<SortField>('filter_sort_field', 'file_name'),
    sortDir: load<SortDirection>('filter_sort_dir', 'asc'),
    excludedCodecs: load<string[]>('filter_excluded_codecs', []),
  }),
  getters: {
    /** 该编码是否已勾选（即不在排除列表中） */
    isCodecChecked: (state) => (codec: string) => !state.excludedCodecs.includes(codec),
    /** 全部选中 = 排除列表为空 = 不过滤 */
    allCodecsSelected: (state) => state.excludedCodecs.length === 0,
  },
  actions: {
    setSearch(q: string) {
      this.search = q
      save('filter_search', q)
    },
    setSort(field: SortField) {
      if (this.sortField === field) {
        this.sortDir = this.sortDir === 'asc' ? 'desc' : 'asc'
      } else {
        this.sortField = field
        this.sortDir = field === 'file_name' ? 'asc' : 'desc'
      }
      save('filter_sort_field', this.sortField)
      save('filter_sort_dir', this.sortDir)
    },
    /** 切换编码的勾选状态 */
    toggleCodec(codec: string) {
      const idx = this.excludedCodecs.indexOf(codec)
      if (idx >= 0) {
        this.excludedCodecs.splice(idx, 1)  // 从排除列表移除 = 勾选
      } else {
        this.excludedCodecs.push(codec)     // 加入排除列表 = 取消勾选
      }
      save('filter_excluded_codecs', this.excludedCodecs)
    },
    selectAll() {
      this.excludedCodecs = []
      save('filter_excluded_codecs', [])
    },
  },
})
