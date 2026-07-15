import { defineStore } from 'pinia'
import axios from 'axios'

interface Task {
  id: string
  kind: string  // "scan" | "build"
  label: string
  total: number
  done: number
}

interface CompletedEntry {
  task: Task
  at: number  // 完成时间戳
}

export const useTaskStore = defineStore('task', {
  state: () => ({
    running: [] as Task[],
    completed: [] as CompletedEntry[],  // 刚完成，2秒内仍显示
    timer: null as ReturnType<typeof setTimeout> | null,
  }),
  getters: {
    visible(state): Task[] {
      const now = Date.now()
      const done = state.completed
        .filter(c => now - c.at < 2000)
        .map(c => ({ ...c.task, done: c.task.total }))
      return [...state.running, ...done]
    },
  },
  actions: {
    async poll() {
      try {
        const { data } = await axios.get('/api/tasks')
        const fresh = data as Task[]
        // 运行中消失的任务 → 加入 completed
        for (const t of this.running) {
          if (!fresh.find(n => n.id === t.id)) {
            this.completed.push({ task: { ...t }, at: Date.now() })
          }
        }
        this.running = fresh
        // 清理过期完成记录
        const now = Date.now()
        this.completed = this.completed.filter(c => now - c.at < 2000)
      } catch {
        /* ignore */
      }
    },
    startPolling() {
      if (this.timer) return
      const tick = async () => {
        await this.poll()
        if (this.running.length > 0 || this.completed.length > 0) {
          this.timer = setTimeout(tick, 1500)
        } else {
          this.timer = null
        }
      }
      tick()
    },
    async buildIndex(rootId: string) {
      await axios.post(`/api/roots/${rootId}/build`)
      this.startPolling()
    },
    // 打开目录触发的扫描也启动轮询
    notifyScan() {
      this.startPolling()
    },
  },
})
