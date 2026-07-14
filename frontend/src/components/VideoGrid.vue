<template>
  <div class="flex-1 p-4 overflow-auto">
    <div v-for="group in groups" :key="group.name" class="mb-6">
      <h3 class="text-lg font-semibold mb-2 text-gray-900 dark:text-gray-100">{{ group.name }}</h3>
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
