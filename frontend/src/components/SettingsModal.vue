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
      class="fixed inset-0 bg-slate-900/50 backdrop-blur-sm flex items-start justify-center z-40 pt-16 px-4"
      @click.self="$emit('close')"
    >
      <transition
        enter-active-class="transition duration-200 ease-out"
        enter-from-class="opacity-0 translate-y-2 scale-95"
        enter-to-class="opacity-100 translate-y-0 scale-100"
      >
        <div v-if="open" class="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl ring-1 ring-slate-200 dark:ring-slate-800 w-full max-w-2xl max-h-[80vh] overflow-auto">
          <!-- 头部 -->
          <div class="flex items-center justify-between px-5 py-4 border-b border-slate-200 dark:border-slate-800">
            <h2 class="text-base font-semibold text-slate-900 dark:text-slate-100">设置</h2>
            <button
              @click="$emit('close')"
              class="text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 w-8 h-8 flex items-center justify-center rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition"
            >
              <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M18 6 6 18M6 6l12 12"/></svg>
            </button>
          </div>

          <!-- 内容 -->
          <div class="p-5 space-y-5">
            <div>
              <label class="block text-sm font-medium mb-2 text-slate-700 dark:text-slate-300">视频目录列表</label>
              <div v-for="(path, i) in config.video_path_list" :key="i" class="flex gap-2 mb-2">
                <input
                  v-model="config.video_path_list[i]"
                  type="text"
                  class="flex-1 h-9 border border-slate-300 dark:border-slate-700 rounded-lg px-3 text-sm bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-500 transition"
                />
                <button
                  @click="buildIndex(path, i)"
                  :disabled="building[i]"
                  :title="building[i] ? '构建中...' : '构建该视频库索引'"
                  class="h-9 w-9 shrink-0 bg-amber-500 text-white rounded-lg hover:bg-amber-600 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center transition"
                >
                  <svg v-if="!building[i]" xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>
                  </svg>
                  <svg v-else xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M21 12a9 9 0 1 1-6.219-8.56" stroke-linecap="round"/>
                  </svg>
                </button>
                <button
                  @click="config.video_path_list.splice(i, 1)"
                  class="h-9 w-9 shrink-0 bg-slate-100 dark:bg-slate-800 text-slate-500 hover:bg-red-500 hover:text-white rounded-lg flex items-center justify-center transition"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M18 6 6 18M6 6l12 12"/></svg>
                </button>
              </div>
              <button
                @click="config.video_path_list.push('')"
                class="h-9 px-3 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-700 text-sm font-medium transition"
              >+ 添加目录</button>
            </div>

            <div class="grid grid-cols-2 gap-4">
              <div>
                <label class="block text-sm font-medium mb-2 text-slate-700 dark:text-slate-300">每页视频数 <span class="text-slate-400 font-normal">(0=不分页)</span></label>
                <input
                  v-model.number="config.page_size"
                  type="number"
                  class="w-full h-9 border border-slate-300 dark:border-slate-700 rounded-lg px-3 text-sm bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-500 transition"
                />
              </div>
              <div>
                <label class="block text-sm font-medium mb-2 text-slate-700 dark:text-slate-300">每行视频数</label>
                <input
                  v-model.number="config.column_size"
                  type="number"
                  class="w-full h-9 border border-slate-300 dark:border-slate-700 rounded-lg px-3 text-sm bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-500 transition"
                />
              </div>
            </div>

            <!-- 文件名解析规则 -->
            <div>
              <label class="block text-sm font-medium mb-2 text-slate-700 dark:text-slate-300">文件名解析规则</label>
              <div v-for="(rule, i) in config.parse_rules" :key="i" class="flex gap-2 mb-2 items-start">
                <div class="flex-1 grid grid-cols-[1fr_2fr] gap-2">
                  <input
                    v-model="rule.name"
                    type="text"
                    placeholder="规则名（如 JAV）"
                    class="h-9 border border-slate-300 dark:border-slate-700 rounded-lg px-3 text-sm bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-500 transition"
                  />
                  <input
                    v-model="rule.pattern"
                    type="text"
                    placeholder="正则，如 ^(?P&lt;code&gt;[A-Z]+-\d+)"
                    class="h-9 border border-slate-300 dark:border-slate-700 rounded-lg px-3 text-sm bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-500 transition font-mono text-[13px]"
                  />
                </div>
                <button
                  @click="config.removeRule(i)"
                  class="h-9 w-9 shrink-0 bg-slate-100 dark:bg-slate-800 text-slate-500 hover:bg-red-500 hover:text-white rounded-lg flex items-center justify-center transition"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M18 6 6 18M6 6l12 12"/></svg>
                </button>
              </div>
              <button
                @click="config.addRule()"
                class="h-9 px-3 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-700 text-sm font-medium transition"
              >+ 添加规则</button>
            </div>
          </div>

          <!-- 底部 -->
          <div class="flex justify-end gap-2 px-5 py-4 border-t border-slate-200 dark:border-slate-800">
            <button
              @click="$emit('close')"
              class="h-9 px-4 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-700 text-sm font-medium transition"
            >取消</button>
            <button
              @click="save"
              class="h-9 px-4 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 shadow-sm shadow-indigo-600/30 text-sm font-medium transition"
            >保存</button>
          </div>
        </div>
      </transition>
    </div>
  </transition>
</template>

<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import axios from 'axios'
import { useConfigStore } from '../stores/config'
import { useTaskStore } from '../stores/task'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ (e: 'close'): void }>()

const config = useConfigStore()
const taskStore = useTaskStore()

const building = reactive<Record<number, boolean>>({})
const pathToId = ref<Record<string, string>>({})

watch(() => props.open, async (isOpen) => {
  if (!isOpen) return
  await config.fetch()
  try {
    const { data } = await axios.get('/api/roots')
    const map: Record<string, string> = {}
    for (const r of data) {
      map[r.path] = r.id
      map[r.name] = r.id
    }
    pathToId.value = map
  } catch {
    /* ignore */
  }
}, { immediate: true })

async function save() {
  await config.update()
  emit('close')
}

async function buildIndex(path: string, i: number) {
  if (!path) return
  const rootId = pathToId.value[path] || pathToId.value[path.split('/').filter(Boolean).pop() || '']
  if (!rootId) {
    alert('未找到该目录的根 ID，请先保存配置')
    return
  }
  building[i] = true
  try {
    await taskStore.buildIndex(rootId)
  } finally {
    setTimeout(() => { building[i] = false }, 2000)
  }
}
</script>
