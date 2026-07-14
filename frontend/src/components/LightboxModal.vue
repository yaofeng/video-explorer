<template>
  <div v-if="video" class="fixed inset-0 bg-black/80 flex items-center justify-center z-50" @click.self="$emit('close')">
    <div class="relative max-w-[90vw] max-h-[90vh]">
      <button @click="$emit('close')" class="absolute top-2 right-2 text-white text-2xl bg-black/50 rounded-full w-8 h-8 flex items-center justify-center">×</button>
      <img :src="`/api/thumb/${video.video_id}?full=1`" class="max-w-full max-h-full object-contain" />
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  video: any | null
}>()
defineEmits<{
  (e: 'close'): void
}>()
</script>
