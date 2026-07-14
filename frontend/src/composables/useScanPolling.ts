import { watch, onUnmounted } from 'vue'
import { useBrowserStore } from '../stores/browser'

export function useScanPolling() {
  const browser = useBrowserStore()
  let interval: ReturnType<typeof setInterval> | null = null

  const start = () => {
    if (interval) return
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
