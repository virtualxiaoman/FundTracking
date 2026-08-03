import { createRouter, createWebHashHistory } from 'vue-router'

import Home from '@/views/Home.vue'
import Holdings from '@/views/Holdings.vue'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', name: 'home', component: Home },
    { path: '/holdings', name: 'holdings', component: Holdings },
  ],
})

export default router
