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
  </div>
</template>

<script setup lang="ts">
defineProps<{
  dirs: { id: string; name: string }[]
  selected: string | null
}>()
defineEmits<{
  (e: 'select', id: string): void
}>()
</script>
