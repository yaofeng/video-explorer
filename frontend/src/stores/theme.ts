import { defineStore } from 'pinia'

type ThemeMode = 'light' | 'dark' | 'system'

export const useThemeStore = defineStore('theme', {
  state: () => ({
    mode: (localStorage.getItem('theme-mode') as ThemeMode) || 'system',
    systemDark: window.matchMedia('(prefers-color-scheme: dark)').matches,
  }),
  getters: {
    isDark: (state) => {
      if (state.mode === 'light') return false
      if (state.mode === 'dark') return true
      return state.systemDark
    },
  },
  actions: {
    setMode(mode: ThemeMode) {
      this.mode = mode
      localStorage.setItem('theme-mode', mode)
      this.applyTheme()
    },
    applyTheme() {
      if (this.isDark) {
        document.documentElement.classList.add('dark')
      } else {
        document.documentElement.classList.remove('dark')
      }
    },
    init() {
      // 监听系统主题变化
      const mq = window.matchMedia('(prefers-color-scheme: dark)')
      mq.addEventListener('change', (e) => {
        this.systemDark = e.matches
        if (this.mode === 'system') {
          this.applyTheme()
        }
      })
      // 初始化时应用主题
      this.applyTheme()
    },
  },
})
