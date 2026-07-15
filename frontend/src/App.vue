<template>
  <div class="min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 transition-colors duration-200">
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
  task.startPolling()
})
</script>
