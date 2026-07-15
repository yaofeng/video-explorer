<template>
  <div class="sticky top-0 z-30 bg-white/80 dark:bg-slate-900/80 backdrop-blur-md border-b border-slate-200 dark:border-slate-800">
    <div class="flex gap-1.5 items-center px-4 h-14">
      <!-- 根目录下拉 -->
      <select
        v-model="selectedRootId"
        @change="onRootChange"
        class="px-3 h-9 bg-slate-100 dark:bg-slate-800 rounded-lg text-sm text-slate-700 dark:text-slate-200 border border-transparent hover:border-slate-300 dark:hover:border-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-500 transition cursor-pointer"
      >
        <option value="" disabled>选择视频库</option>
        <option v-for="root in roots" :key="root.id" :value="root.id">
          {{ root.name }}
        </option>
      </select>

      <div class="w-px h-6 bg-slate-200 dark:bg-slate-700 mx-1"></div>

      <!-- L1 一级目录胶囊 -->
      <button
        v-for="l1 in l1Dirs"
        :key="l1.id"
        @click="$emit('selectL1', l1.id)"
        :class="[
          'px-3.5 h-9 rounded-lg text-sm font-medium transition-all duration-200',
          selectedL1 === l1.id
            ? 'bg-indigo-600 text-white shadow-sm shadow-indigo-600/30'
            : 'text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800'
        ]"
      >
        {{ l1.name }}
      </button>

      <div class="flex-1 min-w-0"></div>

      <!-- 搜索框 -->
      <div class="relative">
        <svg
          class="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 dark:text-slate-500 pointer-events-none"
          xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
        >
          <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
        </svg>
        <input
          :value="filter.search"
          @input="filter.setSearch(($event.target as HTMLInputElement).value)"
          placeholder="搜索文件名..."
          class="w-36 lg:w-48 h-9 pl-8 pr-8 bg-slate-100 dark:bg-slate-800 rounded-lg text-sm text-slate-700 dark:text-slate-200 placeholder:text-slate-400 dark:placeholder:text-slate-500 border border-transparent focus:border-indigo-500/50 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 transition"
        />
        <button
          v-if="filter.search"
          @click="filter.setSearch('')"
          class="absolute right-2 top-1/2 -translate-y-1/2 w-5 h-5 flex items-center justify-center text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M18 6 6 18M6 6l12 12"/></svg>
        </button>
      </div>

      <!-- 排序按钮组 -->
      <div class="flex items-center gap-0.5 p-0.5 bg-slate-100 dark:bg-slate-800 rounded-lg">
        <button
          v-for="s in sortOptions"
          :key="s.field"
          @click="filter.setSort(s.field)"
          :title="s.label + (filter.sortField === s.field ? (filter.sortDir === 'asc' ? ' ↑' : ' ↓') : '')"
          :class="[
            'w-8 h-8 flex items-center justify-center rounded-md transition-all duration-200',
            filter.sortField === s.field
              ? 'bg-white dark:bg-slate-700 text-indigo-600 dark:text-indigo-400 shadow-sm'
              : 'text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200'
          ]"
        >
          <svg v-html="s.icon" class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24"/>
          <span v-if="filter.sortField === s.field" class="text-[9px] ml-0.5">{{ filter.sortDir === 'asc' ? '↑' : '↓' }}</span>
        </button>
      </div>

      <!-- 编码过滤 -->
      <div class="relative" ref="codecRef">
        <button
          @click.stop="codecOpen = !codecOpen"
          title="编码过滤"
          :class="[
            'w-9 h-9 flex items-center justify-center rounded-lg transition',
            !filter.allCodecsSelected
              ? 'bg-indigo-100 dark:bg-indigo-500/20 text-indigo-600 dark:text-indigo-400'
              : 'text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
          ]"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>
          </svg>
        </button>
      </div>

      <!-- 主题切换图标组 -->
      <div class="flex items-center gap-0.5 p-0.5 bg-slate-100 dark:bg-slate-800 rounded-lg">
        <button
          v-for="opt in themeOptions"
          :key="opt.value"
          @click="setTheme(opt.value)"
          :title="opt.label"
          :class="[
            'w-8 h-8 flex items-center justify-center rounded-md transition-all duration-200',
            themeMode === opt.value
              ? 'bg-white dark:bg-slate-700 text-indigo-600 dark:text-indigo-400 shadow-sm'
              : 'text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200'
          ]"
        >
          <svg v-if="opt.value === 'system'" xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/></svg>
          <svg v-else-if="opt.value === 'light'" xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/></svg>
          <svg v-else xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
        </button>
      </div>

      <!-- 设置按钮（仅图标） -->
      <button
        @click="$emit('openSettings')"
        title="设置"
        class="w-9 h-9 flex items-center justify-center rounded-lg text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition"
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="3"/>
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
        </svg>
      </button>
    </div>
  </div>

  <!-- codec 下拉菜单（用 Teleport 渲染到 body，避免 z-index 层级问题） -->
  <Teleport to="body">
    <div v-if="codecOpen" class="fixed inset-0 z-40" @click="codecOpen = false"></div>
    <div
      v-if="codecOpen"
      class="fixed z-50 w-44 bg-white dark:bg-slate-900 rounded-xl shadow-2xl ring-1 ring-slate-200 dark:ring-slate-800 p-2"
      :style="codecMenuStyle"
    >
      <div class="flex justify-between items-center px-3 py-1.5 border-b border-slate-200 dark:border-slate-700 mb-1">
        <span class="text-xs font-medium text-slate-500 dark:text-slate-400">编码筛选</span>
        <button
          v-if="!filter.allCodecsSelected"
          @click="filter.selectAll()"
          class="text-xs text-indigo-600 dark:text-indigo-400 hover:underline"
        >全选</button>
      </div>
      <div
        v-for="c in codecOptions"
        :key="c.value"
        @click="filter.toggleCodec(c.value)"
        class="flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm cursor-pointer hover:bg-slate-100 dark:hover:bg-slate-800 transition"
      >
        <div
          :class="[
            'w-4 h-4 rounded border-2 flex items-center justify-center transition',
            filter.isCodecChecked(c.value)
              ? 'bg-indigo-600 border-indigo-600'
              : 'border-slate-300 dark:border-slate-600'
          ]"
        >
          <svg v-if="filter.isCodecChecked(c.value)" xmlns="http://www.w3.org/2000/svg" class="w-3 h-3 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>
        </div>
        <span class="text-slate-700 dark:text-slate-200">{{ c.label }}</span>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useThemeStore } from '../stores/theme'
