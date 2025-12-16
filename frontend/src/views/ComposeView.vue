<template>
  <div class="compose-view adjusted-view">
    <div class="chat-split">
      <aside class="chat-sidebar">
        <div class="chat-sidebar-header">
          <div class="chat-sidebar-title">Chats</div>
          <button class="chat-new" @click="createChat" title="New chat">
            + New
          </button>
        </div>

        <div class="chat-list">
          <div
            v-for="c in chats"
            :key="c.id"
            class="chat-list-item"
            :class="{ active: c.id === activeChatId }"
            @click="setActiveChat(c.id)"
          >
            <div class="chat-list-item-title">{{ c.title }}</div>
            <button
              class="chat-delete"
              title="Delete chat"
              @click.stop="deleteChat(c.id)"
            >
              ×
            </button>
          </div>
        </div>
      </aside>

      <div class="chat-main">
        <div class="chat-container">
          <div class="chat-history" ref="historyContainer">
            <div
              v-for="(message, index) in activeMessages"
              :key="index"
              class="message"
              :class="{
                'ai-message': message.role === 'bot',
                'user-message': message.role === 'user',
              }"
            >
              <p
                v-if="message.text"
                class="message-text"
                v-html="formatMessageText(message.text)"
              ></p>
              <p
                v-else-if="
                  message.role === 'bot' &&
                  message.emails &&
                  message.emails.length > 0
                "
                class="message-text"
              >
                Here are the emails I found:
              </p>

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
                    <strong>Subject:</strong>
                    {{ email.subject || "(No subject)" }}
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

          <div v-if="isListening" class="listening-box">
            Listening<span class="dot-animation">{{ listeningDots }}</span>
          </div>

          <div class="chat-input-area">
            <div class="input-wrapper">
              <input
                type="text"
                placeholder="Type your prompt here..."
                v-model="userPrompt"
                @keyup.enter="sendMessage"
                :disabled="isLoading || isListening || !activeChat"
              />

              <!-- Send button -->
              <button
                class="inner-send"
                @click="sendMessage"
                :disabled="
                  !userPrompt.trim() || isLoading || isListening || !activeChat
                "
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

              <!-- Voice button (always visible, disabled while loading) -->
              <button
                class="inner-voice"
                @click="toggleVoiceInput"
                :disabled="isLoading || !activeChat"
                :class="{ 'listening-active': isListening }"
              >
                <span class="material-symbols-outlined mic-icon">mic</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { computed, ref, nextTick, onUnmounted, onMounted, watch } from "vue";
import { useAuthStore } from "../stores/auth";
import { useChatStore } from "../stores/chat";

