<template>
  <div class="w-60 shrink-0 bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-800 flex flex-col">
    <div class="flex-1 overflow-auto p-3 space-y-1">
      <button
        v-for="dir in dirs"
        :key="dir.id"
        @click="$emit('select', dir.id)"
        :class="[
          'w-full text-left px-3 py-2 rounded-lg text-sm font-medium transition-all duration-200',
          selected === dir.id
            ? 'bg-indigo-50 dark:bg-indigo-500/15 text-indigo-700 dark:text-indigo-300'
            : 'text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800'
        ]"
      >
        {{ dir.name }}
      </button>
    </div>
    <!-- 进度条 -->
    <div
      v-if="scanning && progress.total > 0"
      class="m-3 p-3 rounded-lg bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700"
    >
      <div class="flex justify-between items-center mb-2">
        <span class="text-xs font-medium text-slate-600 dark:text-slate-300">处理中</span>
        <span class="text-xs text-slate-500 dark:text-slate-400 tabular-nums">{{ progress.level2 }}/{{ progress.total }}</span>
      </div>
      <div class="w-full bg-slate-200 dark:bg-slate-700 rounded-full h-1.5 overflow-hidden">
        <div
          class="bg-indigo-500 h-full rounded-full transition-all duration-300"
          :style="{ width: `${Math.round((progress.level2 / progress.total) * 100)}%` }"
        ></div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  dirs: { id: string; name: string }[]
  selected: string | null
  scanning: boolean
  progress: { total: number; level1: number; level2: number; level3: number }
}>()
defineEmits<{
  (e: 'select', id: string): void
}>()
</script>
