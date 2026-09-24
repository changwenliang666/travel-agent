<template>
  <div class="shell">
    <header class="topbar">
      <div class="brand">漫游<span>记</span></div>
      <nav class="nav"><router-link to="/">返回对话</router-link></nav>
    </header>
    <section class="page">
      <h1>调用记录</h1>
      <el-input v-model="traceId" placeholder="trace_id" />
      <div style="height: 12px"></div>
      <el-button round @click="loadTrace">查看步骤</el-button>
      <pre v-if="trace">{{ trace }}</pre>
      <h2>用量</h2>
      <el-input v-model="userId" placeholder="用户 id，可空" />
      <el-input v-model="start" placeholder="开始时间 2026-01-01T00:00:00" />
      <el-input v-model="end" placeholder="结束时间 2026-12-31T23:59:59" />
      <div style="height: 12px"></div>
      <el-button round type="primary" @click="loadUsage">汇总</el-button>
      <pre v-if="usage">{{ usage }}</pre>
      <p v-if="error" style="color: #d46a4c">{{ error }}</p>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { api } from '../api'

const traceId = ref('')
const trace = ref('')
const userId = ref('')
const start = ref('')
const end = ref('')
const usage = ref('')
const error = ref('')

async function loadTrace() {
  error.value = ''
  try {
    trace.value = JSON.stringify(await api.trace(traceId.value), null, 2)
  } catch (err) {
    error.value = '无法查看 trace'
  }
}

async function loadUsage() {
  error.value = ''
  try {
    usage.value = JSON.stringify(await api.usage(userId.value, start.value, end.value), null, 2)
  } catch (err) {
    error.value = '无法查看用量'
  }
}
</script>
