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

      <!-- 主题选择 -->
      <select
        v-model="themeMode"
        @change="onThemeChange"
        class="px-3 h-9 bg-slate-100 dark:bg-slate-800 rounded-lg text-sm text-slate-600 dark:text-slate-300 border border-transparent hover:border-slate-300 dark:hover:border-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500/30 transition cursor-pointer"
      >
        <option value="system">跟随系统</option>
        <option value="light">浅色</option>
        <option value="dark">深色</option>
      </select>

      <!-- 设置按钮 -->
      <button
        @click="$emit('openSettings')"
        class="h-9 px-3.5 rounded-lg text-sm font-medium text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition flex items-center gap-1.5"
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="3"/>
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
        </svg>
        设置
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useThemeStore } from '../stores/theme'

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
const themeMode = ref(theme.mode)
const selectedRootId = ref(props.selectedRoot || '')

function onRootChange() {
  if (selectedRootId.value) {
    emit('selectRoot', selectedRootId.value)
  }
}

function onThemeChange() {
  theme.setMode(themeMode.value as 'light' | 'dark' | 'system')
}
</script>
