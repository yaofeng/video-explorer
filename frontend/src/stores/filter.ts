import { defineStore } from 'pinia'

export type SortField = 'file_name' | 'file_size' | 'modify_time'
export type SortDirection = 'asc' | 'desc'

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

export const useFilterStore = defineStore('filter', {
  state: () => ({
    search: load<string>('filter_search', ''),
    sortField: load<SortField>('filter_sort_field', 'file_name'),
    sortDir: load<SortDirection>('filter_sort_dir', 'asc'),
    codecs: load<string[]>('filter_codecs', []),
  }),
  actions: {
    setSearch(q: string) {
      this.search = q
      save('filter_search', q)
    },
    setSort(field: SortField) {
      if (this.sortField === field) {
        // 同字段切换方向
        this.sortDir = this.sortDir === 'asc' ? 'desc' : 'asc'
      } else {
        this.sortField = field
        // file_name 默认升序，其余默认降序
        this.sortDir = field === 'file_name' ? 'asc' : 'desc'
      }
      save('filter_sort_field', this.sortField)
      save('filter_sort_dir', this.sortDir)
    },
    toggleCodec(codec: string) {
      const idx = this.codecs.indexOf(codec)
      if (idx >= 0) {
        this.codecs.splice(idx, 1)
      } else {
        this.codecs.push(codec)
      }
      save('filter_codecs', this.codecs)
    },
    setCodecs(list: string[]) {
      this.codecs = list
      save('filter_codecs', list)
    },
    clearCodecs() {
      this.codecs = []
      save('filter_codecs', [])
    },
  },
})