export default {
  name: "ComposeView",
  setup() {
    const authStore = useAuthStore();
    const chatStore = useChatStore();
    const userPrompt = ref("");
    const isLoading = ref(false);
    const historyContainer = ref(null);
    const isListening = ref(false); // New state for listening box
    const listeningDots = ref(""); // New state for dot animation
    let dotInterval = null; // For managing the dot animation timer
    const API_BASE_URL =
      import.meta.env.VITE_API_URL || "http://localhost:8001";
    const normalizedBase = API_BASE_URL.endsWith("/")
      ? API_BASE_URL.slice(0, -1)
      : API_BASE_URL;
    const API_URL = `${normalizedBase}/chat`;

    const chats = computed(() => chatStore.chats);
    const activeChatId = computed(() => chatStore.activeChatId);
    const activeChat = computed(() => chatStore.activeChat);
    const activeMessages = computed(() => activeChat.value?.messages || []);

    const formatBody = (text) => {
      if (!text) return "";
      return text.replace(/\n/g, "<br>");
    };

    const formatMessageText = (text) => {
      if (!text) return "";
      // Escape HTML entities first, then convert newlines to <br>
      const escaped = text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
      return escaped.replace(/\n/g, "<br>");
    };

    const isEmailArray = (parsed) => {
      if (!Array.isArray(parsed) || parsed.length === 0) return false;
      const first = parsed[0];
      if (!first || typeof first !== "object") return false;
      return (
        Object.prototype.hasOwnProperty.call(first, "subject") &&
        (Object.prototype.hasOwnProperty.call(first, "from") ||
          Object.prototype.hasOwnProperty.call(first, "sender"))
      );
    };

    const tryParseEmailsJson = (raw) => {
      try {
        const parsed = JSON.parse(raw);
        return isEmailArray(parsed) ? parsed : null;
      } catch {
        return null;
      }
    };

    const extractJsonFromText = (text) => {
      const result = { textBefore: "", json: null };
      if (!text) return { textBefore: "", json: null };

      // 1) Prefer fenced JSON blocks: ```json ... ``` (with or without newline after json)
      const fenceRegex = /```json\s*([\s\S]*?)\s*```/gi;
      for (const match of text.matchAll(fenceRegex)) {
        const candidate = (match[1] || "").trim();
        const emails = tryParseEmailsJson(candidate);
        if (emails) {
          result.json = emails;
          result.textBefore = text.slice(0, match.index || 0).trim();
          return result;
        }
      }

      // 2) Fallback: any fenced block that happens to contain the email array
      const anyFenceRegex = /```\s*([\s\S]*?)\s*```/g;
      for (const match of text.matchAll(anyFenceRegex)) {
        const candidate = (match[1] || "").trim();
        const emails = tryParseEmailsJson(candidate);
        if (emails) {
          result.json = emails;
          result.textBefore = text.slice(0, match.index || 0).trim();
          return result;
        }
      }

      // 3) Last resort: locate the first JSON array substring and try parsing it
      const bracketRegex = /\[[\s\S]*\]/g;
      for (const match of text.matchAll(bracketRegex)) {
        const candidate = match[0];
        const emails = tryParseEmailsJson(candidate);
        if (emails) {
          result.json = emails;
          result.textBefore = text.slice(0, match.index || 0).trim();
          return result;
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
      if (!activeChat.value) return;
      if (!userPrompt.value.trim() || isLoading.value) return;

      const messageText = userPrompt.value.trim();
      const chatId = activeChat.value.id;

      chatStore.appendMessage(chatId, {
        role: "user",
        text: messageText,
        emails: null,
      });
      userPrompt.value = "";
      scrollToBottom();

      isLoading.value = true;

      try {
        const response = await fetch(API_URL, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-User-Id": authStore.user?.id,
          },
          body: JSON.stringify({
            message: messageText,
            session_id: activeChat.value.sessionId,
          }),
        });

        if (!response.ok) {
          const errorText = await response.text();
          console.error("API error response:", errorText);
          throw new Error(`API request failed: ${response.status}`);
        }

        const data = await response.json();
        console.log("Chat response data:", data);

        if (data.session_id) {
          chatStore.setSessionId(chatId, data.session_id);
        }

        // Handle response - extract JSON and text
        const responseText = data.response || "";
        const extracted = extractJsonFromText(responseText);

        // Ensure we always have some text to display
        let displayText = extracted.textBefore;
        if (!displayText && extracted.json && extracted.json.length > 0) {
          displayText = `Found ${extracted.json.length} email(s):`;
        } else if (!displayText && !extracted.json) {
          displayText = responseText || "I processed your request.";
        }

        chatStore.appendMessage(chatId, {
          role: "bot",
          text: displayText,
          emails: extracted.json,
        });
      } catch (error) {
        console.error("Error:", error);
        chatStore.appendMessage(chatId, {
          role: "bot",
          text: "Sorry, an error occurred connecting to the server. Please ensure the backend is running.",
          emails: null,
        });
      } finally {
        isLoading.value = false;
        scrollToBottom();
      }
    };

    // New function for dot animation
    const startDotAnimation = () => {
      listeningDots.value = "";
      dotInterval = setInterval(() => {
        listeningDots.value =
          listeningDots.value.length < 3 ? listeningDots.value + "." : "";
      }, 500); // Change dot every 0.5 seconds
    };

    // New function to clear the dot animation
    const stopDotAnimation = () => {
      if (dotInterval) {
        clearInterval(dotInterval);
        dotInterval = null;
      }
      listeningDots.value = "";
    };

    // New function to toggle the voice input state
    const toggleVoiceInput = () => {
      if (isLoading.value) return; // Prevent toggling if a message is being processed

      isListening.value = !isListening.value;

      if (isListening.value) {
        startDotAnimation();
        // Here you would typically start the Web Speech API recognition
        // console.log("Starting voice recognition...");
      } else {
        stopDotAnimation();
        // Here you would typically stop the Web Speech API recognition
        // console.log("Stopping voice recognition...");
      }
    };

    // Clear interval when component is destroyed
    onUnmounted(() => {
      stopDotAnimation();
    });

    // Initialize chat store on mount
    onMounted(async () => {
      await chatStore.initialize();
      nextTick(scrollToBottom);
    });

    const clearChat = async () => {
      await chatStore.clearAll();
    };

    const createChat = async () => {
      await chatStore.createChat();
      nextTick(scrollToBottom);
    };

    const deleteChat = async (chatId) => {
      await chatStore.deleteChat(chatId);
      nextTick(scrollToBottom);
    };

    const setActiveChat = async (chatId) => {
      await chatStore.setActiveChat(chatId);
      nextTick(scrollToBottom);
    };

    watch(
      () => activeChatId.value,
      () => {
        nextTick(scrollToBottom);
      }
    );

    return {
      userPrompt,
      isLoading,
      isListening,
      listeningDots,
      chats,
      activeChatId,
      activeChat,
      activeMessages,
      sendMessage,
      formatBody,
      formatMessageText,
      historyContainer,
      toggleVoiceInput,
      clearChat,
      createChat,
      deleteChat,
      setActiveChat,
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

.chat-split {
  display: flex;
  gap: 12px;
  height: 100%;
  min-height: 0;
}

.chat-sidebar {
  width: 260px;
  border: 1px solid var(--border-color);
  border-radius: 12px;
  overflow: hidden;
  background-color: var(--content-bg);
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.chat-sidebar-header {
  padding: 12px;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.chat-sidebar-title {
  font-weight: 600;
  color: var(--text-primary);
}

.chat-new {
  background: var(--primary-color);
  color: #fff;
  border: none;
  padding: 6px 10px;
  border-radius: 10px;
  cursor: pointer;
  font-size: 0.9rem;
}

.chat-new:hover {
  filter: brightness(0.95);
}

.chat-list {
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  overflow: auto;
  min-height: 0;
}

.chat-list-item {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 10px 10px;
  border-radius: 10px;
  border: 1px solid transparent;
  background: transparent;
  color: var(--text-primary);
  cursor: pointer;
  text-align: left;
}

.chat-list-item:hover {
  background: var(--hover-bg);
}

.chat-list-item.active {
  border-color: var(--border-color);
  background: var(--hover-bg);
}

.chat-list-item-title {
  font-size: 0.92rem;
  line-height: 1.2;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.chat-delete {
  width: 26px;
  height: 26px;
  border: none;
  border-radius: 8px;
  background: transparent;
  cursor: pointer;
  font-size: 18px;
  line-height: 1;
  color: var(--text-secondary);
}

.chat-delete:hover {
  background: rgba(0, 0, 0, 0.06);
  color: var(--text-primary);
}

.chat-main {
  flex: 1;
  min-width: 0;
  min-height: 0;
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
}

/* Input field */
.input-wrapper input {
  width: 100%;
  padding: 10px 90px 10px 14px;
  border: 1px solid var(--border-color);
  border-radius: 999px;
  font-size: 0.96rem;
  background-color: var(--content-bg);
  color: var(--text-primary);
  outline: none;
}

.input-wrapper input:focus {
  border-color: var(--primary-color);
  box-shadow: 0 0 0 2px rgba(124, 77, 255, 0.15);
}

/* Send & voice buttons */
.inner-send,
.inner-voice {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  border: none;
  background: transparent;
  cursor: pointer;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.listening-box {
  background-color: var(--primary-color);
  color: #fff;
  padding: 10px 15px;
  margin: 0.75rem 1rem 0; /* Align above input area */
  border-radius: 8px;
  font-weight: 500;
  font-size: 1rem;
  text-align: center;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  display: flex;
  justify-content: center;
  align-items: center;
}

.dot-animation {
  display: inline-block;
  min-width: 15px; /* Ensure space for three dots */
  margin-left: 5px;
  font-family: monospace; /* Monospace for consistent dot spacing */
  overflow: hidden;
}

/* Style for voice button when active */
.inner-voice.listening-active {
  background-color: #fdd835; /* A noticeable color when active (e.g., yellow) */
  color: #333;
}

.inner-send {
  right: 50px;
  color: var(--primary-color);
}

.inner-voice {
  right: 10px;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background-color: var(--primary-color);
  color: #fff;
}

.inner-voice:disabled,
.inner-send:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.mic-icon.material-symbols-outlined {
  font-size: 20px;
  font-variation-settings: "FILL" 0, "wght" 400, "GRAD" 0, "opsz" 24;
}
</style>
