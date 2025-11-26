<template>
  <div class="compose-view adjusted-view">

    <div class="chat-container">
      <div class="chat-history" ref="historyContainer">
        <div 
          v-for="(message, index) in chatHistory" 
          :key="index"
          class="message"
          :class="{ 'ai-message': message.role === 'bot', 'user-message': message.role === 'user' }"
        >
          <p v-if="message.text" class="message-text">{{ message.text }}</p>

          <div v-if="message.emails && message.emails.length > 0" class="emails-list">
            <div v-for="(email, eIndex) in message.emails" :key="eIndex" class="email-block">
              
              <div class="email-header">📧 Email #{{ eIndex + 1 }}</div>
              
              <div class="email-field">
                <strong>From:</strong> {{ email.from || email.sender || 'Unknown' }}
              </div>

              <div class="email-field">
                <strong>Subject:</strong> {{ email.subject || '(No subject)' }}
              </div>

              <div v-if="email.date || email.timestamp" class="email-field">
                <strong>Date:</strong> {{ email.date || email.timestamp }}
              </div>

              <div v-if="email.label" class="email-field email-label">
                <strong>Label:</strong> <span class="label-badge">{{ email.label }}</span>
              </div>

              <div v-if="email.is_important" class="email-field email-important">
                ⭐ <strong>Important</strong>
              </div>

              <div class="email-separator"></div>

              <div class="email-field email-body">
                <strong>Body:</strong><br>
                <div class="email-body-content" v-html="formatBody(email.body)"></div>
              </div>

            </div>
          </div>
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
    const historyContainer = ref(null)
    const API_URL = 'http://127.0.0.1:8001/chat'

    // Initial state
    const chatHistory = ref([
      { role: 'bot', text: 'Hello! I\'m your email assistant. How can I help you today?', emails: [] }
    ])

    // Helper: Format body text (newlines to <br>)
    const formatBody = (text) => {
      if (!text) return '';
      return text.replace(/\n/g, '<br>');
    }

    // Logic: Check if string looks like an email array
    const isEmailArray = (text) => {
      if (!text.trim().startsWith('[') || !text.trim().endsWith(']')) {
        return false;
      }
      try {
        const parsed = JSON.parse(text);
        return Array.isArray(parsed) && parsed.length > 0 &&
               parsed[0].hasOwnProperty('subject') &&
               (parsed[0].hasOwnProperty('from') || parsed[0].hasOwnProperty('sender'));
      } catch (e) {
        return false;
      }
    }

    // Logic: Extract JSON from mixed text
    const extractJsonFromText = (text) => {
      const result = {
        textBefore: '',
        json: null
      };

      const jsonMatch = text.match(/\[\s*\{[\s\S]*\}\s*\]/);

      if (jsonMatch) {
        try {
          // Validate it's actually an email array before accepting it
          if(isEmailArray(jsonMatch[0])) {
              result.json = JSON.parse(jsonMatch[0]);
              const textBefore = text.substring(0, jsonMatch.index).trim();
              if (textBefore) result.textBefore = textBefore;
              return result;
          }
        } catch (e) {
          // parsing failed, fall through
        }
      }
      
      // No valid JSON found
      result.textBefore = text;
      return result;
    }

    const scrollToBottom = () => {
      nextTick(() => {
        if (historyContainer.value) {
          historyContainer.value.scrollTop = historyContainer.value.scrollHeight;
        }
      })
    }

    const sendMessage = async () => {
      if (!userPrompt.value.trim() || isLoading.value) return

      const messageText = userPrompt.value.trim()
      
      // Add User Message
      chatHistory.value.push({ role: 'user', text: messageText, emails: null })
      userPrompt.value = ''
      scrollToBottom()

      isLoading.value = true

      try {
        const response = await fetch(API_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: messageText })
        });

        if (!response.ok) throw new Error('API request failed');

        const data = await response.json();
        
        // Process Response
        const extracted = extractJsonFromText(data.response);
        
        chatHistory.value.push({
            role: 'bot',
            text: extracted.textBefore, // The text part
            emails: extracted.json      // The email array part (if any)
        });

      } catch (error) {
        console.error('Error:', error);
        chatHistory.value.push({ 
            role: 'bot', 
            text: 'Sorry, an error occurred connecting to the server. Please ensure the backend is running.',
            emails: null
        });
      } finally {
        isLoading.value = false
        scrollToBottom()
      }
    }

    return {
      userPrompt,
      isLoading,
      chatHistory,
      sendMessage,
      formatBody,
      historyContainer
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
  gap: 15px;
}

.message {
  max-width: 85%;
  padding: 12px 16px;
  border-radius: 18px;
  line-height: 1.5;
  font-size: 0.95rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
  word-wrap: break-word;
}

.user-message {
  align-self: flex-end;
  background-color: var(--primary-color);
  color: white;
  border-bottom-right-radius: 4px;
}

.ai-message {
  align-self: flex-start;
  background-color: #f0f2f5; /* Fallback if var missing */
  background-color: var(--hover-bg);
  color: var(--text-primary);
  border: 1px solid var(--light-border-color);
  border-bottom-left-radius: 4px;
}

.message-text {
  margin: 0;
}

/* --- Email Card Styles (Ported from Vanilla JS) --- */

.emails-list {
    margin-top: 12px;
    display: flex;
    flex-direction: column;
    gap: 10px;
    width: 100%;
}

.email-block {
    background: #ffffff;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    padding: 12px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    text-align: left;
    color: #333;
}

.email-header {
    font-weight: 600;
    color: var(--primary-color);
    border-bottom: 1px solid #eee;
    padding-bottom: 6px;
    margin-bottom: 8px;
    font-size: 0.9rem;
}

.email-field {
    margin-bottom: 6px;
    font-size: 0.9rem;
    line-height: 1.4;
}

.email-separator {
    height: 1px;
    background: #eee;
    margin: 8px 0;
}

.label-badge {
    background-color: #e3f2fd;
    color: #1976d2;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 0.8rem;
    font-weight: 500;
}

.email-important {
    color: #d32f2f;
    background-color: #ffebee;
    padding: 4px 8px;
    border-radius: 4px;
    display: inline-block;
}

.email-body-content {
    background: #f9f9f9;
    padding: 8px;
    border-radius: 4px;
    margin-top: 4px;
    font-family: 'Courier New', Courier, monospace;
    font-size: 0.85rem;
    white-space: pre-wrap; /* Handles wrapping */
    color: #444;
}

/* --- End Email Card Styles --- */

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
  color: var(--primary-color);
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
  color: var(--text-primary); 
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}
</style>