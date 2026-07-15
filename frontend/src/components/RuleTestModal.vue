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
      v-if="open"
      class="fixed inset-0 bg-slate-900/50 backdrop-blur-sm flex items-start justify-center z-50 pt-16 px-4"
      @click.self="$emit('close')"
    >
      <div class="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl ring-1 ring-slate-200 dark:ring-slate-800 w-full max-w-4xl max-h-[80vh] flex flex-col">
        <!-- 头部 -->
        <div class="flex items-center justify-between px-5 py-4 border-b border-slate-200 dark:border-slate-800 shrink-0">
          <h2 class="text-base font-semibold text-slate-900 dark:text-slate-100">规则测试</h2>
          <button
            @click="$emit('close')"
            class="text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 w-8 h-8 flex items-center justify-center rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M18 6 6 18M6 6l12 12"/></svg>
          </button>
        </div>

        <!-- 内容 -->
        <div class="p-5 space-y-4 overflow-auto">
          <!-- 级联选择 -->
          <div>
            <label class="block text-sm font-medium mb-2 text-slate-700 dark:text-slate-300">选择测试目录</label>
            <div class="flex gap-2">
              <!-- 第一级：视频库根目录 -->
              <select
                v-model="selectedRoot"
                @change="onRootChange"
                class="flex-1 h-9 border border-slate-300 dark:border-slate-700 rounded-lg px-3 text-sm bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-500 transition"
              >
                <option value="">选择视频库</option>
                <option v-for="r in roots" :key="r.id" :value="r.path">{{ r.name }}</option>
              </select>

              <!-- 第二级：根目录下的一级目录 -->
              <select
                v-model="selectedL1"
                @change="onL1Change"
                :disabled="!selectedRoot"
                class="flex-1 h-9 border border-slate-300 dark:border-slate-700 rounded-lg px-3 text-sm bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-500 transition disabled:opacity-40"
              >
                <option value="">选择一级目录</option>
                <option v-for="l1 in l1Dirs" :key="l1.id" :value="l1.path">{{ l1.name }}</option>
              </select>

              <!-- 第三级：二级子目录 -->
              <select
                v-model="selectedL2"
                @change="onL2Change"
                :disabled="!selectedL1"
                class="flex-1 h-9 border border-slate-300 dark:border-slate-700 rounded-lg px-3 text-sm bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-500 transition disabled:opacity-40"
              >
                <option value="">选择二级目录</option>
                <option v-for="l2 in l2Dirs" :key="l2.id" :value="l2.path">{{ l2.name }}</option>
              </select>
            </div>
            <p v-if="selectedL2" class="text-xs text-slate-400 mt-2 font-mono">缓存路径: {{ selectedL2 }}</p>
          </div>

          <!-- 规则列表预览 -->
          <div>
            <label class="block text-sm font-medium mb-2 text-slate-700 dark:text-slate-300">
              规则列表（按顺序匹配，匹配成功即停止）
              <span class="text-slate-400 font-normal">（共 {{ rules.length }} 条）</span>
            </label>
            <div v-if="rules.length === 0" class="text-sm text-slate-400 py-2">暂无规则，请先在设置中添加规则并保存</div>
            <div v-for="(r, i) in rules" :key="i" class="flex items-center gap-2 py-1.5 text-sm">
              <span class="w-5 h-5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 flex items-center justify-center text-xs font-medium shrink-0">{{ i + 1 }}</span>
              <span class="font-medium text-slate-700 dark:text-slate-200 min-w-[5rem]">{{ r.name || '未命名' }}</span>
              <span class="text-xs font-mono text-slate-500 dark:text-slate-400 truncate">{{ r.pattern }}</span>
            </div>
          </div>

          <button
            @click="runTest"
            :disabled="!selectedL2 || rules.length === 0"
            class="h-9 px-4 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium transition"
          >执行测试</button>

          <!-- 结果 -->
          <div v-if="loading" class="text-sm text-slate-500 text-center py-8 animate-pulse">测试执行中...</div>

          <div v-if="error" class="text-sm text-red-500 bg-red-50 dark:bg-red-500/10 rounded-lg p-3">{{ error }}</div>

          <div v-if="results.length > 0" class="overflow-auto border border-slate-200 dark:border-slate-700 rounded-lg max-h-96">
            <table class="w-full text-sm">
              <thead>
                <tr class="bg-slate-50 dark:bg-slate-800/60 text-left">
                  <th class="px-3 py-2 text-slate-600 dark:text-slate-300 font-medium sticky left-0 bg-slate-50 dark:bg-slate-800/60">文件名</th>
                  <th class="px-3 py-2 text-slate-600 dark:text-slate-300 font-medium">匹配规则</th>
                  <th v-for="field in resultFields" :key="field" class="px-3 py-2 text-slate-600 dark:text-slate-300 font-medium font-mono">{{ field }}</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="r in results"
                  :key="r.file_name"
                  :class="['border-t border-slate-100 dark:border-slate-800', r.ext ? 'bg-green-50/50 dark:bg-green-500/5' : '']"
                >
                  <td class="px-3 py-2 text-slate-700 dark:text-slate-200 font-mono text-xs sticky left-0 bg-white dark:bg-slate-900">{{ r.file_name }}</td>
                  <td class="px-3 py-2">
                    <span v-if="r.matched_rule" class="inline-block px-2 py-0.5 rounded text-xs font-medium bg-indigo-100 dark:bg-indigo-500/20 text-indigo-700 dark:text-indigo-300">
                      {{ r.matched_rule }}
                    </span>
                    <span v-else class="text-slate-400">—</span>
                  </td>
                  <td v-for="field in resultFields" :key="field" class="px-3 py-2 text-slate-700 dark:text-slate-200 text-xs">
                    {{ r.ext?.[field] || '—' }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import axios from 'axios'

const props = defineProps<{
  open: boolean
  rules: { name: string; pattern: string }[]
}>()
const emit = defineEmits<{ (e: 'close'): void }>()

// 级联选择状态
const roots = ref<{ id: string; name: string; path: string }[]>([])
const l1Dirs = ref<{ id: string; name: string; path: string }[]>([])
const l2Dirs = ref<{ id: string; name: string; path: string }[]>([])
const selectedRoot = ref('')
const selectedL1 = ref('')
const selectedL2 = ref('')

// 结果状态
const results = ref<any[]>([])
const resultFields = ref<string[]>([])
const loading = ref(false)
const error = ref('')

// 目录加载函数
async function loadRoots() {
  try {
    const { data } = await axios.get('/api/roots')
    roots.value = data
  } catch {
    /* ignore */
  }
}

async function onRootChange() {
  selectedL1.value = ''
  selectedL2.value = ''
  l1Dirs.value = []
  l2Dirs.value = []
  if (!selectedRoot.value) return
  try {
    const root = roots.value.find(r => r.path === selectedRoot.value)
    if (root) {
      const { data } = await axios.get(`/api/roots/${root.id}/l1`)
      l1Dirs.value = data
    }
  } catch {
    /* ignore */
  }
}

async function onL1Change() {
  selectedL2.value = ''
  l2Dirs.value = []
  if (!selectedL1.value) return
  try {
    const l1 = l1Dirs.value.find(d => d.path === selectedL1.value)
    if (l1) {
      const { data } = await axios.get(`/api/l1/${l1.id}/l2`)
      l2Dirs.value = data
    }
  } catch {
    /* ignore */
  }
}

function onL2Change() {
  // 选中 L2 后即可执行测试
}

async function runTest() {
  if (!selectedL2.value || props.rules.length === 0) return
  loading.value = true
  error.value = ''
  results.value = []
  resultFields.value = []
  try {
    const { data } = await axios.post('/api/parse-rules/test', {
      rules: props.rules,
      source_dir: selectedL2.value,
    })
    results.value = data.results || []
    resultFields.value = data.field_names || []
  } catch (e: any) {
    error.value = e.response?.data?.detail || e.message || '测试失败'
  } finally {
    loading.value = false
  }
}

// 打开时加载根目录列表
watch(() => props.open, async (isOpen) => {
  if (isOpen) {
    await loadRoots()
  }
}, { immediate: true })
</script>
