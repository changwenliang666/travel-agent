<template>
  <div class="shell">
    <header class="topbar">
      <div class="brand">漫游<span>记</span></div>
      <nav class="nav"><router-link to="/">返回对话</router-link></nav>
    </header>
    <form class="page" @submit.prevent="save">
      <h1>出行偏好</h1>
      <p>这些会带到之后的每一段行程里。</p>
      <el-form label-position="top">
        <el-form-item label="常住城市"><el-input v-model="form.home_city" /></el-form-item>
        <el-form-item label="节奏"><el-input v-model="form.pace" placeholder="慢 / 适中 / 紧凑" /></el-form-item>
        <el-form-item label="预算"><el-input v-model="form.budget" /></el-form-item>
        <el-form-item label="饮食"><el-input v-model="form.diet" /></el-form-item>
        <el-form-item label="早起"><el-switch v-model="form.early_start" /></el-form-item>
      </el-form>
      <el-button type="primary" round native-type="submit">保存</el-button>
      <span v-if="saved" style="margin-left: 12px; color: #0f6e6b">已保存</span>
    </form>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { api } from '../api'

const form = reactive({ home_city: '', pace: '', budget: '', diet: '', early_start: false })
const saved = ref(false)

onMounted(async () => {
  Object.assign(form, await api.preferences())
})

async function save() {
  await api.savePreferences(form)
  saved.value = true
}
</script>
