// frontend/src/composables/useFramePreview.ts
import { ref, watch, onUnmounted, type Ref } from 'vue'
import axios from 'axios'

export interface FrameStatus {
  status: 'not_started' | 'generating' | 'ready'
  total: number
  ready_count: number
  frame_urls: (string | null)[]
}

export function useFramePreview(videoId: Ref<string | null>) {
  const frames = ref<(string | null)[]>(Array(20).fill(null))
  const currentFrame = ref(0)
  const status = ref<'not_started' | 'generating' | 'ready'>('not_started')
  const readyCount = ref(0)

  let pollTimer: ReturnType<typeof setInterval> | null = null

  function nextFrame() {
    // 循环切换到下一个已就绪的帧
    const total = frames.value.length
    for (let i = 1; i <= total; i++) {
      const next = (currentFrame.value + i) % total
      if (frames.value[next] !== null) {
        currentFrame.value = next
        return
      }
    }
  }

  function selectFrame(index: number) {
    if (index >= 0 && index < frames.value.length && frames.value[index] !== null) {
      currentFrame.value = index
    }
  }

  async function pollStatus(): Promise<'not_started' | 'generating' | 'ready'> {
    if (!videoId.value) return 'not_started'
    try {
      const { data } = await axios.get<FrameStatus>(`/api/frames/${videoId.value}`)
      status.value = data.status
      readyCount.value = data.ready_count
      frames.value = data.frame_urls

      if (data.status === 'ready') {
        stopPolling()
      }
      return data.status
    } catch {
      // 网络错误，继续轮询
      return status.value
    }
  }

  async function startGeneration() {
    if (!videoId.value) return
    // 重置状态
    frames.value = Array(20).fill(null)
    currentFrame.value = 0
    status.value = 'not_started'
    readyCount.value = 0

    try {
      await axios.post(`/api/frames/${videoId.value}/generate`)
    } catch {
      // 已在生成或已完成，忽略
    }

    // 先立即查一次状态
    const currentStatus = await pollStatus()

    // 如果还没完成，启动轮询
    if (currentStatus !== 'ready') {
      startPolling()
    }
  }

  function startPolling() {
    stopPolling()
    pollTimer = setInterval(pollStatus, 2000)
  }

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }

  // 当 videoId 变化时重新开始（immediate: true 确保组件挂载时也触发）
  watch(videoId, (newId) => {
    stopPolling()
    if (newId) {
      startGeneration()
    }
  }, { immediate: true })

  onUnmounted(stopPolling)

  return {
    frames,
    currentFrame,
    status,
    readyCount,
    nextFrame,
    selectFrame,
    startGeneration,
    stopPolling,
  }
}
