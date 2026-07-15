<template>
  <div class="bg-white dark:bg-gray-800 shadow p-4 w-64 flex flex-col">
    <div class="flex-1">
      <button
        v-for="dir in dirs"
        :key="dir.id"
        @click="$emit('select', dir.id)"
        :class="[
          'w-full text-left px-3 py-2 rounded mb-1 relative',
          selected === dir.id
            ? 'bg-blue-500 text-white'
            : 'bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-800 dark:text-gray-200'
        ]"
      >
        {{ dir.name }}
      </button>
    </div>
    <!-- Progress bar for scanning -->
    <div v-if="scanning && progress.total > 0" class="mt-2 pt-2 border-t border-gray-300 dark:border-gray-600">
      <div class="text-xs text-gray-600 dark:text-gray-400 mb-1">
        处理中: {{ progress.level2 }}/{{ progress.total }}
      </div>
      <div class="w-full bg-gray-300 dark:bg-gray-600 rounded-full h-2">
        <div
          class="bg-blue-500 h-2 rounded-full transition-all duration-300"
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
