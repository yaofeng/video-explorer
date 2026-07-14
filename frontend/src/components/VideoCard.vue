<template>
  <div
    class="bg-white dark:bg-gray-800 rounded shadow overflow-hidden cursor-pointer hover:shadow-lg transition-shadow"
    @click="$emit('showLightbox', video)"
  >
    <div class="relative aspect-video bg-gray-900">
      <img v-if="video.ready" :src="`/api/thumb/${video.video_id}`" class="w-full h-full object-contain" />
      <div v-else class="w-full h-full flex items-center justify-center text-gray-400 dark:text-gray-500">加载中...</div>

      <div class="absolute top-2 left-2 bg-black/60 text-white text-xs px-2 py-1 rounded">
        {{ video.meta?.codec || '-' }}
      </div>
      <div class="absolute top-2 right-2 bg-black/60 text-white text-xs px-2 py-1 rounded">
        {{ video.meta?.resolution_label || '-' }}
      </div>
      <div class="absolute bottom-2 left-2 bg-black/60 text-white text-xs px-2 py-1 rounded">
        {{ formatDuration(video.meta?.duration) }}
      </div>
      <div class="absolute bottom-2 right-2 bg-black/60 text-white text-xs px-2 py-1 rounded">
        {{ formatSize(video.file_size) }}
      </div>
    </div>
    <div class="p-2 text-sm text-gray-800 dark:text-gray-200 line-clamp-2">{{ video.file_name }}</div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  video: any
}>()
defineEmits<{
  (e: 'showLightbox', video: any): void
}>()

function formatDuration(sec?: number): string {
  if (!sec) return '-'
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  const s = Math.floor(sec % 60)
  return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
}

function formatSize(bytes: number): string {
  const gb = bytes / (1024 ** 3)
  return `${gb.toFixed(1)}G`
}
</script>
