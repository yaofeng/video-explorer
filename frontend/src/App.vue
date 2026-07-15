<template>
  <div class="min-h-screen bg-gray-100 dark:bg-gray-900 text-gray-900 dark:text-gray-100">
    <router-view />
    <TaskToast />
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useThemeStore } from './stores/theme'
import { useTaskStore } from './stores/task'
import TaskToast from './components/TaskToast.vue'

const theme = useThemeStore()
const task = useTaskStore()

onMounted(() => {
  theme.init()
  // 启动时检查是否有运行中的任务
  task.startPolling()
})
</script>
