import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

const STORAGE_KEY = 'novamind_chat_v1'
const LEGACY_STORAGE_KEY_HISTORY = 'chat_history'
const LEGACY_STORAGE_KEY_SESSION = 'chat_session_id'

function safeJsonParse(value) {
  try {
    return JSON.parse(value)
  } catch {
    return null
  }
}

function newId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID()
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function makeTitle(text) {
  const trimmed = (text || '').trim()
  if (!trimmed) return 'New chat'
  return trimmed.length > 40 ? `${trimmed.slice(0, 40)}…` : trimmed
}

export const useChatStore = defineStore('chat', () => {
  const chats = ref([])
  const activeChatId = ref(null)

  const activeChat = computed(() => chats.value.find((c) => c.id === activeChatId.value) || null)

  const persist = () => {
    try {
      sessionStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          chats: chats.value,
          activeChatId: activeChatId.value,
        })
      )
    } catch (e) {
      console.warn('[chat store] persist failed:', e)
    }
  }

  const load = () => {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    const parsed = raw ? safeJsonParse(raw) : null

    if (parsed && Array.isArray(parsed.chats)) {
      chats.value = parsed.chats
      activeChatId.value = parsed.activeChatId || (parsed.chats[0] && parsed.chats[0].id) || null
      return true
    }

    return false
  }

  const migrateLegacyIfNeeded = () => {
    const legacyHistoryRaw = sessionStorage.getItem(LEGACY_STORAGE_KEY_HISTORY)
    const legacySessionId = sessionStorage.getItem(LEGACY_STORAGE_KEY_SESSION)
    if (!legacyHistoryRaw && !legacySessionId) return false

    const legacyHistory = safeJsonParse(legacyHistoryRaw || 'null')
    const messages = Array.isArray(legacyHistory) && legacyHistory.length ? legacyHistory : null

    const id = newId()
    const createdAt = new Date().toISOString()
    chats.value = [
      {
        id,
        title: 'Chat',
        sessionId: legacySessionId || null,
        messages:
          messages ||
          [
            {
              role: 'bot',
              text: 'Hello! How can I help you manage your emails today?',
              emails: [],
            },
          ],
        createdAt,
        updatedAt: createdAt,
      },
    ]
    activeChatId.value = id

    sessionStorage.removeItem(LEGACY_STORAGE_KEY_HISTORY)
    sessionStorage.removeItem(LEGACY_STORAGE_KEY_SESSION)
    persist()
    return true
  }

  const initialize = () => {
    if (load()) return
    if (migrateLegacyIfNeeded()) return
    createChat()
  }

  const createChat = () => {
    const id = newId()
    const now = new Date().toISOString()

    const chat = {
      id,
      title: 'New chat',
      sessionId: null,
      messages: [
        {
          role: 'bot',
          text: 'Hello! How can I help you manage your emails today?',
          emails: [],
        },
      ],
      createdAt: now,
      updatedAt: now,
    }

    chats.value = [chat, ...chats.value]
    activeChatId.value = id
    persist()
    return chat
  }

  const deleteChat = (chatId) => {
    const remaining = chats.value.filter((c) => c.id !== chatId)
    chats.value = remaining

    if (!remaining.length) {
      createChat()
      return
    }

    if (activeChatId.value === chatId) {
      activeChatId.value = remaining[0].id
    }

    persist()
  }

  const setActiveChat = (chatId) => {
    if (chatId === activeChatId.value) return
    if (!chats.value.some((c) => c.id === chatId)) return
    activeChatId.value = chatId
    persist()
  }

  const appendMessage = (chatId, message) => {
    const chat = chats.value.find((c) => c.id === chatId)
    if (!chat) return

    chat.messages.push(message)
    chat.updatedAt = new Date().toISOString()

    if (message.role === 'user' && chat.title === 'New chat') {
      chat.title = makeTitle(message.text)
    }

    persist()
  }

  const setSessionId = (chatId, sessionId) => {
    const chat = chats.value.find((c) => c.id === chatId)
    if (!chat) return
    chat.sessionId = sessionId
    chat.updatedAt = new Date().toISOString()
    persist()
  }

  const clearAll = () => {
    chats.value = []
    activeChatId.value = null
    sessionStorage.removeItem(STORAGE_KEY)
    sessionStorage.removeItem(LEGACY_STORAGE_KEY_HISTORY)
    sessionStorage.removeItem(LEGACY_STORAGE_KEY_SESSION)
    createChat()
  }

  initialize()

  return {
    chats,
    activeChatId,
    activeChat,
    createChat,
    deleteChat,
    setActiveChat,
    appendMessage,
    setSessionId,
    clearAll,
  }
})

