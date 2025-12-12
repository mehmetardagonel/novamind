<template>
  <div class="compose-view adjusted-view">
    <div class="chat-container">
      <div class="chat-history" ref="historyContainer">
        <div
          v-for="(message, index) in chatHistory"
          :key="index"
          class="message"
          :class="{
            'ai-message': message.role === 'bot',
            'user-message': message.role === 'user',
          }"
        >
          <p v-if="message.text" class="message-text">{{ message.text }}</p>

          <div
            v-if="message.emails && message.emails.length > 0"
            class="emails-list"
          >
            <div
              v-for="(email, eIndex) in message.emails"
              :key="eIndex"
              class="email-block"
            >
              <div class="email-header">📧 Email #{{ eIndex + 1 }}</div>

              <div class="email-field">
                <strong>From:</strong>
                {{ email.from || email.sender || "Unknown" }}
              </div>

              <div class="email-field">
                <strong>Subject:</strong> {{ email.subject || "(No subject)" }}
              </div>

              <div v-if="email.date || email.timestamp" class="email-field">
                <strong>Date:</strong> {{ email.date || email.timestamp }}
              </div>

              <div v-if="email.label" class="email-field email-label">
                <strong>Label:</strong>
                <span class="label-badge">{{ email.label }}</span>
              </div>

              <div
                v-if="email.is_important"
                class="email-field email-important"
              >
                ⭐ <strong>Important</strong>
              </div>

              <div class="email-separator"></div>

              <div class="email-field email-body">
                <strong>Body:</strong><br />
                <div
                  class="email-body-content"
                  v-html="formatBody(email.body)"
                ></div>
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
          />

          <!-- Send button -->
          <button
            class="inner-send"
            @click="sendMessage"
            :disabled="!userPrompt.trim() || isLoading || isListening"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="currentColor"
              width="20"
              height="20"
            >
              <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"></path>
            </svg>
          </button>

          <!-- Voice button (always visible) -->
          <div class="voice-wrap">
            <button
              class="inner-voice"
              @click="toggleVoiceInput"
              :disabled="isLoading"
              :class="{ 'listening-active': isListening }"
              :aria-pressed="isListening"
              :title="isListening ? 'Stop listening' : 'Start voice input'"
            >
              <span class="material-symbols-outlined mic-icon">mic</span>
            </button>

            <button
              v-if="isListening"
              class="voice-cancel-icon"
              @click="cancelVoice"
              title="Cancel recording"
              type="button"
            >
              <span class="material-symbols-outlined">close</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, nextTick } from "vue";