import { useFilterStore } from '../stores/filter'

type ThemeMode = 'light' | 'dark' | 'system'
type SortField = 'file_name' | 'file_size' | 'modify_time'

const props = defineProps<{
  roots: { id: string; name: string }[]
  l1Dirs: { id: string; name: string }[]
  selectedRoot: string | null
  selectedL1: string | null
}>()
const emit = defineEmits<{
  (e: 'selectRoot', id: string): void
  (e: 'selectL1', id: string): void
  (e: 'openSettings'): void
}>()

const theme = useThemeStore()
const filter = useFilterStore()
const themeOptions: { value: ThemeMode; label: string }[] = [
  { value: 'system', label: '跟随系统' },
  { value: 'light', label: '浅色' },
  { value: 'dark', label: '深色' },
]
const sortOptions: { field: SortField; label: string; icon: string }[] = [
  { field: 'file_name', label: '文件名', icon: '<path d="M3 7v10M7 5v14M11 4v16M15 9v6M19 2v20"/><polyline points="21 15 15 21"/><polyline points="3 21 9 15"/>' },
  { field: 'file_size', label: '文件大小', icon: '<rect x="4" y="14" width="4" height="7"/><rect x="10" y="10" width="4" height="11"/><rect x="16" y="6" width="4" height="15"/><rect x="22" y="2" width="4" height="19"/>' },
  { field: 'modify_time', label: '修改时间', icon: '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>' },
]
const codecOptions = [
  { value: 'H264', label: 'H264' },
  { value: 'HEVC', label: 'HEVC' },
  { value: 'AV1', label: 'AV1' },
  { value: 'OTHER', label: '其他' },
]

const themeMode = ref<ThemeMode>(theme.mode)
const selectedRootId = ref(props.selectedRoot || '')
const codecOpen = ref(false)
const codecRef = ref<HTMLElement | null>(null)

const codecMenuStyle = computed(() => {
  if (!codecRef.value) return { display: 'none' }
  const rect = codecRef.value.getBoundingClientRect()
  return {
    top: `${rect.bottom + 4}px`,
    right: `${window.innerWidth - rect.right}px`,
  }
})

function setTheme(mode: ThemeMode) {
  themeMode.value = mode
  theme.setMode(mode)
}

function onRootChange() {
  if (selectedRootId.value) {
    emit('selectRoot', selectedRootId.value)
  }
}

/* 全局 ESC 键关闭下拉 */
function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') codecOpen.value = false
}
onMounted(() => document.addEventListener('keydown', onKeydown))
onUnmounted(() => document.removeEventListener('keydown', onKeydown))
</script>

<style scoped>
/* 确保 Teleport 后的下拉菜单在 body 层级正确渲染 */
:deep(.v-overlay) { z-index: 50; }
</style>
