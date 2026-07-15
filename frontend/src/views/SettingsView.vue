<template>
  <div class="max-w-2xl mx-auto p-8">
    <h1 class="text-2xl font-bold mb-6 text-gray-900 dark:text-gray-100">设置</h1>
    <div class="bg-white dark:bg-gray-800 rounded shadow p-6 space-y-4">
      <div>
        <label class="block text-sm font-medium mb-1 text-gray-700 dark:text-gray-300">视频目录列表</label>
        <div v-for="(path, i) in config.video_path_list" :key="i" class="flex gap-2 mb-2">
          <input
            v-model="config.video_path_list[i]"
            type="text"
            class="flex-1 border border-gray-300 dark:border-gray-600 rounded px-2 py-1 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
          />
          <!-- 构建索引按钮（仅图标） -->
          <button
            @click="buildIndex(path, i)"
            :disabled="building[i]"
            :title="building[i] ? '构建中...' : '构建该视频库索引'"
            class="px-3 py-1 bg-amber-500 text-white rounded hover:bg-amber-600 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
          >
            <!-- 锤子图标 SVG -->
            <svg v-if="!building[i]" xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>
            </svg>
            <!-- 加载动画 -->
            <svg v-else xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 12a9 9 0 1 1-6.219-8.56" stroke-linecap="round"/>
            </svg>
          </button>
          <button @click="config.video_path_list.splice(i, 1)" class="px-3 py-1 bg-red-500 text-white rounded hover:bg-red-600">×</button>
        </div>
        <button @click="config.video_path_list.push('')" class="px-3 py-1 bg-blue-500 text-white rounded hover:bg-blue-600">+ 添加目录</button>
      </div>
      <div>
        <label class="block text-sm font-medium mb-1 text-gray-700 dark:text-gray-300">每页视频数 (0=不分页)</label>
        <input
          v-model.number="config.page_size"
          type="number"
          class="border border-gray-300 dark:border-gray-600 rounded px-2 py-1 w-32 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
        />
      </div>
      <div>
        <label class="block text-sm font-medium mb-1 text-gray-700 dark:text-gray-300">每行视频数</label>
        <input
          v-model.number="config.column_size"
          type="number"
          class="border border-gray-300 dark:border-gray-600 rounded px-2 py-1 w-32 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
        />
      </div>
      <div class="flex gap-2">
        <button @click="save" class="px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600">保存</button>
        <router-link to="/" class="px-4 py-2 bg-gray-300 dark:bg-gray-600 rounded text-gray-800 dark:text-gray-200 hover:bg-gray-400 dark:hover:bg-gray-500">返回</router-link>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import axios from 'axios'
import { useConfigStore } from '../stores/config'
import { useTaskStore } from '../stores/task'
import { useRouter } from 'vue-router'

const config = useConfigStore()
const taskStore = useTaskStore()
const router = useRouter()

// 每个目录的构建按钮状态
const building = reactive<Record<number, boolean>>({})
// path → root_id 映射（从 /api/roots 获取）
const pathToId = ref<Record<string, string>>({})

onMounted(async () => {
  await config.fetch()
  try {
    const { data } = await axios.get('/api/roots')
    const map: Record<string, string> = {}
    for (const r of data) {
      map[r.path] = r.id
      // 也用目录名做 key，兜底匹配
      map[r.name] = r.id
    }
    pathToId.value = map
  } catch {
    /* ignore */
  }
})

async function save() {
  await config.update()
  router.push('/')
}

async function buildIndex(path: string, i: number) {
  if (!path) return
  // 查找 root_id：精确路径 → 目录名兜底
  const rootId = pathToId.value[path] || pathToId.value[path.split('/').filter(Boolean).pop() || '']
  if (!rootId) {
    alert('未找到该目录的根 ID，请先保存配置')
    return
  }
  building[i] = true
  try {
    await taskStore.buildIndex(rootId)
  } finally {
    // 浮窗持续显示进度；按钮稍后恢复（实际完成由浮窗体现）
    setTimeout(() => { building[i] = false }, 2000)
  }
}
</script>
