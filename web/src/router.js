import { createRouter, createWebHashHistory } from 'vue-router'

import Home from '@/views/Home.vue'
import Holdings from '@/views/Holdings.vue'
import Ranking from '@/views/Ranking.vue'
import Sectors from '@/views/Sectors.vue'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', name: 'home', component: Home },
    { path: '/holdings', name: 'holdings', component: Holdings },
    { path: '/ranking', name: 'ranking', component: Ranking },
    { path: '/sectors', name: 'sectors', component: Sectors },
  ],
})

export default router
