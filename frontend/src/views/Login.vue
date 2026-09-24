<template>
  <div class="login-wrap">
    <form class="login-card" @submit.prevent="submit">
      <h1>出门之前，先把日子排好</h1>
      <p>告诉我想去哪里、玩几天。信息不够时，我会先问你。</p>
      <el-input v-model="username" placeholder="用户名" />
      <div style="height: 12px"></div>
      <el-input v-model="password" type="password" placeholder="密码" show-password />
      <div style="height: 16px"></div>
      <el-button type="primary" native-type="submit" round :loading="loading">进入</el-button>
      <p v-if="error" style="color: #d46a4c">{{ error }}</p>
    </form>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'

const router = useRouter()
const username = ref('admin')
const password = ref('')
const loading = ref(false)
const error = ref('')

async function submit() {
  loading.value = true
  error.value = ''
  try {
    await api.login(username.value, password.value)
    router.push('/')
  } catch {
    error.value = '登录失败，请检查用户名和密码'
  } finally {
    loading.value = false
  }
}
</script>
