<template>
  <div class="flex flex-col h-screen">
    <TopMenu :roots="browser.roots" :selected="browser.selectedRootId" @select="onSelectRoot" />
    <div class="flex flex-1 overflow-hidden">
      <SideMenu :dirs="browser.l2Dirs" :selected="browser.selectedL2Id" @select="onSelectL2" />
      <VideoGrid :groups="browser.groups" :columnSize="config.column_size" @showLightbox="showLightbox" />
    </div>
    <LightboxModal :video="lightboxVideo" @close="lightboxVideo = null" />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useBrowserStore } from '../stores/browser'
import { useConfigStore } from '../stores/config'
import { useScanPolling } from '../composables/useScanPolling'
import TopMenu from '../components/TopMenu.vue'
import SideMenu from '../components/SideMenu.vue'
import VideoGrid from '../components/VideoGrid.vue'
import LightboxModal from '../components/LightboxModal.vue'

const browser = useBrowserStore()
const config = useConfigStore()
const lightboxVideo = ref(null)
useScanPolling()

onMounted(async () => {
  await config.fetch()
  await browser.fetchRoots()
})

async function onSelectRoot(id: string) {
  await browser.selectRoot(id)
}

async function onSelectL2(id: string) {
  await browser.selectL2(id)
}

function showLightbox(video: any) {
  lightboxVideo.value = video
}
</script>
