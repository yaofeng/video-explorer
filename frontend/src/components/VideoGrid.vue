<template>
  <div class="flex-1 overflow-auto p-6 bg-slate-50 dark:bg-slate-950">
    <div v-if="filteredGroups.length === 0" class="text-center mt-16 text-slate-400 dark:text-slate-500">
      <p class="text-lg">没有匹配的视频</p>
      <button
        v-if="filter.search || !filter.allCodecsSelected"
        @click="clearFilters"
        class="mt-2 text-sm text-indigo-600 dark:text-indigo-400 hover:underline"
      >清除筛选条件</button>
    </div>
    <div v-for="group in paginatedGroups" :key="group.name" class="mb-8">
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
      <!-- 分页控件 -->
      <div
        v-if="pageSize > 0 && getGroupTotalPages(group.name) > 1"
        class="mt-4 flex items-center justify-center gap-2"
      >
        <button
          @click="changePage(group.name, -1)"
          :disabled="currentPage[group.name] <= 1"
          class="px-3 py-1 text-sm rounded bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-300 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-slate-300 dark:hover:bg-slate-600"
        >上一页</button>
        <span class="text-sm text-slate-600 dark:text-slate-400">
          {{ currentPage[group.name] }} / {{ getGroupTotalPages(group.name) }}
        </span>
        <button
          @click="changePage(group.name, 1)"
          :disabled="currentPage[group.name] >= getGroupTotalPages(group.name)"
          class="px-3 py-1 text-sm rounded bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-300 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-slate-300 dark:hover:bg-slate-600"
        >下一页</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import { useFilterStore } from '../stores/filter'
import { useConfigStore } from '../stores/config'
import VideoCard from './VideoCard.vue'

const props = defineProps<{
  groups: any[]
  columnSize: number
}>()
defineEmits<{
  (e: 'showLightbox', video: any): void
}>()

const filter = useFilterStore()
const config = useConfigStore()

const pageSize = computed(() => config.page_size || 0)

// 每个组的当前页码
const currentPage = reactive<Record<string, number>>({})

const KNOWN_CODECS = ['H264', 'HEVC', 'AV1']

function videoMatches(v: any): boolean {
  // 搜索过滤
  if (filter.search) {
    const q = filter.search.toLowerCase()
    if (!v.file_name.toLowerCase().includes(q)) return false
  }
  // 编码过滤（排除模式）：excludedCodecs 记录被取消勾选的编码
  // 全选状态（排除列表为空）= 不过滤
  if (filter.excludedCodecs.length > 0 && v.codec) {
    const c = v.codec
    const excludedOther = filter.excludedCodecs.includes('OTHER')
    const excludedKnown = filter.excludedCodecs.filter(k => KNOWN_CODECS.includes(k))

    if (excludedKnown.length === 0 && !excludedOther) return true  // 无排除

    if (excludedOther && excludedKnown.length === 0) {
      // 只排除了"其他"：已知编码显示，非已知编码隐藏
      return KNOWN_CODECS.includes(c)
    }
    if (excludedOther && excludedKnown.length > 0) {
      // 排除了"其他"+部分已知：已知的只要不在排除列表就显示
      if (KNOWN_CODECS.includes(c)) return !excludedKnown.includes(c)
      return false  // 非已知编码被"其他"排除
    }
    // 只排除了部分已知编码
    return !excludedKnown.includes(c)
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

// 计算每个组的总页数
function getGroupTotalPages(groupName: string): number {
  if (pageSize.value <= 0) return 1
  const group = filteredGroups.value.find(g => g.name === groupName)
  if (!group) return 1
  return Math.ceil(group.videos.length / pageSize.value)
}

// 分页后的组
const paginatedGroups = computed(() => {
  if (pageSize.value <= 0) {
    return filteredGroups.value
  }
  return filteredGroups.value.map(g => {
    const page = currentPage[g.name] || 1
    const start = (page - 1) * pageSize.value
    const end = start + pageSize.value
    return {
      name: g.name,
      videos: g.videos.slice(start, end),
    }
  })
})

function changePage(groupName: string, delta: number) {
  const totalPages = getGroupTotalPages(groupName)
  const current = currentPage[groupName] || 1
  const newPage = Math.max(1, Math.min(totalPages, current + delta))
  currentPage[groupName] = newPage
}

// 当筛选条件变化时，重置所有组的页码到第 1 页
watch([() => filter.search, () => filter.excludedCodecs, () => filter.sortField, () => filter.sortDir], () => {
  for (const key in currentPage) {
    currentPage[key] = 1
  }
})

// 当目录变化（分组名集合变化）时重置页码。
// 用浅签名代替 deep watch，避免每次轮询合并都深遍历整个视频树（M12）。
const groupSignature = computed(() => props.groups.map(g => g.name).join('\n'))
watch(groupSignature, () => {
  for (const key in currentPage) {
    delete currentPage[key]
  }
})

function clearFilters() {
  filter.setSearch('')
  filter.selectAll()
}
</script>
