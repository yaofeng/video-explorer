<template>
  <div class="bg-white dark:bg-gray-800 shadow p-4 flex gap-2 items-center">
    <select
      v-model="selectedRootId"
      @change="onRootChange"
      class="px-3 py-2 bg-gray-200 dark:bg-gray-700 rounded text-gray-800 dark:text-gray-200"
    >
      <option value="" disabled>选择视频库</option>
      <option v-for="root in roots" :key="root.id" :value="root.id">
        {{ root.name }}
      </option>
    </select>

    <button
      v-for="l1 in l1Dirs"
      :key="l1.id"
      @click="$emit('selectL1', l1.id)"
      :class="[
        'px-4 py-2 rounded',
        selectedL1 === l1.id
          ? 'bg-blue-500 text-white'
          : 'bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 text-gray-800 dark:text-gray-200'
      ]"
    >
      {{ l1.name }}
    </button>
    <div class="flex-1"></div>

    <select
      v-model="themeMode"
      @change="onThemeChange"
      class="px-3 py-2 bg-gray-200 dark:bg-gray-700 rounded text-gray-800 dark:text-gray-200"
    >
      <option value="system">跟随系统</option>
      <option value="light">浅色</option>
      <option value="dark">深色</option>
    </select>
    <router-link
      to="/settings"
      class="px-4 py-2 bg-gray-200 dark:bg-gray-700 rounded hover:bg-gray-300 dark:hover:bg-gray-600 text-gray-800 dark:text-gray-200"
    >
      设置
    </router-link>
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
