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
      v-if="video"
      class="fixed inset-0 bg-slate-950/85 backdrop-blur-sm flex items-center justify-center z-50 p-8"
      @click.self="$emit('close')"
    >
      <div class="relative max-w-[90vw] max-h-[90vh]">
        <button
          @click="$emit('close')"
          class="absolute -top-3 -right-3 z-10 w-9 h-9 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 rounded-full shadow-lg flex items-center justify-center hover:scale-110 transition"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M18 6 6 18M6 6l12 12"/></svg>
        </button>
        <img
          :src="`/api/thumb/${video.video_id}`"
          class="max-w-full max-h-full object-contain rounded-lg shadow-2xl"
        />
      </div>
    </div>
  </transition>
</template>

<script setup lang="ts">
defineProps<{
  video: any | null
}>()
defineEmits<{
  (e: 'close'): void
}>()
</script>
