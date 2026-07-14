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
import { onMounted } from 'vue'
import { useConfigStore } from '../stores/config'
import { useRouter } from 'vue-router'

const config = useConfigStore()
const router = useRouter()

onMounted(() => config.fetch())

async function save() {
  await config.update()
  router.push('/')
}
</script>
