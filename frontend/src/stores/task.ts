import { defineStore } from 'pinia'
import axios from 'axios'

// 连续失败多少次后停止轮询（M11，避免服务器不可达时无限重试）
const MAX_CONSECUTIVE_ERRORS = 5

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
    active: false,  // 是否正在轮询
    consecutiveErrors: 0,  // 连续失败计数（M11）
  }),
  getters: {
    visibleTasks(state): Task[] {
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
        this.consecutiveErrors = 0  // 成功 → 清零（M11）
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
        // 连续失败超过阈值 → 停止轮询，避免服务器挂掉后无限重试（M11）
        this.consecutiveErrors += 1
        if (this.consecutiveErrors >= MAX_CONSECUTIVE_ERRORS) {
          this.running = []
          this.active = false
        }
      }
    },
    startPolling() {
      if (this.active) return
      this.active = true
      this.consecutiveErrors = 0
      const tick = async () => {
        await this.poll()
        // 有运行中或刚完成的任务 → 继续；否则停止
        if (this.active && (this.running.length > 0 || this.completed.length > 0)) {
          setTimeout(tick, 1000)
        } else {
          this.active = false
        }
      }
      tick()
    },
    async buildIndex(rootId: string) {
      // 立即先轮询一次（抢占式），再发请求，确保不漏掉快速任务
      this.startPolling()
      await axios.post(`/api/roots/${rootId}/build`)
      await this.poll()  // 请求返回后立刻再拉一次
      this.startPolling()
    },
    notifyScan() {
      this.startPolling()
    },
  },
})
