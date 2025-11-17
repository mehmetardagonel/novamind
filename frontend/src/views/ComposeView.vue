<template>
  <div class="compose-view adjusted-view">

    <div class="chat-container">
      <div class="chat-history">
        <div 
          v-for="(message, index) in chatHistory" 
          :key="index"
          class="message"
          :class="{ 'ai-message': message.role === 'ai', 'user-message': message.role === 'user' }"
        >
          <p>{{ message.text }}</p>
        </div>

        <div v-if="isLoading" class="message ai-message loading-indicator">
          <p>
            <span class="dot">.</span>
            <span class="dot">.</span>
            <span class="dot">.</span>
          </p>
        </div>
      </div>

      <div class="chat-input-area">
        <div class="input-wrapper">
          <input 
            type="text" 
            placeholder="Type your prompt here..." 
            v-model="userPrompt"
            @keyup.enter="sendMessage"
            :disabled="isLoading"
          >
          <button class="inner-send" @click="sendMessage" :disabled="!userPrompt.trim() || isLoading">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" width="20" height="20">
              <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"></path>
            </svg>
          </button>
        </div>

        <button 
          class="voice-btn"
          :disabled="isLoading"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" width="20" height="20">
            <path d="M12 14a3 3 0 003-3V5a3 3 0 10-6 0v6a3 3 0 003 3zm5-3a5 5 0 01-10 0H5a7 7 0 0014 0h-2zm-5 9a3.001 3.001 0 01-2.83-2H9a5 5 0 009.9 0h-1.17A3.001 3.001 3.001 0 0112 20z" />
          </svg>
        </button>
      </div>

    </div>
  </div>
</template>

<script>
import { ref, nextTick } from 'vue'

export default { 
  name: 'ComposeView',
  setup() {
    const userPrompt = ref('')
    const isLoading = ref(false)
    const chatHistory = ref([
      { role: 'ai', text: 'How can I help you draft your email?' }
    ])

    const sendMessage = () => {
      if (!userPrompt.value.trim() || isLoading.value) return

      const promptToSend = userPrompt.value.trim()
      chatHistory.value.push({ role: 'user', text: promptToSend })
      userPrompt.value = ''

      nextTick(() => {
        const history = document.querySelector('.chat-history')
        if (history) history.scrollTop = history.scrollHeight
      })

      isLoading.value = true

      // Simulate AI response delay
      setTimeout(() => {
        chatHistory.value.push({ role: 'ai', text: `[Simulated response to: "${promptToSend}"] - Ready for your next command!` })
        isLoading.value = false
        nextTick(() => {
          const history = document.querySelector('.chat-history')
          if (history) history.scrollTop = history.scrollHeight
        })
      }, 1500)
    }

    return {
      userPrompt,
      isLoading,
      chatHistory,
      sendMessage,
    }
  }
}
</script>

<style scoped>
.compose-view {
  display: flex;
  flex-direction: column;
  height: calc(100% - 40px);
  padding: 0 1.5rem 1.5rem 0;
}

.assistant-header {
  color: var(--text-primary); 
  font-weight: 700;
  font-size: 1.8rem;
  padding-bottom: 1rem;
  border-bottom: 2px solid var(--border-color);
  margin-bottom: 1.5rem;
  margin-top: 0;
}

.chat-container {
  display: flex;
  flex-direction: column;
  flex-grow: 1;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  overflow: hidden; 
  background-color: var(--content-bg);
}

.chat-history {
  flex-grow: 1;
  padding: 1rem;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.message {
  max-width: 85%;
  padding: 10px 15px;
  border-radius: 18px;
  line-height: 1.4;
  font-size: 0.95rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.user-message {
  align-self: flex-end;
  background-color: var(--primary-color);
  color: white;
  border-bottom-right-radius: 4px;
}

.ai-message {
  align-self: flex-start;
  background-color: var(--hover-bg);
  color: var(--text-primary);
  border: 1px solid var(--light-border-color);
  border-bottom-left-radius: 4px;
}

.loading-indicator .dot {
  opacity: 0;
  animation: dot-flicker 1.5s infinite;
}

.loading-indicator .dot:nth-child(2) { animation-delay: 0.5s; }
.loading-indicator .dot:nth-child(3) { animation-delay: 1s; }

@keyframes dot-flicker {
  0%, 80%, 100% { opacity: 0; }
  40% { opacity: 1; }
}

.chat-input-area {
  padding: 1rem;
  border-top: 1px solid var(--border-color);
  display: flex;
  background-color: #f7f7f7; 
}

.input-wrapper {
  position: relative;
  flex-grow: 1;
}

.input-wrapper input {
  width: 100%;
  padding: 10px 45px 10px 15px;
  border: 1px solid var(--border-color);
  border-radius: 20px;
  font-size: 1rem;
  background-color: white;
}

.inner-send {
  position: absolute;
  right: 10px;
  top: 50%;
  transform: translateY(-50%);
  border: none;
  background: transparent;
  cursor: pointer;
  padding: 0;
  color: var(--primary-color); /* Added color */
}

.voice-btn {
  margin-left: 10px;
  padding: 10px 15px;
  border: none;
  border-radius: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: white;
  color: var(--text-primary); /* Set color */
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}
</style>