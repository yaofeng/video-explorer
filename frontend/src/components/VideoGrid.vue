<template>
  <div class="flex-1 overflow-auto p-6 bg-slate-50 dark:bg-slate-950">
    <div v-for="group in groups" :key="group.name" class="mb-8">
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
import VideoCard from './VideoCard.vue'

defineProps<{
  groups: any[]
  columnSize: number
}>()
defineEmits<{
  (e: 'showLightbox', video: any): void
}>()
</script>
