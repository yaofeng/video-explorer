<template>
  <div v-if="task.visibleTasks.length" class="fixed top-4 right-4 z-50 space-y-2 w-72">
    <div
      v-for="t in task.visibleTasks"
      :key="t.id"
      class="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-3 border border-gray-200 dark:border-gray-700"
    >
      <div class="flex justify-between items-center mb-1.5">
        <div class="flex items-center gap-1.5 min-w-0">
          <span class="text-base shrink-0">{{ t.kind === 'build' ? '🔨' : '🔍' }}</span>
          <span class="text-sm font-medium text-gray-800 dark:text-gray-200 truncate">{{ t.label }}</span>
        </div>
        <span class="text-xs text-gray-500 dark:text-gray-400 shrink-0 ml-2">{{ t.done }}/{{ t.total }}</span>
      </div>
      <div class="w-full bg-gray-200 dark:bg-gray-600 rounded-full h-2 overflow-hidden">
        <div
          class="h-full rounded-full transition-all duration-300"
          :class="t.done >= t.total ? 'bg-green-500' : 'bg-blue-500'"
          :style="{ width: pct(t) + '%' }"
        ></div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useTaskStore } from '../stores/task'

const task = useTaskStore()

function pct(t: { done: number; total: number }): number {
  if (!t.total) return 0
  return Math.min(100, Math.round((t.done / t.total) * 100))
}
</script>
