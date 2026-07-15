<template>
  <div class="sticky top-0 z-30 bg-white/80 dark:bg-slate-900/80 backdrop-blur-md border-b border-slate-200 dark:border-slate-800">
    <div class="flex gap-1.5 items-center px-4 h-14">
      <!-- 根目录下拉 -->
      <select
        v-model="selectedRootId"
        @change="onRootChange"
        class="px-3 h-9 bg-slate-100 dark:bg-slate-800 rounded-lg text-sm text-slate-700 dark:text-slate-200 border border-transparent hover:border-slate-300 dark:hover:border-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-500 transition cursor-pointer"
      >
        <option value="" disabled>选择视频库</option>
        <option v-for="root in roots" :key="root.id" :value="root.id">
          {{ root.name }}
        </option>
      </select>

      <div class="w-px h-6 bg-slate-200 dark:bg-slate-700 mx-1"></div>

      <!-- L1 一级目录胶囊 -->
      <button
        v-for="l1 in l1Dirs"
        :key="l1.id"
        @click="$emit('selectL1', l1.id)"
        :class="[
          'px-3.5 h-9 rounded-lg text-sm font-medium transition-all duration-200',
          selectedL1 === l1.id
            ? 'bg-indigo-600 text-white shadow-sm shadow-indigo-600/30'
            : 'text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800'
        ]"
      >
        {{ l1.name }}
      </button>

      <div class="flex-1"></div>

      <!-- 主题切换图标组 -->
      <div class="flex items-center gap-0.5 p-0.5 bg-slate-100 dark:bg-slate-800 rounded-lg">
        <button
          v-for="opt in themeOptions"
          :key="opt.value"
          @click="setTheme(opt.value)"
          :title="opt.label"
          :class="[
            'w-8 h-8 flex items-center justify-center rounded-md transition-all duration-200',
            themeMode === opt.value
              ? 'bg-white dark:bg-slate-700 text-indigo-600 dark:text-indigo-400 shadow-sm'
              : 'text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200'
          ]"
        >
          <!-- 电脑（跟随系统） -->
          <svg v-if="opt.value === 'system'" xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <rect x="2" y="3" width="20" height="14" rx="2"/>
            <path d="M8 21h8M12 17v4"/>
          </svg>
          <!-- 太阳（浅色） -->
          <svg v-else-if="opt.value === 'light'" xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="4"/>
            <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/>
          </svg>
          <!-- 月亮（深色） -->
          <svg v-else xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
          </svg>
        </button>
      </div>

      <!-- 设置按钮（仅图标） -->
      <button
        @click="$emit('openSettings')"
        title="设置"
        class="w-9 h-9 flex items-center justify-center rounded-lg text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition"
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="3"/>
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
        </svg>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useThemeStore } from '../stores/theme'

type ThemeMode = 'light' | 'dark' | 'system'

const props = defineProps<{
  roots: { id: string; name: string }[]
  l1Dirs: { id: string; name: string }[]
  selectedRoot: string | null
  selectedL1: string | null
}>()
const emit = defineEmits<{
  (e: 'selectRoot', id: string): void
  (e: 'selectL1', id: string): void
  (e: 'openSettings'): void
}>()

const theme = useThemeStore()
const themeMode = ref<ThemeMode>(theme.mode)
const selectedRootId = ref(props.selectedRoot || '')

const themeOptions: { value: ThemeMode; label: string }[] = [
  { value: 'system', label: '跟随系统' },
  { value: 'light', label: '浅色' },
  { value: 'dark', label: '深色' },
]

function setTheme(mode: ThemeMode) {
  themeMode.value = mode
  theme.setMode(mode)
}

function onRootChange() {
  if (selectedRootId.value) {
    emit('selectRoot', selectedRootId.value)
  }
}
</script>
