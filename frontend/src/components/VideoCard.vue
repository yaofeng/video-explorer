<template>
  <div
    class="group bg-white dark:bg-slate-900 rounded-xl shadow-sm overflow-hidden cursor-pointer hover:shadow-lg hover:-translate-y-1 transition-all duration-200 ring-1 ring-slate-200/60 dark:ring-slate-800"
    @click="$emit('showLightbox', video)"
  >
    <div class="relative aspect-video bg-slate-900 flex items-center justify-center">
      <img
        v-if="video.level >= 3"
        :src="`/api/thumb/${video.video_id}?size=small`"
        class="w-full h-full object-contain"
        loading="lazy"
      />
      <p
        v-else
        class="text-slate-500 dark:text-slate-400 text-sm animate-pulse"
      >加载中...</p>

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
      <div class="absolute bottom-2 right-2 bg-black/55 backdrop-blur-sm text-white text-[11px] font-medium px-1.5 py-0.5 rounded-md tabular-nums">
        {{ formatSize(video.file_size) }}
      </div>
    </div>

    <!-- 文件名 / 解析信息 -->
    <div class="px-3 py-2">
      <template v-if="video.ext">
        <div v-if="video.ext.title" class="text-sm text-slate-700 dark:text-slate-200 leading-snug line-clamp-1 mb-1" :title="video.ext.title">{{ video.ext.title }}</div>
        <div v-else class="text-sm text-slate-500 dark:text-slate-400 leading-snug line-clamp-1 mb-1">{{ video.file_name }}</div>
        <div class="flex flex-wrap gap-1">
          <span
            v-for="(val, key) in extLabels"
            :key="key"
            @click.stop="copyText(val)"
            :title="'点击复制 ' + val"
            class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md text-[11px] font-medium bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-indigo-100 dark:hover:bg-indigo-500/20 hover:text-indigo-700 dark:hover:text-indigo-300 cursor-pointer transition"
          >
            <span>{{ val }}</span>
          </span>
        </div>
      </template>
      <template v-else>
        <div class="text-sm text-slate-700 dark:text-slate-300 line-clamp-2 leading-snug">{{ video.file_name }}</div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  video: any
}>()
defineEmits<{
  (e: 'showLightbox', video: any): void
}>()

/** ext 中要显示的标签键，按优先级排序 */
const LABEL_KEYS = ['code', 'actress']

const extLabels = computed(() => {
  if (!props.video.ext) return {}
  const result: Record<string, string> = {}
  for (const key of LABEL_KEYS) {
    const val = props.video.ext[key]
    if (val) result[key] = val
  }
  return result
})

function copyText(text: string) {
  navigator.clipboard.writeText(text).catch(() => {
    // 降级：选中复制
    const ta = document.createElement('textarea')
    ta.value = text
    ta.style.position = 'fixed'
    ta.style.opacity = '0'
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
  })
}

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
