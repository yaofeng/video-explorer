import { watch, onUnmounted } from 'vue'
import { useBrowserStore } from '../stores/browser'

export function useScanPolling() {
  const browser = useBrowserStore()
  let interval: ReturnType<typeof setInterval> | null = null

  const start = () => {
    if (interval) return
    // 立即轮询一次，避免等待第一个 2s 周期才更新缩略图
    browser.pollStatus()
    interval = setInterval(async () => {
      if (browser.scanning) {
        await browser.pollStatus()
      } else if (interval) {
        clearInterval(interval)
        interval = null
      }
    }, 2000)
  }

  const stop = () => {
    if (interval) {
      clearInterval(interval)
      interval = null
    }
  }

  watch(() => browser.scanning, (val) => {
    if (val) start()
    else stop()
  })

  onUnmounted(stop)

  return { start, stop }
}
