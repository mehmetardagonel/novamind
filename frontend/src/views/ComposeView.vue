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

            <div v-if="isVoiceActive" class="message ai-message voice-inline">
              <div class="voice-inline-row">
                <span class="voice-inline-dot"></span>
                <span class="voice-inline-label">
                  {{ voiceStatusLabel }}{{ voiceDots }}
                </span>
              </div>
              <div class="voice-inline-wave">
                <span></span>
                <span></span>
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
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
                @click="handleVoiceInput"
                :disabled="isLoading || !activeChat"
                :class="{ 'listening-active': isListening }"
              >
                <span class="material-symbols-outlined mic-icon">
                  {{ isRecording ? "stop" : "mic" }}
                </span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="isVoiceActive" class="voice-overlay" aria-live="polite">
      <div class="voice-orb">
        <span class="voice-orb-core"></span>
        <span class="voice-orb-ring ring-1"></span>
        <span class="voice-orb-ring ring-2"></span>
        <span class="voice-orb-ring ring-3"></span>
      </div>
      <div class="voice-overlay-label">
        {{ voiceStatusLabel }}{{ voiceDots }}
      </div>
      <button class="voice-overlay-stop" @click="handleVoiceInput">
        Stop
      </button>
    </div>
  </div>
</template>

<script>
import { computed, ref, nextTick, onUnmounted, onMounted, watch } from "vue";
import { useAuthStore } from "../stores/auth";
import { useChatStore } from "../stores/chat";
import { sendVoicePrompt } from "@/api/voice";
import { recordUntilSilence } from "@/utils/voiceRecorder";

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
    const activeRecorder = ref(null);
    let dotInterval = null; // For managing the dot animation timer
    const isRecording = ref(false);
    const isSpeaking = ref(false);
    const audioPlayer = new Audio();
    let currentAudioUrl = null;
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

    const isVoiceActive = computed(
      () => isListening.value || isSpeaking.value
    );

    const voiceStatusLabel = computed(() => {
      if (isListening.value) return "Listening";
      if (isSpeaking.value) return "Speaking";
      return "Voice";
    });

    const voiceDots = computed(() =>
      isListening.value ? listeningDots.value : ""
    );

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
    const playReplyAudio = async (blob) => {
      if (currentAudioUrl) {
        URL.revokeObjectURL(currentAudioUrl);
      }
      currentAudioUrl = URL.createObjectURL(blob);
      audioPlayer.src = currentAudioUrl;
      try {
        isSpeaking.value = true;
        await audioPlayer.play();
      } catch (error) {
        isSpeaking.value = false;
        console.error("Failed to play voice response:", error);
      }
    };

    audioPlayer.addEventListener("ended", () => {
      isSpeaking.value = false;
      if (currentAudioUrl) {
        URL.revokeObjectURL(currentAudioUrl);
        currentAudioUrl = null;
      }
    });

    // New function to handle voice input
    const handleVoiceInput = async () => {
      if (isLoading.value || !activeChat.value) return;

      if (isRecording.value) {
        if (activeRecorder.value?.stop) {
          activeRecorder.value.stop();
        }
        return;
      }

      isRecording.value = true;
      isListening.value = true;
      startDotAnimation();

      try {
        const recorder = recordUntilSilence();
        activeRecorder.value = recorder;
        const audioBlob = await recorder.promise;
        activeRecorder.value = null;
        if (!audioBlob || audioBlob.size === 0) {
          return;
        }
        const {
          audioBlob: replyAudio,
          sessionId,
          userTranscript,
          assistantReply,
        } = await sendVoicePrompt(audioBlob, activeChat.value?.sessionId || null);

        const chatId = activeChat.value.id;
        if (sessionId) {
          await chatStore.setSessionId(chatId, sessionId);
        }
        if (userTranscript) {
          chatStore.appendMessage(chatId, {
            role: "user",
            text: userTranscript.trim(),
            emails: null,
          });
        }
        if (assistantReply) {
          const extracted = extractJsonFromText(assistantReply);
          let displayText = extracted.textBefore;
          if (!displayText && extracted.json && extracted.json.length > 0) {
            displayText = `Found ${extracted.json.length} email(s):`;
          } else if (!displayText && !extracted.json) {
            displayText = assistantReply.trim();
          }

          chatStore.appendMessage(chatId, {
            role: "bot",
            text: displayText,
            emails: extracted.json,
          });

          if (!extracted.json && replyAudio) {
            await playReplyAudio(replyAudio);
          }
        }
        scrollToBottom();
      } catch (error) {
        console.error("Voice request failed:", error);
        window.alert("Voice request failed");
      } finally {
        isRecording.value = false;
        isListening.value = false;
        stopDotAnimation();
        activeRecorder.value = null;
        if (!isListening.value) {
          isSpeaking.value = false;
        }
      }
    };

    // Clear interval when component is destroyed
    onUnmounted(() => {
      stopDotAnimation();
      if (currentAudioUrl) {
        URL.revokeObjectURL(currentAudioUrl);
        currentAudioUrl = null;
      }
      audioPlayer.pause();
      audioPlayer.src = "";
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
      isRecording,
      isSpeaking,
      isVoiceActive,
      voiceStatusLabel,
      voiceDots,
      chats,
      activeChatId,
      activeChat,
      activeMessages,
      sendMessage,
      formatBody,
      formatMessageText,
      historyContainer,
      handleVoiceInput,
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
  --primary-color: #10a37f;
  --primary-color-light: rgba(16, 163, 127, 0.16);
  --border-color: rgba(17, 24, 39, 0.12);
  --light-border-color: rgba(17, 24, 39, 0.08);
  --hover-bg: rgba(17, 24, 39, 0.05);
  --content-bg: rgba(255, 255, 255, 0.9);
  --text-primary: #1f2328;
  --text-secondary: #667085;
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 0 1.5rem 1.5rem 0;
  font-family: "IBM Plex Sans", "Söhne", sans-serif;
  background: radial-gradient(
      circle at top right,
      rgba(16, 163, 127, 0.14),
      transparent 55%
    ),
    radial-gradient(
      circle at bottom left,
      rgba(17, 24, 39, 0.08),
      transparent 45%
    ),
    #f6f7f4;
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
  border-radius: 18px;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.78);
  backdrop-filter: blur(12px);
}

