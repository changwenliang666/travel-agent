import { createRouter, createWebHistory } from 'vue-router'
import Login from './views/Login.vue'
import Chat from './views/Chat.vue'
import Preferences from './views/Preferences.vue'
import Admin from './views/Admin.vue'
import { api } from './api'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: Login },
    { path: '/', component: Chat },
    { path: '/preferences', component: Preferences },
    { path: '/admin', component: Admin },
  ],
})

router.beforeEach(async (to) => {
  if (to.path === '/login') {
    return true
  }
  try {
    const me = await api.me()
    if (to.path === '/admin' && me.role !== 'admin') {
      return '/'
    }
    return true
  } catch {
    return '/login'
  }
})
