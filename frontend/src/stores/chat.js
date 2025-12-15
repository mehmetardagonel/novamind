import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { useAuthStore } from './auth'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001'
const normalizedBase = API_BASE_URL.endsWith('/') ? API_BASE_URL.slice(0, -1) : API_BASE_URL
const CHAT_API_URL = `${normalizedBase}/chat/sessions`

function newId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID()
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function makeTitle(text) {
  const trimmed = (text || '').trim()
  if (!trimmed) return 'New chat'
  return trimmed.length > 40 ? `${trimmed.slice(0, 40)}...` : trimmed
}

export const useChatStore = defineStore('chat', () => {
  const chats = ref([])
  const activeChatId = ref(null)
  const isLoading = ref(false)
  const isInitialized = ref(false)

  const activeChat = computed(() => chats.value.find((c) => c.id === activeChatId.value) || null)

  // Get auth headers for API calls
  const getHeaders = () => {
    const authStore = useAuthStore()
    return {
      'Content-Type': 'application/json',
      'X-User-Id': authStore.user?.id || ''
    }
  }

  // Load all chat sessions from database
  const loadFromDatabase = async () => {
    if (isLoading.value) return false
    isLoading.value = true

    try {
      const response = await fetch(CHAT_API_URL, {
        method: 'GET',
        headers: getHeaders()
      })

      if (!response.ok) {
        console.error('Failed to load chat sessions:', response.status)
        return false
      }

      const sessions = await response.json()

      // Convert API format to local format
      chats.value = sessions.map(s => ({
        id: s.id,
        title: s.title,
        sessionId: s.backend_session_id, // Backend ChatService session ID
        messages: [], // Will be loaded on demand
        createdAt: s.created_at,
        updatedAt: s.updated_at
      }))

      // Set active chat to first one if exists
      if (chats.value.length > 0 && !activeChatId.value) {
        activeChatId.value = chats.value[0].id
      }

      isInitialized.value = true
      return true
    } catch (e) {
      console.error('[chat store] loadFromDatabase failed:', e)
      return false
    } finally {
      isLoading.value = false
    }
  }

  // Load messages for a specific chat session
  const loadChatMessages = async (chatId) => {
    try {
      const response = await fetch(`${CHAT_API_URL}/${chatId}`, {
        method: 'GET',
        headers: getHeaders()
      })

      if (!response.ok) {
        console.error('Failed to load chat messages:', response.status)
        return false
      }

      const sessionData = await response.json()
      const chat = chats.value.find(c => c.id === chatId)

      if (chat) {
        // Convert API messages to local format
        chat.messages = sessionData.messages.map(m => ({
          role: m.role,
          text: m.text,
          emails: m.emails
        }))
        chat.sessionId = sessionData.backend_session_id
      }

      return true
    } catch (e) {
      console.error('[chat store] loadChatMessages failed:', e)
      return false
    }
  }

  // Create a new chat session in database
  const createChat = async () => {
    const tempId = newId()
    const now = new Date().toISOString()

    // Add optimistically with welcome message
    const newChat = {
      id: tempId,
      title: 'New chat',
      sessionId: null,
      messages: [
        {
          role: 'bot',
          text: 'Hello! How can I help you manage your emails today?',
          emails: null
        }
      ],
      createdAt: now,
      updatedAt: now
    }

    chats.value = [newChat, ...chats.value]
    activeChatId.value = tempId

    try {
      // Create in database
      const response = await fetch(CHAT_API_URL, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify({ title: 'New chat' })
      })

      if (response.ok) {
        const created = await response.json()
        // Update local chat with real ID
        newChat.id = created.id
        newChat.createdAt = created.created_at
        newChat.updatedAt = created.updated_at
        activeChatId.value = created.id

        // Add welcome message to database
        await addMessageToDatabase(created.id, {
          role: 'bot',
          text: 'Hello! How can I help you manage your emails today?',
          emails: null
        })
      }
    } catch (e) {
      console.error('[chat store] createChat API call failed:', e)
      // Keep local chat even if API fails
    }

    return newChat
  }

  // Add message to database (async, don't block UI)
  const addMessageToDatabase = async (chatId, message) => {
    try {
      await fetch(`${CHAT_API_URL}/${chatId}/messages`, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify({
          role: message.role,
          text: message.text,
          emails: message.emails
        })
      })
    } catch (e) {
      console.error('[chat store] addMessageToDatabase failed:', e)
    }
  }

  // Delete a chat session
  const deleteChat = async (chatId) => {
    const remaining = chats.value.filter((c) => c.id !== chatId)
    chats.value = remaining

    // Try to delete from database
    try {
      await fetch(`${CHAT_API_URL}/${chatId}`, {
        method: 'DELETE',
        headers: getHeaders()
      })
    } catch (e) {
      console.error('[chat store] deleteChat API call failed:', e)
    }

    if (!remaining.length) {
      await createChat()
      return
    }

    if (activeChatId.value === chatId) {
      activeChatId.value = remaining[0].id
    }
  }

  // Set active chat and load its messages if needed
  const setActiveChat = async (chatId) => {
    if (chatId === activeChatId.value) return
    if (!chats.value.some((c) => c.id === chatId)) return

    activeChatId.value = chatId

    // Load messages if not loaded yet
    const chat = chats.value.find(c => c.id === chatId)
    if (chat && chat.messages.length === 0) {
      await loadChatMessages(chatId)
    }
  }

  // Append message locally and save to database
  const appendMessage = (chatId, message) => {
    const chat = chats.value.find((c) => c.id === chatId)
    if (!chat) return

    chat.messages.push(message)
    chat.updatedAt = new Date().toISOString()

    // Update title if first user message
    if (message.role === 'user' && chat.title === 'New chat') {
      chat.title = makeTitle(message.text)
      // Update title in database
      updateSessionTitle(chatId, chat.title)
    }

    // Save message to database (async, don't block)
    addMessageToDatabase(chatId, message)
  }

  // Update session title in database
  const updateSessionTitle = async (chatId, title) => {
    try {
      await fetch(`${CHAT_API_URL}/${chatId}`, {
        method: 'PATCH',
        headers: getHeaders(),
        body: JSON.stringify({ title })
      })
    } catch (e) {
      console.error('[chat store] updateSessionTitle failed:', e)
    }
  }

  // Set backend session ID
  const setSessionId = async (chatId, sessionId) => {
    const chat = chats.value.find((c) => c.id === chatId)
    if (!chat) return

    chat.sessionId = sessionId
    chat.updatedAt = new Date().toISOString()

    // Update in database
    try {
      await fetch(`${CHAT_API_URL}/${chatId}`, {
        method: 'PATCH',
        headers: getHeaders(),
        body: JSON.stringify({ backend_session_id: sessionId })
      })
    } catch (e) {
      console.error('[chat store] setSessionId API call failed:', e)
    }
  }

  // Clear all chats
  const clearAll = async () => {
    // Delete all chats from database
    for (const chat of chats.value) {
      try {
        await fetch(`${CHAT_API_URL}/${chat.id}`, {
          method: 'DELETE',
          headers: getHeaders()
        })
      } catch (e) {
        console.error('[chat store] clearAll delete failed:', e)
      }
    }

    chats.value = []
    activeChatId.value = null
    await createChat()
  }

  // Initialize store
  const initialize = async () => {
    if (isInitialized.value) return

    const authStore = useAuthStore()
    if (!authStore.user?.id) {
      console.warn('[chat store] No user ID, skipping database load')
      // Create a local chat if no user
      await createChat()
      return
    }

    const loaded = await loadFromDatabase()

    if (!loaded || chats.value.length === 0) {
      // No chats found, create first one
      await createChat()
    } else if (activeChatId.value) {
      // Load messages for active chat
      await loadChatMessages(activeChatId.value)
    }
  }

  return {
    chats,
    activeChatId,
    activeChat,
    isLoading,
    isInitialized,
    initialize,
    loadFromDatabase,
    loadChatMessages,
    createChat,
    deleteChat,
    setActiveChat,
    appendMessage,
    setSessionId,
    clearAll
  }
})
