<template>
  <div class="bg-white dark:bg-gray-800 rounded shadow overflow-hidden cursor-pointer hover:shadow-lg transition-shadow">
    <div class="relative aspect-video bg-gray-900 flex items-center justify-center">
      <!-- L3: Thumbnail ready -->
      <img
        v-if="video.level >= 3"
        :src="`/api/thumb/${video.video_id}`"
        class="w-full h-full object-contain"
        @click="$emit('showLightbox', video)"
      />
      <!-- L1/L2: Loading placeholder -->
      <p
        v-else
        class="text-gray-400 dark:text-gray-500 text-sm"
        @click="$emit('showLightbox', video)"
      >
        加载中...
      </p>

      <!-- L2: Metadata tags appear when level >= 2 -->
      <template v-if="video.level >= 2 && video.meta">
        <div class="absolute top-2 left-2 bg-black/60 text-white text-xs px-2 py-1 rounded">
          {{ video.meta.codec || '-' }}
        </div>
        <div class="absolute top-2 right-2 bg-black/60 text-white text-xs px-2 py-1 rounded">
          {{ formatResolution(video.meta.height) }}
        </div>
        <div class="absolute bottom-2 left-2 bg-black/60 text-white text-xs px-2 py-1 rounded">
          {{ formatDuration(video.meta.duration) }}
        </div>
      </template>
      <!-- Always show file size -->
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

function formatResolution(height: number): string {
  if (height >= 2160) return '4K'
  if (height >= 1440) return '2K'
  if (height >= 1080) return 'FHD'
  if (height >= 720) return 'HD'
  if (height >= 480) return 'SD'
  if (height >= 360) return 'LD'
  return height ? `${height}P` : '-'
}

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
