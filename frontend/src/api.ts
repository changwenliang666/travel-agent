export type Me = { id: number; username: string; role: string }
export type PlanItem = { time: string; name: string; note: string }
export type PlanDay = { day: number; title: string; weather: string; items: PlanItem[] }
export type Plan = {
  destination: string
  days_count: number
  date_start: string
  days: PlanDay[]
  sources: { title: string; url: string }[]
}

async function request(path: string, options: RequestInit = {}) {
  const response = await fetch(path, { credentials: 'include', headers: { 'Content-Type': 'application/json' }, ...options })
  if (!response.ok) {
    const text = await response.text()
    throw new Error(text || '请求失败')
  }
  return response.json()
}

export const api = {
  me: () => request('/api/auth/me') as Promise<Me>,
  login: (username: string, password: string) => request('/api/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) }),
  logout: () => request('/api/auth/logout', { method: 'POST' }),
  conversations: () => request('/api/conversations/list') as Promise<{ id: number; title: string }[]>,
  createConversation: () => request('/api/conversations/create', { method: 'POST' }) as Promise<{ id: number; title: string }>,
  conversation: (id: number) => request('/api/conversations/' + id + '/detail'),
  preferences: () => request('/api/preferences/current'),
  savePreferences: (body: object) => request('/api/preferences/save', { method: 'PUT', body: JSON.stringify(body) }),
  trace: (traceId: string) => request('/api/admin/traces/' + traceId),
  usage: (userId: string, start: string, end: string) => {
    const query = new URLSearchParams()
    if (userId) query.set('user_id', userId)
    if (start) query.set('start', start)
    if (end) query.set('end', end)
    return request('/api/admin/usage/summary?' + query.toString())
  },
}

export async function sendMessage(id: number, text: string, onEvent: (event: string, data: any) => void) {
  const response = await fetch('/api/conversations/' + id + '/messages/send', {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  })
  if (!response.ok || !response.body) {
    throw new Error('发送失败')
  }
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const chunk = await reader.read()
    if (chunk.done) break
    buffer += decoder.decode(chunk.value, { stream: true })
    const parts = buffer.split('\n\n')
    buffer = parts.pop() || ''
    for (const part of parts) {
      const lines = part.split('\n')
      let event = 'message'
      let data = ''
      for (const line of lines) {
        if (line.startsWith('event: ')) event = line.slice(7)
        if (line.startsWith('data: ')) data = line.slice(6)
      }
      if (data) onEvent(event, JSON.parse(data))
    }
  }
}