export default {
  name: "ComposeView",
  setup() {
    const userPrompt = ref("");
    const isLoading = ref(false);
    const historyContainer = ref(null);
    const isListening = ref(false); // New state for listening box
    const API_URL = "http://localhost:8001/chat";

    const STORAGE_KEY_HISTORY = "chat_history";
    const STORAGE_KEY_SESSION = "chat_session_id";

    const initialBotMessage = {
      role: "bot",
      text: "Hello! How can I help you manage your emails today?",
      emails: [],
    };

    const loadStoredHistory = () => {
      try {
        const raw = sessionStorage.getItem(STORAGE_KEY_HISTORY);
        if (!raw) return null;
        const parsed = JSON.parse(raw);
        return Array.isArray(parsed) ? parsed : null;
      } catch (e) {
        console.error("Failed to load chat history from storage:", e);
        return null;
      }
    };

    const storedHistory = loadStoredHistory();
    const chatHistory = ref(
      storedHistory && storedHistory.length
        ? storedHistory
        : [initialBotMessage]
    );

    const storedSessionId = sessionStorage.getItem(STORAGE_KEY_SESSION);
    const sessionId = ref(storedSessionId || null);

    const persistChatState = () => {
      try {
        sessionStorage.setItem(
          STORAGE_KEY_HISTORY,
          JSON.stringify(chatHistory.value)
        );
        if (sessionId.value) {
          sessionStorage.setItem(STORAGE_KEY_SESSION, sessionId.value);
        } else {
          sessionStorage.removeItem(STORAGE_KEY_SESSION);
        }
      } catch (e) {
        console.error("Failed to persist chat state:", e);
      }
    };

    const formatBody = (text) => {
      if (!text) return "";
      return text.replace(/\n/g, "<br>");
    };

    const isEmailArray = (text) => {
      if (!text.trim().startsWith("[") || !text.trim().endsWith("]"))
        return false;
      try {
        const parsed = JSON.parse(text);
        return (
          Array.isArray(parsed) &&
          parsed.length > 0 &&
          parsed[0].hasOwnProperty("subject") &&
          (parsed[0].hasOwnProperty("from") ||
            parsed[0].hasOwnProperty("sender"))
        );
      } catch {
        return false;
      }
    };

    const extractJsonFromText = (text) => {
      const result = { textBefore: "", json: null };
      const jsonMatch = text.match(/\[\s*\{[\s\S]*\}\s*\]/);

      if (jsonMatch) {
        try {
          if (isEmailArray(jsonMatch[0])) {
            result.json = JSON.parse(jsonMatch[0]);
            const textBefore = text.substring(0, jsonMatch.index).trim();
            if (textBefore) result.textBefore = textBefore;
            return result;
          }
        } catch {
          // ignore
        }
      }

      result.textBefore = text;
      return result;
    };

    const scrollToBottom = () => {
      nextTick(() => {
        if (historyContainer.value) {
          historyContainer.value.scrollTop =
            historyContainer.value.scrollHeight;
        }
      });
    };

    const sendMessage = async () => {
      if (!userPrompt.value.trim() || isLoading.value) return;

      const messageText = userPrompt.value.trim();

      chatHistory.value.push({ role: "user", text: messageText, emails: null });
      userPrompt.value = "";
      persistChatState();
      scrollToBottom();

      isLoading.value = true;

      try {
        const response = await fetch(API_URL, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message: messageText,
            session_id: sessionId.value,
          }),
        });

        if (!response.ok) throw new Error("API request failed");

        const data = await response.json();

        if (data.session_id) {
          sessionId.value = data.session_id;
        }

        const extracted = extractJsonFromText(data.response);

        chatHistory.value.push({
          role: "bot",
          text: extracted.textBefore,
          emails: extracted.json,
        });

        persistChatState();
      } catch (error) {
        console.error("Error:", error);
        chatHistory.value.push({
          role: "bot",
          text: "Sorry, an error occurred connecting to the server. Please ensure the backend is running.",
          emails: null,
        });
        persistChatState();
      } finally {
        isLoading.value = false;
        scrollToBottom();
      }
    };

    const toggleVoiceInput = () => {
      if (isLoading.value) return;

      // Stop listening -> SEND (if we have text)
      if (isListening.value) {
        isListening.value = false;

        if (userPrompt.value.trim()) {
          sendMessage();
        }
        return;
      }

      // Start listening
      isListening.value = true;

      // Start Web Speech API here later if you add it
    };

    const cancelVoice = () => {
      isListening.value = false;
      // Optional: clear whatever was dictated
      // userPrompt.value = "";
    };

    const clearChat = () => {
      chatHistory.value = [initialBotMessage];
      sessionId.value = null;
      sessionStorage.removeItem(STORAGE_KEY_HISTORY);
      sessionStorage.removeItem(STORAGE_KEY_SESSION);
    };

    return {
      userPrompt,
      isLoading,
      isListening,
      chatHistory,
      sendMessage,
      formatBody,
      historyContainer,
      toggleVoiceInput,
      cancelVoice,
      clearChat,
    };
  },
};
</script>

<style scoped>
.compose-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 0 1.5rem 1.5rem 0;
}

.chat-container {
  display: flex;
  flex-direction: column;
  flex-grow: 1;
  border: 1px solid var(--border-color);
  border-radius: 12px;
  overflow: hidden;
  background-color: var(--content-bg);
}

/* Scrollable messages */
.chat-history {
  flex-grow: 1;
  padding: 1rem 1rem 0.75rem;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* Message bubbles */
.message {
  max-width: 70%;
  padding: 10px 14px;
  border-radius: 18px;
  line-height: 1.5;
  font-size: 0.95rem;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06);
  word-wrap: break-word;
}

.user-message {
  align-self: flex-end;
  background-color: var(--primary-color);
  color: #fff;
  border-bottom-right-radius: 4px;
}

.ai-message {
  align-self: flex-start;
  background-color: var(--hover-bg);
  color: var(--text-primary);
  border: 1px solid var(--light-border-color);
  border-bottom-left-radius: 4px;
}

.message-text {
  margin: 0;
}

/* Email cards inside AI messages */
.emails-list {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
}

.email-block {
  background: #ffffff;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 10px 12px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
  text-align: left;
  color: #333;
}

.email-header {
  font-weight: 600;
  color: var(--primary-color);
  border-bottom: 1px solid #eee;
  padding-bottom: 4px;
  margin-bottom: 6px;
  font-size: 0.88rem;
}

.email-field {
  margin-bottom: 4px;
  font-size: 0.88rem;
  line-height: 1.4;
}

.email-separator {
  height: 1px;
  background: #eee;
  margin: 6px 0;
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
  padding: 3px 6px;
  border-radius: 4px;
  display: inline-block;
}

.email-body-content {
  background: #f9f9f9;
  padding: 7px;
  border-radius: 4px;
  margin-top: 4px;
  font-family: "Courier New", Courier, monospace;
  font-size: 0.84rem;
  white-space: pre-wrap;
  color: #444;
}

/* Loading dots */
.loading-indicator .dot {
  opacity: 0;
  animation: dot-flicker 1.5s infinite;
}

.loading-indicator .dot:nth-child(2) {
  animation-delay: 0.4s;
}
.loading-indicator .dot:nth-child(3) {
  animation-delay: 0.8s;
}

@keyframes dot-flicker {
  0%,
  80%,
  100% {
    opacity: 0;
  }
  40% {
    opacity: 1;
  }
}

