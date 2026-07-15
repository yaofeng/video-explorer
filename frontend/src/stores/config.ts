import { defineStore } from 'pinia'
import axios from 'axios'

export const useConfigStore = defineStore('config', {
  state: () => ({
    video_path_list: [] as string[],
    page_size: 0,
    column_size: 4,
    parse_rules: [] as { name: string; pattern: string }[],
  }),
  actions: {
    async fetch() {
      const { data } = await axios.get('/api/config')
      this.video_path_list = data.video_path_list
      this.page_size = data.page_size
      this.column_size = data.column_size
      this.parse_rules = data.parse_rules || []
    },
    async update() {
      await axios.put('/api/config', {
        video_path_list: this.video_path_list,
        page_size: this.page_size,
        column_size: this.column_size,
        parse_rules: this.parse_rules,
      })
      await this.fetch()
    },
    addRule() {
      this.parse_rules.push({ name: '', pattern: '' })
    },
    removeRule(i: number) {
      this.parse_rules.splice(i, 1)
    },
  },
})
