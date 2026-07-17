<template>
  <transition
    enter-active-class="transition duration-200 ease-out"
    enter-from-class="opacity-0"
    enter-to-class="opacity-100"
    leave-active-class="transition duration-150 ease-in"
    leave-from-class="opacity-100"
    leave-to-class="opacity-0"
  >
    <div
      v-if="video"
      class="fixed inset-0 bg-slate-950/85 backdrop-blur-sm flex items-center justify-center z-50 p-4 sm:p-8"
      @click.self="$emit('close')"
    >
      <div class="relative w-full max-w-5xl">
        <!-- 关闭按钮 -->
        <button
          @click="$emit('close')"
          class="absolute -top-2 -right-2 z-10 w-9 h-9 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 rounded-full shadow-lg flex items-center justify-center hover:scale-110 transition"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M18 6 6 18M6 6l12 12"/></svg>
        </button>

        <!-- 视频标题 + 元信息 -->
        <div class="mb-3">
          <div class="text-lg font-semibold text-white leading-snug line-clamp-1">{{ displayName }}</div>
          <div class="flex gap-2 mt-1 text-xs text-slate-400">
            <span v-if="video.codec">{{ video.codec }}</span>
            <span v-if="video.resolution_label">{{ video.resolution_label }}</span>
            <span v-if="video.duration">{{ formatDuration(video.duration) }}</span>
            <span>{{ formatSize(video.file_size) }}</span>
          </div>
        </div>

        <!-- 大图预览区 -->
        <div
          class="relative bg-black rounded-lg overflow-hidden aspect-video flex items-center justify-center"
          @contextmenu.prevent="onRightClick"
        >
          <img
            v-if="displaySrc"
            :src="displaySrc"
            class="max-w-full max-h-full object-contain"
          />
          <p v-else class="text-slate-500 text-sm animate-pulse">加载中...</p>

          <!-- 帧计数器 -->
          <div
            v-if="framesReady"
            class="absolute top-2 left-2 bg-black/60 text-white text-xs px-2 py-1 rounded-md backdrop-blur-sm"
          >
            {{ currentFrame + 1 }} / {{ frames.length }}
          </div>

          <!-- 右键提示 -->
          <div
            v-if="framesReady"
            class="absolute bottom-2 right-2 bg-black/60 text-slate-400 text-xs px-2 py-1 rounded-md backdrop-blur-sm"
          >
            右键切换下一帧 →
          </div>
        </div>

        <!-- 小图条 -->
        <div class="flex gap-1 mt-3 overflow-x-auto py-1 px-1" ref="stripRef">
          <div
            v-for="(url, i) in frames"
            :key="i"
            @click="onSelectFrame(i)"
            class="flex-shrink-0 w-20 aspect-video rounded cursor-pointer transition-all"
            :class="i === currentFrame && url ? 'ring-2 ring-indigo-500 shadow-lg shadow-indigo-500/40' : 'ring-1 ring-slate-700 hover:ring-slate-500'"
          >
            <img
              v-if="url"
              :src="url"
              class="w-full h-full object-cover rounded"
              loading="lazy"
            />
            <div v-else class="w-full h-full bg-slate-800 rounded flex items-center justify-center">
              <svg class="w-4 h-4 text-slate-600 animate-spin" viewBox="0 0 24 24" fill="none">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
              </svg>
            </div>
          </div>
        </div>

        <!-- 播放按钮 -->
        <div class="flex gap-3 justify-center mt-4">
          <button
            @click="openInBrowser"
            title="浏览器播放"
            class="w-10 h-10 rounded-full bg-blue-600 hover:bg-blue-500 text-white flex items-center justify-center transition hover:scale-110"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
              <path d="M8 5v14l11-7z"/>
            </svg>
          </button>
          <button
            @click="openInIINA"
            title="IINA 播放"
            class="w-10 h-10 rounded-full bg-purple-600 hover:bg-purple-500 text-white flex items-center justify-center transition hover:scale-110"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
              <path d="M8 5v14l11-7z"/>
              <circle cx="12" cy="12" r="11" fill="none" stroke="currentColor" stroke-width="1.5"/>
            </svg>
          </button>
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup lang="ts">
import { computed, ref, watch, nextTick } from 'vue'
import { useFramePreview } from '../composables/useFramePreview'

const props = defineProps<{
  video: any | null
}>()
defineEmits<{
  (e: 'close'): void
}>()

const videoIdRef = computed(() => props.video?.video_id ?? null)
const { frames, currentFrame, status, nextFrame, selectFrame } = useFramePreview(videoIdRef)
const stripRef = ref<HTMLElement | null>(null)

const framesReady = computed(() => status.value === 'ready' || status.value === 'generating')

const displaySrc = computed(() => {
  if (frames.value[currentFrame.value]) {
    return frames.value[currentFrame.value]
  }
  if (props.video?.video_id) {
    return `/api/thumb/${props.video.video_id}`
  }
  return null
})

const displayName = computed(() => {
  if (!props.video) return ''
  if (props.video.ext?.title) return props.video.ext.title
  return props.video.file_name || ''
})

function onRightClick() {
  nextFrame()
  // scrollStripToCurrent 由 watch(currentFrame) 自动触发
}

function onSelectFrame(i: number) {
  selectFrame(i)
  // scrollStripToCurrent 由 watch(currentFrame) 自动触发
}

function scrollStripToCurrent() {
  nextTick(() => {
    if (!stripRef.value) return
    const active = stripRef.value.children[currentFrame.value] as HTMLElement | undefined
    if (active) {
      active.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' })
    }
  })
}

function openInBrowser() {
  if (!props.video?.video_id) return
  window.open(`/api/video/${props.video.video_id}`, '_blank')
}

function openInIINA() {
  if (!props.video?.video_id) return
  const videoUrl = `${window.location.origin}/api/video/${props.video.video_id}`
  window.location.href = `iina://open?url=${encodeURIComponent(videoUrl)}`
}

function formatDuration(sec?: number): string {
  if (sec == null || sec < 0) return ''
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  const s = Math.floor(sec % 60)
  return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
}

function formatSize(mb: number): string {
  if (mb == null || mb < 0) return ''
  if (mb < 1024) return `${mb}M`
  return `${(mb / 1024).toFixed(1)}G`
}

watch(currentFrame, () => {
  scrollStripToCurrent()
})
</script>
