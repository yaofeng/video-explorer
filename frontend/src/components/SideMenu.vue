<template>
  <div class="bg-white dark:bg-gray-800 shadow p-4 w-64">
    <button
      v-for="dir in dirs"
      :key="dir.id"
      @click="$emit('select', dir.id)"
      :class="[
        'w-full text-left px-3 py-2 rounded mb-1',
        selected === dir.id
          ? 'bg-blue-500 text-white'
          : 'bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-800 dark:text-gray-200'
      ]"
    >
      {{ dir.name }}
    </button>
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
