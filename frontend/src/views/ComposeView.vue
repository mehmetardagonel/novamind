<template>
  <div class="compose-view adjusted-view">
    <!-- Chat Split: Sidebar + Main -->
    <div class="chat-split">
      <!-- Overlay (Outside sidebar for proper z-index) -->
      <div
        class="chat-sidebar-overlay"
        :class="{ visible: sidebarOpen }"
        @click="sidebarOpen = false"
      ></div>

      <!-- Chat Sidebar (Left) -->
      <div class="chat-sidebar" :class="{ open: sidebarOpen }">
        <div class="chat-sidebar-content">
          <div class="chat-sidebar-header">
            <h3>Chats</h3>
            <button @click="handleNewChat" class="btn-new-chat">
              <span class="material-symbols-outlined">add</span>
              New
            </button>
          </div>

          <div class="chat-list">
            <div
              v-for="chat in chats"
              :key="chat.id"
              class="chat-list-item"
              :class="{ active: chat.id === activeChatId }"
              @click="handleChatSwitch(chat.id)"
            >
              <div class="chat-list-item-content">
                <div class="chat-list-item-title">{{ chat.title }}</div>
                <div class="chat-list-item-time">{{ formatChatTime(chat.updatedAt) }}</div>
              </div>
              <button
                class="chat-delete-btn"
                @click.stop="handleDeleteChat(chat.id)"
                v-if="chats.length > 1"
              >
                ×
              </button>
            </div>

            <div v-if="chats.length === 0" class="chat-list-empty">
              <p>No chats yet</p>
              <button @click="handleNewChat" class="btn-create-first">
                Create your first chat
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Chat Main (Right) -->
      <div class="chat-main">
        <!-- Mobile: Hamburger menu -->
        <button class="btn-toggle-sidebar" @click="sidebarOpen = !sidebarOpen">
          <span class="material-symbols-outlined">{{ sidebarOpen ? 'close' : 'menu' }}</span>
        </button>

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

            <!-- Voice Thinking Indicator -->
            <div v-if="isVoiceThinking" class="message ai-message voice-inline">
              <div class="voice-inline-row">
                <span class="voice-inline-dot"></span>
                <span class="voice-inline-label">
                  Thinking{{ voiceDots }}
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
                :disabled="isLoading || isListening"
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

              <!-- Voice button -->
              <button
                class="inner-voice"
                @click="handleVoiceInput"
                :disabled="isLoading"
                :class="{ 'listening-active': isListening || isRecording }"
              >
                <span class="material-symbols-outlined mic-icon">mic</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Voice Overlay (Full Screen) - Only for Listening -->
    <div v-if="isListening" class="voice-overlay" aria-live="polite">
      <div class="voice-orb">
        <span class="voice-orb-core"></span>
        <span class="voice-orb-ring ring-1"></span>
        <span class="voice-orb-ring ring-2"></span>
        <span class="voice-orb-ring ring-3"></span>
      </div>
      <div class="voice-overlay-label">
        Listening{{ voiceDots }}
      </div>
      <button
        class="voice-overlay-stop"
        @click="handleVoiceInput"
      >
        Stop
      </button>
    </div>
  </div>
</template>

<script>
import { ref, computed, nextTick, onMounted, onUnmounted, watch } from "vue";
import { useAuthStore } from "../stores/auth";
import { useChatStore } from "../stores/chat";
import { getApiUrl } from "../utils/platformHelper";
import { recordUntilSilence } from "../utils/voiceRecorder";
import { sendVoicePrompt } from "../api/voice";

