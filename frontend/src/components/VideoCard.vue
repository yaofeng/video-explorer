<template>
  <div
    class="group bg-white dark:bg-slate-900 rounded-xl shadow-sm overflow-hidden cursor-pointer hover:shadow-lg hover:-translate-y-1 transition-all duration-200 ring-1 ring-slate-200/60 dark:ring-slate-800"
    @click="$emit('showLightbox', video)"
  >
    <div class="relative aspect-video bg-slate-900 flex items-center justify-center">
      <!-- L3: 缩略图 -->
      <img
        v-if="video.level >= 3"
        :src="`/api/thumb/${video.video_id}?size=small`"
        class="w-full h-full object-contain"
        loading="lazy"
      />
      <!-- L1/L2: 加载占位 -->
      <p
        v-else
        class="text-slate-500 dark:text-slate-400 text-sm animate-pulse"
      >
        加载中...
      </p>

      <!-- L2: 元数据胶囊标签（毛玻璃） -->
      <template v-if="video.level >= 2 && video.meta">
        <div class="absolute top-2 left-2 bg-black/55 backdrop-blur-sm text-white text-[11px] font-medium px-1.5 py-0.5 rounded-md">
          {{ video.meta.codec || '-' }}
        </div>
        <div class="absolute top-2 right-2 bg-black/55 backdrop-blur-sm text-white text-[11px] font-medium px-1.5 py-0.5 rounded-md">
          {{ formatResolution(video.meta.height) }}
        </div>
        <div class="absolute bottom-2 left-2 bg-black/55 backdrop-blur-sm text-white text-[11px] font-medium px-1.5 py-0.5 rounded-md tabular-nums">
          {{ formatDuration(video.meta.duration) }}
        </div>
      </template>
      <!-- 文件大小（始终显示） -->
      <div class="absolute bottom-2 right-2 bg-black/55 backdrop-blur-sm text-white text-[11px] font-medium px-1.5 py-0.5 rounded-md tabular-nums">
        {{ formatSize(video.file_size) }}
      </div>
    </div>
    <div class="px-3 py-2 text-sm text-slate-700 dark:text-slate-300 line-clamp-2 leading-snug">{{ video.file_name }}</div>
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