/* Bottom input area */
.chat-input-area {
  padding: 0.75rem 1rem 1rem;
  border-top: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  background-color: var(--content-bg);
}

.input-wrapper {
  position: relative;
  flex-grow: 1;
  z-index: 1;

  /* NEW: make the wrapper the pill */
  border: 1px solid var(--border-color);
  border-radius: 999px;
  background: var(--content-bg);
  overflow: visible; /* IMPORTANT: clips the right side cleanly */
}

/* Input should not draw its own border anymore */
.input-wrapper input {
  width: 100%;
  padding: 10px 190px 10px 14px;

  border: none; /* NEW */
  border-radius: 999px; /* ok to keep */
  background: transparent; /* NEW */

  font-size: 0.96rem;
  color: var(--text-primary);
  outline: none;
}

.input-wrapper:focus-within {
  border-color: var(--primary-color);
  box-shadow: 0 0 0 2px rgba(124, 77, 255, 0.15);
}

/* Send & voice buttons */
/* Send & voice buttons (single source of truth) */
.inner-send,
.inner-voice {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  border: none;
  cursor: pointer;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;

  width: 34px;
  height: 34px;
  border-radius: 999px;
  background: transparent;

  transition: transform 120ms ease, background 160ms ease, box-shadow 160ms ease;
}

/* Send button placement + subtle hover */
.inner-send {
  right: 52px; /* <-- this is the key */
  color: var(--primary-color);
}

.inner-send:hover:not(:disabled) {
  background: rgba(124, 77, 255, 0.1);
}

/* Voice button placement + styled background */
.inner-voice {
  right: 10px;
  background: rgba(124, 77, 255, 0.16);
  border: 1px solid var(--border-color);
  color: var(--primary-color);
}

.inner-voice:hover:not(:disabled) {
  transform: translateY(-1px); /* keep the lift */
  background: rgba(124, 77, 255, 0.22);
  box-shadow: 0 6px 14px rgba(0, 0, 0, 0.12);
}

/* Listening state: red + subtle pulse */
.inner-voice.listening-active {
  background: rgba(255, 77, 109, 0.18);
  border-color: rgba(255, 77, 109, 0.35);
  color: #ff4d6d;
  box-shadow: 0 10px 22px rgba(255, 77, 109, 0.12);
  animation: micPulse 1.2s ease-out infinite;
}

@keyframes micPulse {
  0% {
    box-shadow: 0 0 0 0 rgba(255, 77, 109, 0.25);
  }
  70% {
    box-shadow: 0 0 0 10px rgba(255, 77, 109, 0);
  }
  100% {
    box-shadow: 0 0 0 0 rgba(255, 77, 109, 0);
  }
}

.inner-send:disabled,
.inner-voice:disabled {
  opacity: 0.55;
  cursor: not-allowed;
  box-shadow: none;
  transform: translateY(-50%);
}

/* Mic icon sizing */
.mic-icon.material-symbols-outlined {
  font-size: 20px;
  line-height: 1;
  font-variation-settings: "FILL" 0, "wght" 500, "GRAD" 0, "opsz" 24;
}

/* anchor container exactly where mic lives */
.voice-wrap {
  position: absolute;
  right: 10px; /* same as old mic right */
  top: 50%;
  transform: translateY(-50%);
  width: 34px;
  height: 34px;
}

/* mic becomes normal inside wrapper */
.voice-wrap .inner-voice {
  position: relative;
  right: auto;
  top: auto;
  transform: none;
}
/* Cancel (X) — perfectly centered and never jumps */
.voice-wrap .voice-cancel-icon {
  position: absolute;
  left: 50%;
  bottom: 42px;

  width: 26px;
  height: 26px;
  padding: 0;
  border-radius: 999px;

  border: 1px solid var(--border-color);
  background: var(--content-bg);
  color: var(--text-secondary);

  display: flex;
  align-items: center;
  justify-content: center;

  cursor: pointer;
  z-index: 10;
  box-shadow: 0 8px 16px rgba(0, 0, 0, 0.12);

  /* keep centering ALWAYS */
  transform: translateX(-50%);
  transition: transform 120ms ease, background 120ms ease, box-shadow 120ms ease,
    color 120ms ease;
}

.voice-wrap .voice-cancel-icon:hover {
  background: rgba(255, 77, 109, 0.1);
  color: #ff4d6d;

  /* keep centering + tiny lift */
  transform: translateX(-50%) translateY(-1px);
}

.voice-wrap .voice-cancel-icon:active {
  /* keep centering + press */
  transform: translateX(-50%) scale(0.98);
  box-shadow: 0 6px 12px rgba(0, 0, 0, 0.1);
}

/* Icon sizing */
.voice-wrap .voice-cancel-icon .material-symbols-outlined {
  font-size: 18px;
  line-height: 1;
  font-variation-settings: "FILL" 0, "wght" 500, "GRAD" 0, "opsz" 20;
}
</style>
