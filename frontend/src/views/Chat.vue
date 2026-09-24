<template>
  <div class="shell">
    <header class="topbar">
      <div class="brand">漫游<span>记</span></div>
      <nav class="nav">
        <router-link to="/">对话</router-link>
        <router-link to="/preferences">偏好</router-link>
        <router-link v-if="me?.role === 'admin'" to="/admin">记录</router-link>
        <a href="#" @click.prevent="exit">退出</a>
      </nav>
    </header>
    <div class="chat-layout">
      <aside class="side">
        <el-button type="primary" round style="width: 100%; margin-bottom: 12px" @click="create">新对话</el-button>
        <button v-for="item in conversations" :key="item.id" class="conv" :class="{ active: item.id === currentId }"
          @click="open(item.id)">
          {{ item.title }}
        </button>
      </aside>
      <section class="stage">
        <div ref="messagePane" class="messages">
          <div v-for="(item, index) in messages" :key="index" class="bubble" :class="item.role">
            <div v-if="item.role === 'assistant' && item.status && !item.content" class="status">{{ item.status }}</div>
            <div v-else-if="item.role === 'assistant'" v-html="render(item.content)"></div>
            <div v-else>{{ item.content }}</div>
            <ItineraryCard v-if="item.plan" :plan="item.plan" />
          </div>
        </div>
        <form class="composer" @submit.prevent="send">
          <textarea v-model="text" rows="2" placeholder="例如：帮我规划杭州三天，节奏慢一点" @keydown="onComposerKey"></textarea>
          <el-button type="primary" round native-type="submit" :loading="sending">发</el-button>
        </form>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onMounted, ref } from 'vue'
import MarkdownIt from 'markdown-it'
import { useRouter } from 'vue-router'
import { api, sendMessage, type Me, type Plan } from '../api'
import ItineraryCard from '../components/ItineraryCard.vue'

const md = new MarkdownIt({ html: false, linkify: true })
const router = useRouter()
const me = ref<Me | null>(null)
const conversations = ref<{ id: number; title: string }[]>([])
const currentId = ref<number | null>(null)
const messages = ref<{ role: string; content: string; status?: string; plan?: Plan | null }[]>([])
const text = ref('')
const sending = ref(false)
const messagePane = ref<HTMLElement | null>(null)

function render(content: string) {
  return md.render(content || '')
}

function scrollMessages() {
  nextTick(() => {
    const pane = messagePane.value
    if (pane) pane.scrollTop = pane.scrollHeight
  })
}

function onComposerKey(event: KeyboardEvent) {
  if (event.key !== 'Enter' || event.isComposing) return
  if (event.shiftKey) {
    event.preventDefault()
    const el = event.target as HTMLTextAreaElement
    const start = el.selectionStart ?? text.value.length
    const end = el.selectionEnd ?? text.value.length
    text.value = text.value.slice(0, start) + '\n' + text.value.slice(end)
    nextTick(() => {
      el.selectionStart = el.selectionEnd = start + 1
    })
    return
  }
  event.preventDefault()
  send()
}

async function loadList() {
  conversations.value = await api.conversations()
}

async function open(id: number) {
  currentId.value = id
  const data = await api.conversation(id)
  messages.value = data.messages.map((item: { role: string; content: string }, index: number) => ({
    role: item.role,
    content: item.content,
    plan: index === data.messages.length - 1 ? data.plan : null,
  }))
}

async function create() {
  const row = await api.createConversation()
  await loadList()
  await open(row.id)
}

async function send() {
  if (!text.value.trim()) return
  if (currentId.value === null) await create()
  const id = currentId.value
  if (id === null) return
  const content = text.value
  text.value = ''
  messages.value.push({ role: 'user', content })
  const reply = { role: 'assistant', content: '', status: '正在搜索...', plan: null as Plan | null }
  messages.value.push(reply)
  const index = messages.value.length - 1
  sending.value = true
  scrollMessages()
  try {
    await sendMessage(id, content, (event, data) => {
      const live = messages.value[index]
      if (event === 'progress' && !live.content) {
        live.status = data.text;
      }

      if (event === 'delta' && data.text) {
        live.status = ''
        live.content += data.text
      }
      if (event === 'plan') live.plan = data
      if (event === 'done') {
        live.status = ''
        live.content = data.reply || live.content
      }
      if (event === 'error') {
        live.status = ''
        live.content = data.message
      }
      scrollMessages()
    })
    await loadList()
  } finally {
    sending.value = false
  }
}

async function exit() {
  await api.logout()
  router.push('/login')
}

onMounted(async () => {
  me.value = await api.me()
  await loadList()
  if (conversations.value.length) await open(conversations.value[0].id)
})
</script>