/* Scrollable messages */
.chat-history {
  flex-grow: 1;
  padding: 1.75rem 1.5rem 1rem;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* Message bubbles */
.message {
  max-width: 760px;
  width: fit-content;
  padding: 0;
  border-radius: 16px;
  line-height: 1.55;
  font-size: 0.96rem;
  box-shadow: none;
  word-wrap: break-word;
}

.user-message {
  align-self: flex-end;
  background-color: var(--primary-color);
  color: #fff;
  padding: 10px 14px;
  border-bottom-right-radius: 6px;
}

.ai-message {
  align-self: flex-start;
  background-color: transparent;
  color: var(--text-primary);
  border: none;
  border-bottom-left-radius: 6px;
}

.message-text {
  margin: 0;
  display: inline-block;
  padding: 10px 14px;
  border-radius: 16px;
  border: 1px solid var(--light-border-color);
  background: rgba(17, 24, 39, 0.04);
}

.user-message .message-text {
  padding: 0;
  border: none;
  background: transparent;
  color: inherit;
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
  box-shadow: 0 0 0 3px rgba(16, 163, 127, 0.18);
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

.voice-inline {
  align-self: flex-start;
  background: rgba(17, 24, 39, 0.06);
  border: 1px solid rgba(17, 24, 39, 0.1);
  padding: 10px 14px;
  border-radius: 14px;
  max-width: 320px;
}

.voice-inline-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.9rem;
  font-weight: 500;
  color: var(--text-primary);
}

.voice-inline-dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: var(--primary-color);
  box-shadow: 0 0 0 6px rgba(16, 163, 127, 0.12);
  animation: voice-pulse 1.2s ease-in-out infinite;
}

.voice-inline-wave {
  display: flex;
  gap: 4px;
  margin-top: 8px;
  height: 18px;
}

.voice-inline-wave span {
  width: 4px;
  height: 100%;
  background: rgba(16, 163, 127, 0.8);
  border-radius: 999px;
  animation: voice-wave 1s ease-in-out infinite;
}

.voice-inline-wave span:nth-child(2) {
  animation-delay: 0.15s;
}
.voice-inline-wave span:nth-child(3) {
  animation-delay: 0.3s;
}
.voice-inline-wave span:nth-child(4) {
  animation-delay: 0.45s;
}
.voice-inline-wave span:nth-child(5) {
  animation-delay: 0.6s;
}

.voice-overlay {
  position: fixed;
  inset: 0;
  background: radial-gradient(
      circle at top,
      rgba(16, 163, 127, 0.25),
      transparent 60%
    ),
    rgba(9, 11, 13, 0.9);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 18px;
  z-index: 50;
}

.voice-orb {
  position: relative;
  width: 140px;
  height: 140px;
  display: grid;
  place-items: center;
}

.voice-orb-core {
  width: 54px;
  height: 54px;
  border-radius: 50%;
  background: radial-gradient(
    circle,
    rgba(16, 163, 127, 1),
    rgba(16, 163, 127, 0.65)
  );
  box-shadow: 0 0 24px rgba(16, 163, 127, 0.55);
  animation: orb-core 1.6s ease-in-out infinite;
}

.voice-orb-ring {
  position: absolute;
  width: 100%;
  height: 100%;
  border-radius: 50%;
  border: 2px solid rgba(16, 163, 127, 0.35);
  animation: orb-ring 2.4s ease-out infinite;
}

.voice-orb-ring.ring-2 {
  animation-delay: 0.5s;
}

.voice-orb-ring.ring-3 {
  animation-delay: 1s;
}

.voice-overlay-label {
  color: #f3f4f6;
  font-size: 1rem;
  letter-spacing: 0.3px;
}

.voice-overlay-stop {
  background: transparent;
  color: #f3f4f6;
  border: 1px solid rgba(255, 255, 255, 0.3);
  padding: 8px 18px;
  border-radius: 999px;
  cursor: pointer;
  font-weight: 600;
  transition: transform 0.2s ease, border-color 0.2s ease;
}

.voice-overlay-stop:hover {
  transform: translateY(-1px);
  border-color: rgba(255, 255, 255, 0.6);
}

@keyframes voice-pulse {
  0%,
  100% {
    transform: scale(1);
  }
  50% {
    transform: scale(1.15);
  }
}

@keyframes voice-wave {
  0%,
  100% {
    transform: scaleY(0.35);
  }
  50% {
    transform: scaleY(1);
  }
}

@keyframes orb-core {
  0%,
  100% {
    transform: scale(0.9);
  }
  50% {
    transform: scale(1.1);
  }
}

@keyframes orb-ring {
  0% {
    transform: scale(0.7);
    opacity: 0.7;
  }
  100% {
    transform: scale(1.15);
    opacity: 0;
  }
}

/* Style for voice button when active */
.inner-voice.listening-active {
  background-color: #10a37f;
  color: #fff;
  box-shadow: 0 0 0 4px rgba(16, 163, 127, 0.2);
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
