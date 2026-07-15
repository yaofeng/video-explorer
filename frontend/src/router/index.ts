import { createRouter, createWebHistory } from 'vue-router'
import BrowserView from '../views/BrowserView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: BrowserView },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

export default router
