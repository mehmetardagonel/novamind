import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import apiClient from '@/api/client'
import { useAuthStore } from './auth'

export const useChatStore = defineStore('chat', () => {
  const authStore = useAuthStore()

  // State
  const chats = ref([])
  const activeChatId = ref(null)
  const isLoading = ref(false)
  const isInitialized = ref(false)

  // Computed
  const activeChat = computed(() => {
    return chats.value.find((c) => c.id === activeChatId.value) || null
  })

  // Initialize - load chats from database
  const initialize = async () => {
    if (isInitialized.value) return

    try {
      if (authStore.isAuthenticated) {
        await loadFromDatabase()
      }

      // Create first chat if none exist
      if (chats.value.length === 0) {
        await createChat()
      }

      // Load messages for active chat
      if (activeChat.value && !activeChat.value.messages) {
        await loadChatMessages(activeChat.value.id)
      }

      isInitialized.value = true
    } catch (error) {
      console.error('Failed to initialize chat store:', error)
      // Create a fallback local chat
      await createLocalChat()
      isInitialized.value = true
    }
  }

  // Load all chats from database
  const loadFromDatabase = async () => {
    try {
      const response = await apiClient.get('/chat/sessions', {
        headers: { 'X-User-Id': authStore.user?.id }
      })

      const sessionsData = response.data

      if (Array.isArray(sessionsData) && sessionsData.length > 0) {
        chats.value = sessionsData.map(session => ({
          id: session.id,
          title: session.title || 'New chat',
          sessionId: session.backend_session_id || null,
          messages: null, // Lazy loaded
          createdAt: session.created_at,
          updatedAt: session.updated_at
        }))

        // Set first chat as active
        if (!activeChatId.value && chats.value.length > 0) {
          activeChatId.value = chats.value[0].id
        }
      }
    } catch (error) {
      console.error('Failed to load chats from database:', error)
      throw error
    }
  }

  // Load messages for a specific chat
  const loadChatMessages = async (chatId) => {
    const chat = chats.value.find(c => c.id === chatId)
    if (!chat) return

    // Already loaded
    if (chat.messages) return

    try {
      const response = await apiClient.get(`/chat/sessions/${chatId}`, {
        headers: { 'X-User-Id': authStore.user?.id }
      })

      const sessionData = response.data

      if (sessionData.messages && Array.isArray(sessionData.messages)) {
        chat.messages = sessionData.messages.map(msg => ({
          role: msg.role,
          text: msg.text,
          emails: msg.emails || null
        }))
      } else {
        // No messages yet, add welcome message
        chat.messages = [{
          role: 'bot',
          text: 'Hello! How can I help you manage your emails today?',
          emails: null
        }]
      }
    } catch (error) {
      console.error('Failed to load chat messages:', error)
      // Fallback to welcome message
      chat.messages = [{
        role: 'bot',
        text: 'Hello! How can I help you manage your emails today?',
        emails: null
      }]
    }
  }

  // Create new chat
  const createChat = async () => {
    const newChat = {
      id: `chat_${Date.now()}`,
      title: 'New chat',
      sessionId: null,
      messages: [{
        role: 'bot',
        text: 'Hello! How can I help you manage your emails today?',
        emails: null
      }],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString()
    }

    // Add to state immediately (optimistic update)
    chats.value.unshift(newChat)
    activeChatId.value = newChat.id

    // Save to database if authenticated
    if (authStore.isAuthenticated) {
      try {
        const response = await apiClient.post('/chat/sessions', {
          title: newChat.title
        }, {
          headers: { 'X-User-Id': authStore.user?.id }
        })

        // Update with server ID
        const chat = chats.value.find(c => c.id === newChat.id)
        if (chat && response.data.id) {
          chat.id = response.data.id
          activeChatId.value = response.data.id
        }
      } catch (error) {
        console.error('Failed to save chat to database:', error)
        // Keep local chat even if DB fails
      }
    }

    return newChat
  }

  // Create local-only chat (fallback)
  const createLocalChat = async () => {
    const newChat = {
      id: `local_${Date.now()}`,
      title: 'New chat',
      sessionId: null,
      messages: [{
        role: 'bot',
        text: 'Hello! How can I help you manage your emails today?',
        emails: null
      }],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString()
    }

    chats.value.push(newChat)
    activeChatId.value = newChat.id
    return newChat
  }

  // Delete chat
  const deleteChat = async (chatId) => {
    const index = chats.value.findIndex(c => c.id === chatId)
    if (index === -1) return

    // Remove from state immediately
    chats.value.splice(index, 1)

    // Delete from database if authenticated and not local chat
    if (authStore.isAuthenticated && !chatId.startsWith('local_')) {
      try {
        await apiClient.delete(`/chat/sessions/${chatId}`, {
          headers: { 'X-User-Id': authStore.user?.id }
        })
      } catch (error) {
        console.error('Failed to delete chat from database:', error)
      }
    }

    // If deleted active chat, switch to another
    if (activeChatId.value === chatId) {
      if (chats.value.length > 0) {
        activeChatId.value = chats.value[0].id
        if (!chats.value[0].messages) {
          await loadChatMessages(chats.value[0].id)
        }
      } else {
        // Create new chat if deleted the last one
        await createChat()
      }
    }
  }

  // Set active chat
  const setActiveChat = async (chatId) => {
    const chat = chats.value.find(c => c.id === chatId)
    if (!chat) return

    activeChatId.value = chatId

    // Lazy load messages if not loaded
    if (!chat.messages) {
      await loadChatMessages(chatId)
    }
  }

  // Append message to chat
  const appendMessage = async (chatId, message) => {
    const chat = chats.value.find(c => c.id === chatId)
    if (!chat) return

    // Ensure messages array exists
    if (!chat.messages) {
      chat.messages = []
    }

    // Add message immediately (optimistic)
    chat.messages.push(message)
    chat.updatedAt = new Date().toISOString()

    // Auto-generate title from first user message
    if (message.role === 'user' && chat.title === 'New chat') {
      const title = message.text.substring(0, 40) + (message.text.length > 40 ? '...' : '')
      chat.title = title

      if (authStore.isAuthenticated && !chatId.startsWith('local_')) {
        updateSessionTitle(chatId, title)
      }
    }

    // Save to database if authenticated
    if (authStore.isAuthenticated && !chatId.startsWith('local_')) {
      addMessageToDatabase(chatId, message)
    }
  }

  // Add message to database (non-blocking)
  const addMessageToDatabase = async (chatId, message) => {
    try {
      await apiClient.post(`/chat/sessions/${chatId}/messages`, {
        role: message.role,
        text: message.text,
        emails: message.emails
      }, {
        headers: { 'X-User-Id': authStore.user?.id }
      })
    } catch (error) {
      console.error('Failed to save message to database:', error)
      // Continue anyway - message is already in local state
    }
  }

  // Update session title
  const updateSessionTitle = async (chatId, title) => {
    try {
      await apiClient.patch(`/chat/sessions/${chatId}`, {
        title
      }, {
        headers: { 'X-User-Id': authStore.user?.id }
      })
    } catch (error) {
      console.error('Failed to update session title:', error)
    }
  }

  // Set backend session ID
  const setSessionId = async (chatId, sessionId) => {
    const chat = chats.value.find(c => c.id === chatId)
    if (!chat) return

    chat.sessionId = sessionId

    if (authStore.isAuthenticated && !chatId.startsWith('local_')) {
      try {
        await apiClient.patch(`/chat/sessions/${chatId}`, {
          backend_session_id: sessionId
        }, {
          headers: { 'X-User-Id': authStore.user?.id }
        })
      } catch (error) {
        console.error('Failed to update session ID:', error)
      }
    }
  }

  // Clear all chats
  const clearAll = async () => {
    const chatIds = [...chats.value.map(c => c.id)]

    for (const chatId of chatIds) {
      await deleteChat(chatId)
    }

    // Create fresh chat
    await createChat()
  }

  return {
    // State
    chats,
    activeChatId,
    isLoading,
    isInitialized,

    // Computed
    activeChat,

    // Actions
    initialize,
    loadFromDatabase,
    loadChatMessages,
    createChat,
    deleteChat,
    setActiveChat,
    appendMessage,
    setSessionId,
    updateSessionTitle,
    clearAll
  }
})