export default {
  name: "ComposeView",
  setup() {
    const authStore = useAuthStore();
    const chatStore = useChatStore();

    const userPrompt = ref("");
    const isLoading = ref(false);
    const historyContainer = ref(null);
    const isListening = ref(false);
    const listeningDots = ref("");
    const sidebarOpen = ref(false);
    const isRecording = ref(false);
    const isVoiceThinking = ref(false);
    const isSpeaking = ref(false);
    const activeRecorder = ref(null);
    let dotInterval = null;
    let audioPlayer = null;
    let currentAudioUrl = null;

    const API_BASE_URL = getApiUrl();
    const normalizedBase = API_BASE_URL.endsWith("/")
      ? API_BASE_URL.slice(0, -1)
      : API_BASE_URL;
    const API_URL = `${normalizedBase}/chat`;
    const VOICE_RESPONSE_URL = `${normalizedBase}/voice/response`;

    // Computed
    const chats = computed(() => chatStore.chats);
    const activeChatId = computed(() => chatStore.activeChatId);
    const activeChat = computed(() => chatStore.activeChat);

    const chatHistory = computed(() => {
      return activeChat.value?.messages || [];
    });

    const isVoiceActive = computed(
      () => isListening.value || isVoiceThinking.value || isSpeaking.value
    );

    const voiceStatusLabel = computed(() => {
      if (isListening.value) return "Listening";
      if (isVoiceThinking.value) return "Thinking";
      if (isSpeaking.value) return "Speaking";
      return "Voice";
    });

    const voiceDots = computed(() =>
      isListening.value || isVoiceThinking.value ? listeningDots.value : ""
    );

    // Initialize chat store
    onMounted(async () => {
      await chatStore.initialize();
      scrollToBottom();

      // Initialize audio player for voice responses
      audioPlayer = new Audio();
      audioPlayer.addEventListener('ended', () => {
        isSpeaking.value = false;
        if (currentAudioUrl) {
          URL.revokeObjectURL(currentAudioUrl);
          currentAudioUrl = null;
        }
      });
    });

    // Watch active chat changes
    watch(activeChatId, () => {
      scrollToBottom();
      sidebarOpen.value = false; // Close sidebar on mobile after switching
    });

    // Helper functions for email extraction
    const isEmailArray = (parsed) => {
      if (!Array.isArray(parsed)) return false;
      if (parsed.length === 0) return true;
      const first = parsed[0];
      if (!first || typeof first !== "object") return false;
      return (
        Object.prototype.hasOwnProperty.call(first, "subject") ||
        Object.prototype.hasOwnProperty.call(first, "from") ||
        Object.prototype.hasOwnProperty.call(first, "sender") ||
        Object.prototype.hasOwnProperty.call(first, "date") ||
        Object.prototype.hasOwnProperty.call(first, "body")
      );
    };

    const normalizeEmailsPayload = (parsed) => {
      if (isEmailArray(parsed)) {
        return { emails: parsed, insights: null };
      }
      if (parsed && typeof parsed === "object") {
        const emails = parsed.emails;
        if (isEmailArray(emails)) {
          const insights =
            typeof parsed.insights === "string"
              ? parsed.insights
              : typeof parsed.summary === "string"
              ? parsed.summary
              : typeof parsed.message === "string"
              ? parsed.message
              : null;
          return { emails, insights };
        }
      }
      return null;
    };

    const tryParseEmailsJson = (raw) => {
      try {
        const parsed = JSON.parse(raw);
        return normalizeEmailsPayload(parsed);
      } catch {
        return null;
      }
    };

    const stripJsonBlocks = (text) => {
      if (!text) return "";
      return text
        .replace(/```[\s\S]*?```/g, (block) => {
          const inner = block
            .replace(/^```\s*[a-z]*\s*/i, "")
            .replace(/```$/, "")
            .trim();
          if (!inner) return "";
          try {
            JSON.parse(inner);
            return "";
          } catch {
            return block;
          }
        })
        .trim();
    };

    const cleanTextBeforeJson = (text) => {
      if (!text) return "";
      return text
        .replace(/```/g, "")
        .replace(/\bjson\b/gi, "")
        .replace(/\s+/g, " ")
        .trim()
        .replace(/[:\s]+$/, "");
    };

    const findBalancedJson = (text, startIndex, openChar, closeChar) => {
      let depth = 0;
      let inString = false;
      let escape = false;
      for (let i = startIndex; i < text.length; i += 1) {
        const ch = text[i];
        if (inString) {
          if (escape) {
            escape = false;
          } else if (ch === "\\") {
            escape = true;
          } else if (ch === '"') {
            inString = false;
          }
          continue;
        }
        if (ch === '"') {
          inString = true;
          continue;
        }
        if (ch === openChar) {
          depth += 1;
        } else if (ch === closeChar) {
          depth -= 1;
          if (depth === 0) {
            return text.slice(startIndex, i + 1);
          }
        }
      }
      return null;
    };

    const findFirstBalancedJson = (text, openChar, closeChar) => {
      let idx = text.indexOf(openChar);
      while (idx !== -1) {
        const candidate = findBalancedJson(text, idx, openChar, closeChar);
        if (candidate) {
          return { candidate, index: idx };
        }
        idx = text.indexOf(openChar, idx + 1);
      }
      return null;
    };

    const extractJsonFromText = (text) => {
      const result = { textBefore: "", emails: null, insights: null };
      if (!text) return result;

      const tryCandidate = (candidate, index) => {
        const cleaned = candidate.replace(/^json\s*/i, "").trim();
        const payload = tryParseEmailsJson(cleaned);
        if (!payload) return false;
        result.emails = payload.emails;
        result.insights = payload.insights;
        result.textBefore = cleanTextBeforeJson(text.slice(0, index || 0).trim());
        return true;
      };

      // 1) Prefer fenced JSON blocks: ```json ... ```
      const fenceRegex = /```\s*json\s*([\s\S]*?)\s*```/gi;
      for (const match of text.matchAll(fenceRegex)) {
        const candidate = (match[1] || "").trim();
        if (tryCandidate(candidate, match.index)) {
          return result;
        }
      }

      // 2) Fallback: any fenced block that contains email array
      const anyFenceRegex = /```\s*([\s\S]*?)\s*```/g;
      for (const match of text.matchAll(anyFenceRegex)) {
        const candidate = (match[1] || "").trim();
        if (tryCandidate(candidate, match.index)) {
          return result;
        }
      }

      // 3) Direct parse if whole response is JSON
      const directPayload = tryParseEmailsJson(text.trim());
      if (directPayload) {
        result.emails = directPayload.emails;
        result.insights = directPayload.insights;
        return result;
      }

      // 4) Balanced JSON array substring
      const arrayMatch = findFirstBalancedJson(text, "[", "]");
      if (arrayMatch && tryCandidate(arrayMatch.candidate, arrayMatch.index)) {
        return result;
      }

      // 5) Balanced JSON object substring
      const objectMatch = findFirstBalancedJson(text, "{", "}");
      if (objectMatch && tryCandidate(objectMatch.candidate, objectMatch.index)) {
        return result;
      }

      result.textBefore = stripJsonBlocks(text);
      return result;
    };

    const isImportantEmail = (email) => {
      if (!email || typeof email !== "object") return false;
      if (email.is_important) return true;
      if (email.ml_prediction === "important") return true;
      const labels = Array.isArray(email.label_ids) ? email.label_ids : [];
      return labels.some((label) => String(label).toUpperCase() === "IMPORTANT");
    };

    // Format chat time
    const formatChatTime = (dateString) => {
      if (!dateString) return '';
      const date = new Date(dateString);
      const now = new Date();
      const diff = now - date;

      // Less than 1 minute
      if (diff < 60000) return 'Just now';

      // Less than 1 hour
      if (diff < 3600000) {
        const mins = Math.floor(diff / 60000);
        return `${mins}m ago`;
      }

      // Less than 1 day
      if (diff < 86400000) {
        const hours = Math.floor(diff / 3600000);
        return `${hours}h ago`;
      }

      // Less than 7 days
      if (diff < 604800000) {
        const days = Math.floor(diff / 86400000);
        return `${days}d ago`;
      }

      // Older - show date
      return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    };

    const formatBody = (text) => {
      if (!text) return "";
      return text.replace(/\n/g, "<br>");
    };

    const scrollToBottom = () => {
      nextTick(() => {
        if (historyContainer.value) {
          historyContainer.value.scrollTop = historyContainer.value.scrollHeight;
        }
      });
    };

    const sendMessage = async () => {
      if (!userPrompt.value.trim() || isLoading.value || !activeChat.value) return;

      const messageText = userPrompt.value.trim();
      const currentChatId = activeChat.value.id;

      // Append user message
      await chatStore.appendMessage(currentChatId, {
        role: "user",
        text: messageText,
        emails: null
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

        if (!response.ok) throw new Error("API request failed");

        const data = await response.json();

        // Update backend session ID if provided
        if (data.session_id && data.session_id !== activeChat.value.sessionId) {
          await chatStore.setSessionId(currentChatId, data.session_id);
        }

        // Extract emails from response
        const extracted = extractJsonFromText(data.response);

        // Append bot response
        await chatStore.appendMessage(currentChatId, {
          role: "bot",
          text: extracted.textBefore,
          emails: extracted.json
        });

        scrollToBottom();
      } catch (error) {
        console.error("Error:", error);
        await chatStore.appendMessage(currentChatId, {
          role: "bot",
          text: "Sorry, an error occurred connecting to the server. Please ensure the backend is running.",
          emails: null
        });
        scrollToBottom();
      } finally {
        isLoading.value = false;
      }
    };

    const startDotAnimation = () => {
      listeningDots.value = "";
      dotInterval = setInterval(() => {
        listeningDots.value =
          listeningDots.value.length < 3 ? listeningDots.value + "." : "";
      }, 500);
    };

    const stopDotAnimation = () => {
      if (dotInterval) {
        clearInterval(dotInterval);
        dotInterval = null;
      }
      listeningDots.value = "";
    };

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
        isRecording.value = false;
        isListening.value = false;
        isVoiceThinking.value = true;

        if (!audioBlob || audioBlob.size === 0) {
          return;
        }

        isLoading.value = true;

        const {
          audioBlob: replyAudio,
          sessionId,
          userTranscript,
          assistantReply,
          responseId,
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

        if (!userTranscript && !assistantReply && !replyAudio) {
          chatStore.appendMessage(chatId, {
            role: "bot",
            text: "I didn't catch that. Please try again.",
            emails: null,
          });
        }

        if (assistantReply || responseId) {
          let responseText = assistantReply || "";
          let extracted = extractJsonFromText(responseText);

          if (responseId) {
            try {
              const res = await fetch(
                `${VOICE_RESPONSE_URL}/${encodeURIComponent(responseId)}`,
                {
                  headers: {
                    "X-User-Id": authStore.user?.id,
                  },
                }
              );
              if (res.ok) {
                const payload = await res.json();
                responseText = payload.response_text || responseText;
                if (Array.isArray(payload.emails)) {
                  extracted = {
                    textBefore: payload.text_before || "",
                    emails: payload.emails,
                    insights:
                      typeof payload.insights === "string"
                        ? payload.insights
                        : null,
                  };
                } else {
                  extracted = extractJsonFromText(responseText);
                }
              }
            } catch (error) {
              console.warn("Failed to load voice response payload:", error);
            }
          }

          let displayText = extracted.textBefore;
          if (extracted.insights) {
            displayText = displayText
              ? `${displayText}\n\n${extracted.insights}`
              : extracted.insights;
          }
          if (!displayText && Array.isArray(extracted.emails)) {
            displayText = extracted.emails.length
              ? `Found ${extracted.emails.length} email(s).`
              : "No emails found.";
          } else if (!displayText) {
            displayText = stripJsonBlocks(responseText).trim();
          }

          chatStore.appendMessage(chatId, {
            role: "bot",
            text: displayText,
            emails: extracted.emails,
          });

          if (replyAudio) {
            await playReplyAudio(replyAudio);
          }
        }

        scrollToBottom();
      } catch (error) {
        console.error("Voice request failed:", error);
        alert("Voice request failed");
      } finally {
        isRecording.value = false;
        isListening.value = false;
        isVoiceThinking.value = false;
        isLoading.value = false;
        stopDotAnimation();
        activeRecorder.value = null;
        if (!isListening.value) {
          isSpeaking.value = false;
        }
      }
    };

    const handleNewChat = async () => {
      await chatStore.createChat();
      sidebarOpen.value = false; // Close sidebar on mobile
    };

    const handleDeleteChat = async (chatId) => {
      if (chats.value.length <= 1) return;

      if (confirm('Delete this chat?')) {
        await chatStore.deleteChat(chatId);
      }
    };

    const handleChatSwitch = async (chatId) => {
      await chatStore.setActiveChat(chatId);
    };

    onUnmounted(() => {
      stopDotAnimation();
    });

    return {
      userPrompt,
      isLoading,
      isListening,
      isRecording,
      isVoiceThinking,
      isSpeaking,
      listeningDots,
      chatHistory,
      sendMessage,
      formatBody,
      historyContainer,
      handleVoiceInput,
      sidebarOpen,
      chats,
      activeChatId,
      handleNewChat,
      handleDeleteChat,
      handleChatSwitch,
      formatChatTime
    };
  },
};
</script>

<style scoped>
.compose-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 0;
}

/* Chat Split Layout */
.chat-split {
  display: flex;
  height: 100%;
  position: relative;
}

/* ===== OVERLAY ===== */
.chat-sidebar-overlay {
  display: none;
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.4);
  z-index: 999;
  opacity: 0;
  transition: opacity 0.3s ease;
}

.chat-sidebar-overlay.visible {
  display: block;
  opacity: 1;
}

/* ===== CHAT SIDEBAR (Left) ===== */
.chat-sidebar {
  width: 260px;
  background: linear-gradient(180deg, #ffffff 0%, #f8f9fa 100%);
  border-right: 1px solid #e0e6ed;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  overflow: hidden;
  box-shadow: 2px 0 12px rgba(0, 0, 0, 0.05);
}

.chat-sidebar-content {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.chat-sidebar-header {
  padding: 1.25rem 1rem;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
  box-shadow: 0 2px 8px rgba(102, 126, 234, 0.2);
}

.chat-sidebar-header h3 {
  margin: 0;
  font-size: 1.2rem;
  font-weight: 700;
  color: white;
  letter-spacing: 0.5px;
}

.btn-new-chat {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.5rem 0.9rem;
  background: rgba(255, 255, 255, 0.25);
  backdrop-filter: blur(10px);
  color: white;
  border: 1px solid rgba(255, 255, 255, 0.3);
  border-radius: 8px;
  cursor: pointer;
  font-size: 0.85rem;
  font-weight: 600;
  transition: all 0.2s;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1);
}

.btn-new-chat:hover {
  background: rgba(255, 255, 255, 0.35);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.btn-new-chat .material-symbols-outlined {
  font-size: 18px;
}

/* Chat List */
.chat-list {
  flex: 1;
  overflow-y: auto;
  padding: 0.5rem;
}

.chat-list-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.85rem;
  margin-bottom: 0.4rem;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
  border: 1px solid transparent;
}

.chat-list-item:hover {
  background: linear-gradient(135deg, #f8f9ff 0%, #f0f2ff 100%);
  border-color: #e0e6ff;
  transform: translateX(2px);
  box-shadow: 0 2px 8px rgba(102, 126, 234, 0.08);
}

.chat-list-item.active {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-color: #667eea;
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
}

.chat-list-item-content {
  flex: 1;
  overflow: hidden;
}

.chat-list-item-title {
  font-size: 0.9rem;
  font-weight: 600;
  color: #2d3748;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 0.25rem;
  transition: color 0.2s;
}

.chat-list-item.active .chat-list-item-title {
  color: white;
  font-weight: 700;
}

.chat-list-item-time {
  font-size: 0.75rem;
  color: #718096;
  transition: color 0.2s;
}

.chat-list-item.active .chat-list-item-time {
  color: rgba(255, 255, 255, 0.85);
}

.chat-delete-btn {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: none;
  background: transparent;
  color: #a0aec0;
  font-size: 1.5rem;
  line-height: 1;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: all 0.2s;
  flex-shrink: 0;
}

.chat-list-item:hover .chat-delete-btn {
  opacity: 1;
}

.chat-list-item.active .chat-delete-btn {
  color: rgba(255, 255, 255, 0.8);
  opacity: 1;
}

.chat-delete-btn:hover {
  background: rgba(239, 68, 68, 0.15);
  color: #ef4444;
  transform: scale(1.1);
}

.chat-list-item.active .chat-delete-btn:hover {
  background: rgba(255, 255, 255, 0.2);
  color: white;
}

.chat-list-empty {
  text-align: center;
  padding: 2rem 1rem;
  color: var(--text-secondary, #666);
}

.btn-create-first {
  margin-top: 1rem;
  padding: 0.5rem 1rem;
  background: var(--primary-color, #6c63ff);
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.85rem;
}

/* ===== CHAT MAIN (Right) ===== */
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
}

.btn-toggle-sidebar {
  display: none; /* Hidden on desktop */
}

.chat-container {
  display: flex;
  flex-direction: column;
  flex-grow: 1;
  border: 1px solid var(--border-color);
  border-radius: 12px;
  overflow: hidden;
  background-color: var(--content-bg);
  margin: 0 1.5rem 1.5rem 0;
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

/* Email cards */
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

/* Voice Overlay - Full Screen */
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
  font-size: 1.5rem;
  font-weight: 600;
  letter-spacing: 0.5px;
  margin-top: 8px;
  text-align: center;
}

.voice-overlay-stop {
  background: transparent;
  color: #f3f4f6;
  border: 1px solid rgba(255, 255, 255, 0.3);
  padding: 10px 24px;
  border-radius: 999px;
  cursor: pointer;
  font-weight: 600;
  font-size: 1rem;
  transition: transform 0.2s ease, border-color 0.2s ease;
}

.voice-overlay-stop:hover {
  transform: translateY(-1px);
  border-color: rgba(255, 255, 255, 0.6);
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

/* Voice Inline Thinking Badge */
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
  background: #10a37f;
  box-shadow: 0 0 0 6px rgba(16, 163, 127, 0.12);
  animation: voice-pulse 1.2s ease-in-out infinite;
}

.voice-inline-label {
  font-size: 0.95rem;
  font-weight: 500;
}

.voice-inline-wave {
  display: flex;
  gap: 4px;
  margin-top: 8px;
  height: 18px;
  align-items: flex-end;
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

@keyframes voice-pulse {
  0%, 100% {
    transform: scale(1);
  }
  50% {
    transform: scale(1.15);
  }
}

@keyframes voice-wave {
  0%, 100% {
    transform: scaleY(0.35);
  }
  50% {
    transform: scaleY(1);
  }
}

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

/* ===== MOBILE RESPONSIVE ===== */
@media (max-width: 768px) {
  .chat-split {
    flex-direction: row;
  }

  /* Sidebar: Full-screen overlay on mobile */
  .chat-sidebar {
    position: fixed;
    left: 0;
    top: 0;
    width: 85%;
    max-width: 320px;
    height: 100vh;
    z-index: 1000;
    transform: translateX(-100%);
    transition: transform 0.3s ease;
    box-shadow: 4px 0 24px rgba(102, 126, 234, 0.15);
  }

  .chat-sidebar.open {
    transform: translateX(0);
  }

  /* Show hamburger button on mobile */
  .btn-toggle-sidebar {
    display: flex;
    position: absolute;
    top: 1rem;
    left: 1rem;
    z-index: 10;
    width: 48px;
    height: 48px;
    border-radius: 50%;
    border: none;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    box-shadow: 0 4px 16px rgba(102, 126, 234, 0.4);
    transition: all 0.2s;
  }

  .btn-toggle-sidebar:active {
    transform: scale(0.95);
  }

  .btn-toggle-sidebar .material-symbols-outlined {
    font-size: 24px;
  }

  .chat-main {
    width: 100%;
    flex: 1;
  }

  .chat-container {
    margin: 0;
    border-radius: 0;
    border: none;
  }

  .message {
    max-width: 85%;
  }
}

@media (max-width: 480px) {
  .chat-sidebar {
    width: 90%;
  }

  .btn-toggle-sidebar {
    top: 0.75rem;
    left: 0.75rem;
    width: 40px;
    height: 40px;
  }

  .chat-history {
    padding: 0.75rem;
  }

  .message {
    font-size: 0.9rem;
    max-width: 90%;
  }
}
</style>
