<template>
  <div class="flex-1 overflow-auto p-6 bg-slate-50 dark:bg-slate-950">
    <div v-if="filteredGroups.length === 0" class="text-center mt-16 text-slate-400 dark:text-slate-500">
      <p class="text-lg">没有匹配的视频</p>
      <button
        v-if="filter.search || filter.codecs.length"
        @click="clearFilters"
        class="mt-2 text-sm text-indigo-600 dark:text-indigo-400 hover:underline"
      >清除筛选条件</button>
    </div>
    <div v-for="group in filteredGroups" :key="group.name" class="mb-8">
      <h3
        v-if="group.name !== '未分组'"
        class="text-sm font-semibold mb-3 text-slate-500 dark:text-slate-400 uppercase tracking-wide"
      >{{ group.name }}</h3>
      <div class="grid gap-4" :style="{ gridTemplateColumns: `repeat(${columnSize || 4}, minmax(0, 1fr))` }">
        <VideoCard
          v-for="video in group.videos"
          :key="video.video_id"
          :video="video"
          @showLightbox="(v) => $emit('showLightbox', v)"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useFilterStore } from '../stores/filter'
import VideoCard from './VideoCard.vue'

const props = defineProps<{
  groups: any[]
  columnSize: number
}>()
defineEmits<{
  (e: 'showLightbox', video: any): void
}>()

const filter = useFilterStore()

const KNOWN_CODECS = ['H264', 'HEVC', 'AV1']

function videoMatches(v: any): boolean {
  // 搜索过滤
  if (filter.search) {
    const q = filter.search.toLowerCase()
    if (!v.file_name.toLowerCase().includes(q)) return false
  }
  // 编码过滤：没有 meta 信息的视频（level 1）不过滤（仍然显示）
  // 有 meta 的才参与编码过滤
  if (filter.codecs.length > 0 && v.meta?.codec) {
    const c = v.meta.codec
    const hasOther = filter.codecs.includes('OTHER')
    const knownSelected = filter.codecs.filter(k => KNOWN_CODECS.includes(k))

    if (hasOther && knownSelected.length === 0) {
      // 只选了"其他" → 只显示非已知编码的视频
      if (KNOWN_CODECS.includes(c)) return false
    } else if (hasOther && knownSelected.length > 0) {
      // 选了"其他"+ 已知编码 → 显示已知编码 + 非已知编码
      if (!KNOWN_CODECS.includes(c) && !knownSelected.includes(c)) return false
    } else if (knownSelected.length > 0) {
      // 只选了已知编码
      if (!knownSelected.includes(c)) return false
    }
  }
  return true
}

function videoSorter(a: any, b: any): number {
  const dir = filter.sortDir === 'asc' ? 1 : -1
  switch (filter.sortField) {
    case 'file_name':
      return dir * a.file_name.localeCompare(b.file_name)
    case 'file_size':
      return dir * ((a.file_size || 0) - (b.file_size || 0))
    case 'modify_time':
      return dir * ((a.modify_time || 0) - (b.modify_time || 0))
    default:
      return 0
  }
}

const filteredGroups = computed(() => {
  return props.groups
    .map(g => ({
      name: g.name,
      videos: (g.videos || []).filter(videoMatches).sort(videoSorter),
    }))
    .filter(g => g.videos.length > 0)
})

function clearFilters() {
  filter.setSearch('')
  filter.clearCodecs()
}
</script>
