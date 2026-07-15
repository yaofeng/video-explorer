<template>
  <div v-if="task.visibleTasks.length" class="fixed top-4 right-4 z-50 space-y-2 w-72">
    <div
      v-for="t in task.visibleTasks"
      :key="t.id"
      class="bg-white dark:bg-slate-900 rounded-xl shadow-2xl shadow-slate-900/10 ring-1 ring-slate-200 dark:ring-slate-800 p-3"
    >
      <div class="flex justify-between items-center mb-2">
        <div class="flex items-center gap-1.5 min-w-0">
          <span class="text-sm shrink-0">{{ t.kind === 'build' ? '🔨' : '🔍' }}</span>
          <span class="text-sm font-medium text-slate-700 dark:text-slate-200 truncate">{{ t.label }}</span>
        </div>
        <span class="text-xs text-slate-500 dark:text-slate-400 shrink-0 ml-2 tabular-nums">{{ t.done }}/{{ t.total }}</span>
      </div>
      <div class="w-full bg-slate-200 dark:bg-slate-700 rounded-full h-2 overflow-hidden">
        <div
          class="h-full rounded-full transition-all duration-300"
          :class="t.done >= t.total ? 'bg-emerald-500' : 'bg-indigo-500'"
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
