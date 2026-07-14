import { createRouter, createWebHistory } from 'vue-router'
import BrowserView from '../views/BrowserView.vue'
import SettingsView from '../views/SettingsView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: BrowserView },
    { path: '/settings', component: SettingsView },
  ],
})

export default router
