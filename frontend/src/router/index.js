import { createRouter, createWebHistory } from 'vue-router'
import TodayBoard from '../views/TodayBoard.vue'

const routes = [
  { path: '/', name: 'today', component: TodayBoard, meta: { title: '📊 今日看板' } },
  { path: '/self', name: 'self', component: () => import('../views/SelfStock.vue'), meta: { title: '⭐ 自选股分析' } },
  { path: '/history', name: 'history', component: () => import('../views/History.vue'), meta: { title: '📅 历史记录' } },
  { path: '/accuracy', name: 'accuracy', component: () => import('../views/Accuracy.vue'), meta: { title: '📈 准确率看板' } },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
