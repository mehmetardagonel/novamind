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

              <ChatEmailList
                v-if="message.emails && message.emails.length > 0"
                :emails="message.emails"
              />
            </div>

            <div
              v-if="isLoading && !isVoiceActive"
              class="message ai-message loading-indicator"
            >
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
              <!-- Normal chat input -->
              <template v-if="!isVoiceActive && !isRecording && !isListening">
                <input
                  type="text"
                  placeholder="Type your prompt here..."
                  v-model="userPrompt"
                  @keyup.enter="sendMessage"
                  :disabled="isLoading || isListening || !activeChat"
                />

                <button
                  class="inner-send"
                  @click="sendMessage"
                  :disabled="
                    !userPrompt.trim() ||
                    isLoading ||
                    isListening ||
                    !activeChat
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
              </template>

              <!-- Voice recorder bar (replaces the input) -->
              <template v-else>
                <div class="voice-bar" :class="{ recording: isRecording }">
                  <div class="voice-bar-left">
                    <div class="voice-pill">
                      <span
                        class="voice-pill-dot"
                        :class="{ live: isRecording || isListening }"
                      ></span>

                      <div class="voice-pill-text">
                        <div class="voice-pill-title">
                          {{ voiceStatusLabel }}{{ voiceDots }}
                        </div>
                        <div class="voice-pill-sub">
                          {{
                            isRecording
                              ? "Tap stop to finish"
                              : "Processing audio…"
                          }}
                        </div>
                      </div>
                    </div>
                  </div>

                  <div class="voice-bar-wave" aria-hidden="true">
                    <span></span><span></span><span></span><span></span
                    ><span></span> <span></span><span></span><span></span
                    ><span></span><span></span>
                  </div>

                  <!-- SAME click handler, just styled as a stop button while recording -->
                  <button
                    class="voice-bar-stop"
                    @click="handleVoiceInput"
                    :disabled="isLoading || !activeChat"
                    :class="{ active: isRecording }"
                    title="Stop recording"
                  >
                    <span class="material-symbols-outlined">
                      {{ isRecording ? "stop" : "mic" }}
                    </span>
                  </button>
                </div>

                <!-- Keep mic button behavior available even in voice bar (optional, but nice) -->
              </template>
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
import { sendVoicePrompt } from "@/api/voice";
import { recordUntilSilence } from "@/utils/voiceRecorder";
import ChatEmailList from "@/components/ChatEmailList.vue";

export default {
  name: "ComposeView",
  components: { ChatEmailList },
  setup() {
    const authStore = useAuthStore();
    const chatStore = useChatStore();
    const userPrompt = ref("");
    const isLoading = ref(false);
    const historyContainer = ref(null);
    const isListening = ref(false); // Listening state for voice
    const isVoiceThinking = ref(false); // Waiting on voice response
    const listeningDots = ref(""); // Dot animation state
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
    const VOICE_RESPONSE_URL = `${normalizedBase}/voice/response`;

    const chats = computed(() => chatStore.chats);
    const activeChatId = computed(() => chatStore.activeChatId);
    const activeChat = computed(() => chatStore.activeChat);
    const activeMessages = computed(() => activeChat.value?.messages || []);

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

    const formatBody = (text) => {
      if (!text) return "";
      return text.replace(/\n/g, "<br>");
    };

    const isImportantEmail = (email) => {
      if (!email || typeof email !== "object") return false;
      if (email.is_important) return true;
      if (email.ml_prediction === "important") return true;
      const labels = Array.isArray(email.label_ids) ? email.label_ids : [];
      return labels.some(
        (label) => String(label).toUpperCase() === "IMPORTANT"
      );
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

    const stripEmailBlocks = (text) => {
      if (!text) return "";
      const marker = "# Email #1";
      const idx = text.indexOf(marker);
      if (idx === -1) return text;
      return text.slice(0, idx).trim();
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
        result.textBefore = cleanTextBeforeJson(
          text.slice(0, index || 0).trim()
        );
        return true;
      };

      // 1) Prefer fenced JSON blocks: ```json ... ``` (with or without newline after json)
      const fenceRegex = /```\s*json\s*([\s\S]*?)\s*```/gi;
      for (const match of text.matchAll(fenceRegex)) {
        const candidate = (match[1] || "").trim();
        if (tryCandidate(candidate, match.index)) {
          return result;
        }
      }

      // 2) Fallback: any fenced block that happens to contain the email array
      const anyFenceRegex = /```\s*([\s\S]*?)\s*```/g;
      for (const match of text.matchAll(anyFenceRegex)) {
        const candidate = (match[1] || "").trim();
        if (tryCandidate(candidate, match.index)) {
          return result;
        }
      }

      // 3) Direct parse if the whole response is JSON
      const directPayload = tryParseEmailsJson(text.trim());
      if (directPayload) {
        result.emails = directPayload.emails;
        result.insights = directPayload.insights;
        return result;
      }

      // 4) Locate a balanced JSON array substring and try parsing it
      const arrayMatch = findFirstBalancedJson(text, "[", "]");
      if (arrayMatch && tryCandidate(arrayMatch.candidate, arrayMatch.index)) {
        return result;
      }

      // 5) Locate a balanced JSON object substring and try parsing it
      const objectMatch = findFirstBalancedJson(text, "{", "}");
      if (
        objectMatch &&
        tryCandidate(objectMatch.candidate, objectMatch.index)
      ) {
        return result;
      }

      result.textBefore = stripJsonBlocks(text);
      return result;
    };

    const scrollToBottom = () => {
      nextTick(() => {
        if (historyContainer.value) {
          historyContainer.value.scrollTo({
            top: historyContainer.value.scrollHeight,
            behavior: "smooth",
          });
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
        const providedEmails = Array.isArray(data.emails) ? data.emails : null;
        const extracted = providedEmails
          ? { textBefore: "", emails: providedEmails, insights: null }
          : extractJsonFromText(responseText);

        // Ensure we always have some text to display
        let displayText = extracted.textBefore;
        if (extracted.insights) {
          displayText = displayText
            ? `${displayText}\n\n${extracted.insights}`
            : extracted.insights;
        }
        const cleanedResponse = stripJsonBlocks(stripEmailBlocks(responseText)).trim();
        if (!displayText && cleanedResponse) {
          displayText = cleanedResponse;
        }
        if (!displayText && Array.isArray(extracted.emails)) {
          displayText = extracted.emails.length
            ? `Found ${extracted.emails.length} email(s).`
            : "No emails found.";
        } else if (!displayText) {
          displayText = cleanedResponse || "I processed your request.";
        }

        chatStore.appendMessage(chatId, {
          role: "bot",
          text: displayText,
          emails: extracted.emails,
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
        } = await sendVoicePrompt(
          audioBlob,
          activeChat.value?.sessionId || null
        );

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
          const cleanedResponse = stripJsonBlocks(stripEmailBlocks(responseText)).trim();
          if (!displayText && cleanedResponse) {
            displayText = cleanedResponse;
          }
          if (!displayText && Array.isArray(extracted.emails)) {
            displayText = extracted.emails.length
              ? `Found ${extracted.emails.length} email(s).`
              : "No emails found.";
          } else if (!displayText) {
            displayText = cleanedResponse;
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
        window.alert("Voice request failed");
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
      isVoiceThinking,
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
      isImportantEmail,
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
/* =========================================================
   ComposeView
   - Uses MainApp theme variables (dark/light) automatically
   - Keeps blue accent (#6c63ff)
   ========================================================= */

.compose-view {
  /* Only keep accent local; everything else comes from MainApp */
  --cv-primary: #6c63ff;
  --cv-primary-light: rgba(108, 99, 255, 0.16);

  /* Pull from MainApp variables if present, otherwise fallback */
  --cv-app-bg: var(--app-bg, #f6f7f4);
  --cv-content-bg: var(--content-bg, rgba(255, 255, 255, 0.9));
  --cv-border: var(--border-color, rgba(17, 24, 39, 0.12));
  --cv-border-light: var(--light-border-color, rgba(17, 24, 39, 0.08));
  --cv-hover: var(--hover-bg, rgba(17, 24, 39, 0.05));
  --cv-text: var(--text-primary, #1f2328);
  --cv-text-2: var(--text-secondary, #667085);

  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 0 1.5rem 1.5rem 0;
  font-family: "IBM Plex Sans", "Söhne", sans-serif;

  /* Keep your nice “glass + gradients”, but base color follows theme */
  background: radial-gradient(
      circle at top right,
      rgba(108, 99, 255, 0.14),
      transparent 55%
    ),
    radial-gradient(
      circle at bottom left,
      rgba(17, 24, 39, 0.08),
      transparent 45%
    ),
    var(--cv-app-bg);
}

/* Make gradients darker when dark theme is active (optional but nice) */
:global(.main-app.dark-theme) .compose-view {
  background: radial-gradient(
      circle at top right,
      rgba(108, 99, 255, 0.22),
      transparent 55%
    ),
    radial-gradient(
      circle at bottom left,
      rgba(255, 255, 255, 0.06),
      transparent 45%
    ),
    var(--cv-app-bg);
}

.chat-split {
  display: flex;
  gap: 12px;
  height: 100%;
  min-height: 0;
}

.chat-sidebar {
  width: 260px;
  border: 1px solid var(--cv-border);
  border-radius: 12px;
  overflow: hidden;
  background-color: var(--cv-content-bg);
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.chat-sidebar-header {
  padding: 12px;
  border-bottom: 1px solid var(--cv-border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  background-color: var(--cv-content-bg);
}

.chat-sidebar-title {
  font-weight: 600;
  color: var(--cv-text);
}

.chat-new {
  background: var(--cv-primary);
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
  padding: 6px; /* tighter */
  display: flex;
  flex-direction: column;
  gap: 4px; /* tighter spacing */
  overflow: auto;
  overflow-x: hidden; /* prevent any horizontal overflow */
  min-height: 0;
}

.chat-list-item {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px; /* tighter */
  padding: 7px 8px; /* smaller rows */
  border-radius: 9px;
  border: 1px solid transparent;
  background: transparent;
  color: var(--cv-text);
  cursor: pointer;
  text-align: left;
  min-height: 34px; /* consistent compact height */
  box-sizing: border-box;
}

.chat-list-item:hover {
  background: var(--cv-hover);
}

.chat-list-item.active {
  border-color: var(--cv-border);
  background: var(--cv-hover);
}

.chat-list-item-title {
  font-size: 0.86rem; /* slightly smaller */
  line-height: 1.15; /* tighter */
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  min-width: 0; /* important for flex ellipsis */
}

.chat-delete {
  width: 22px; /* smaller button */
  height: 22px;
  border: none;
  border-radius: 7px;
  background: transparent;
  cursor: pointer;
  font-size: 16px; /* smaller X */
  line-height: 1;
  color: var(--cv-text-2);
  display: grid;
  place-items: center;
  flex: 0 0 auto;
}

.chat-delete:hover {
  background: rgba(0, 0, 0, 0.06);
  color: var(--cv-text);
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
  border: 1px solid var(--cv-border);
  border-radius: 18px;
  overflow: hidden;

  /* Glass look but follows theme */
  background: color-mix(in srgb, var(--cv-content-bg) 78%, transparent);
  backdrop-filter: blur(12px);
  height: 100%;
}

/* Scrollable messages */
.chat-history {
  flex-grow: 1;
  padding: 1.75rem 1.5rem 1rem;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 0;
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
  background-color: var(--cv-primary);
  color: #fff;
  padding: 10px 14px;
  border-bottom-right-radius: 6px;
}

.ai-message {
  align-self: flex-start;
  background-color: transparent;
  color: var(--cv-text);
  border: none;
  border-bottom-left-radius: 6px;
}

.message-text {
  margin: 0;
  display: inline-block;
  padding: 10px 14px;
  border-radius: 16px;
  border: 1px solid var(--cv-border-light);
  background: rgba(17, 24, 39, 0.04);
  color: var(--cv-text);
}

:global(.main-app.dark-theme) .compose-view .message-text {
  background: rgba(255, 255, 255, 0.06);
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
  background: var(--cv-content-bg);
  border: 1px solid var(--cv-border);
  border-radius: 8px;
  padding: 10px 12px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
  text-align: left;
  color: var(--cv-text);
}

.email-header {
  font-weight: 600;
  color: var(--cv-primary);
  border-bottom: 1px solid var(--cv-border);
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
  background: var(--cv-border);
  margin: 6px 0;
}

.label-badge {
  background-color: rgba(108, 99, 255, 0.12);
  color: var(--cv-text);
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
  background: rgba(0, 0, 0, 0.04);
  padding: 7px;
  border-radius: 4px;
  margin-top: 4px;
  font-family: "Courier New", Courier, monospace;
  font-size: 0.84rem;
  white-space: pre-wrap;
  color: var(--cv-text);
}

:global(.main-app.dark-theme) .compose-view .email-body-content {
  background: rgba(255, 255, 255, 0.06);
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
  border-top: 1px solid var(--cv-border);
  display: flex;
  align-items: center;
  background-color: var(--cv-content-bg);
}

.input-wrapper {
  position: relative;
  flex-grow: 1;
}

.input-wrapper input {
  width: 100%;
  padding: 10px 90px 10px 14px;
  border: 1px solid var(--cv-border);
  border-radius: 999px;
  font-size: 0.96rem;
  background-color: var(--cv-content-bg);
  color: var(--cv-text);
  outline: none;
}

.input-wrapper input:focus {
  border-color: var(--cv-primary);
  box-shadow: 0 0 0 3px rgba(108, 99, 255, 0.18);
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

.inner-send {
  right: 50px;
  color: var(--cv-primary);
}

.inner-voice {
  right: 10px;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background-color: var(--cv-primary);
  color: #fff;
}

.inner-voice.listening-active {
  background-color: var(--cv-primary);
  color: #fff;
  box-shadow: 0 0 0 4px rgba(108, 99, 255, 0.2);
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

/* --- Voice inline indicator --- */
.voice-inline {
  align-self: flex-start;
  background: rgba(17, 24, 39, 0.06);
  border: 1px solid rgba(17, 24, 39, 0.1);
  padding: 10px 14px;
  border-radius: 14px;
  max-width: 320px;
}

:global(.main-app.dark-theme) .compose-view .voice-inline {
  background: rgba(255, 255, 255, 0.06);
  border-color: var(--cv-border);
}

.voice-inline-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.9rem;
  font-weight: 500;
  color: var(--cv-text);
}

.voice-bar-left {
  padding-left: 2px;
}
.voice-inline-dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: var(--cv-primary);
  box-shadow: 0 0 0 6px rgba(108, 99, 255, 0.12);
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
  background: rgba(108, 99, 255, 0.8);
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

/* --- Voice recorder bar --- */
.voice-bar {
  width: 100%;
  height: 44px;
  border-radius: 999px;
  border: 1px solid var(--cv-border);
  background: var(--cv-content-bg);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 10px 0 12px;
  gap: 12px;
}

.voice-bar.recording {
  border-color: rgba(108, 99, 255, 0.55);
  box-shadow: 0 0 0 3px rgba(108, 99, 255, 0.18);
}

.voice-bar-dot {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: rgba(17, 24, 39, 0.3);
}

.voice-bar-dot.live {
  background: var(--cv-primary);
  box-shadow: 0 0 0 6px rgba(108, 99, 255, 0.12);
  animation: voice-pulse 1.2s ease-in-out infinite;
}

.voice-bar-wave {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 4px;
  height: 18px;
  min-width: 90px;
}

/* --- Voice recorder bar --- */
.voice-bar {
  width: 100%;
  height: 44px;
  border-radius: 999px;
  border: 1px solid var(--cv-border);
  background: var(--cv-content-bg);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 10px 0 12px;
  gap: 12px;
}

.voice-bar.recording {
  border-color: rgba(108, 99, 255, 0.55);
  box-shadow: 0 0 0 3px rgba(108, 99, 255, 0.18);
}

/* Left “colored button/pill” */
.voice-pill {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0; /* remove padding bubble */
  border-radius: 0; /* no pill */
  background: transparent; /* no blue background */
  border: none; /* remove outline */
}

/* Voice dot uses text color as a fallback so it always has contrast */
.voice-pill-dot {
  width: 10px;
  height: 10px;
  border-radius: 999px;

  /* Use text color so it auto adapts to dark/light */
  background: color-mix(in srgb, var(--cv-text) 55%, transparent);
}

/* Live dot is always your accent */
.voice-pill-dot.live {
  background: var(--cv-primary);
  box-shadow: 0 0 0 6px rgba(108, 99, 255, 0.18);
  animation: voice-dot-pulse 1.35s ease-in-out infinite;
}

@keyframes voice-dot-pulse {
  0%,
  100% {
    transform: scale(1);
    box-shadow: 0 0 0 6px rgba(108, 99, 255, 0.12);
  }
  50% {
    transform: scale(1.16);
    box-shadow: 0 0 0 9px rgba(108, 99, 255, 0.16);
  }
}

.voice-pill-text {
  display: flex;
  flex-direction: column;
  line-height: 1.1;
}

.voice-pill-title {
  font-weight: 650;
  font-size: 0.92rem;
  color: var(--cv-text);
}

.voice-pill-sub {
  margin-top: 2px;
  font-size: 0.78rem;
  color: var(--cv-text-2);
}

/* Wave = staggered pulse, NOT synchronized block */
.voice-bar-wave {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 4px;
  height: 18px;
  min-width: 110px;
  padding-right: 4px;
}

.voice-bar-wave span {
  width: 3px;
  height: 100%;
  border-radius: 999px;
  background: rgba(108, 99, 255, 0.78);
  transform-origin: bottom;
  transform: scaleY(0.22);
  opacity: 0.85;
  animation-name: voice-pulse-bar;
  animation-timing-function: cubic-bezier(0.2, 0.7, 0.2, 1);
  animation-iteration-count: infinite;
}

/* Uneven rhythm: different delays + different durations + slight amplitude variance */
.voice-bar-wave span:nth-child(1) {
  animation-delay: 0s;
  animation-duration: 1.05s;
}
.voice-bar-wave span:nth-child(2) {
  animation-delay: 0.18s;
  animation-duration: 1.32s;
}
.voice-bar-wave span:nth-child(3) {
  animation-delay: 0.07s;
  animation-duration: 0.92s;
}
.voice-bar-wave span:nth-child(4) {
  animation-delay: 0.26s;
  animation-duration: 1.44s;
}
.voice-bar-wave span:nth-child(5) {
  animation-delay: 0.12s;
  animation-duration: 1.1s;
}
.voice-bar-wave span:nth-child(6) {
  animation-delay: 0.33s;
  animation-duration: 1.58s;
}
.voice-bar-wave span:nth-child(7) {
  animation-delay: 0.09s;
  animation-duration: 0.98s;
}
.voice-bar-wave span:nth-child(8) {
  animation-delay: 0.21s;
  animation-duration: 1.26s;
}
.voice-bar-wave span:nth-child(9) {
  animation-delay: 0.04s;
  animation-duration: 1.38s;
}
.voice-bar-wave span:nth-child(10) {
  animation-delay: 0.29s;
  animation-duration: 1.62s;
}

.voice-bar:not(.recording) .voice-bar-wave span {
  opacity: 0.45;
  transform: scaleY(0.18);
  animation-play-state: paused;
}

@keyframes voice-pulse-bar {
  0% {
    transform: scaleY(0.18);
    opacity: 0.55;
  }
  18% {
    transform: scaleY(0.85);
    opacity: 0.95;
  }
  38% {
    transform: scaleY(0.28);
    opacity: 0.7;
  }
  56% {
    transform: scaleY(0.68);
    opacity: 0.92;
  }
  78% {
    transform: scaleY(0.24);
    opacity: 0.68;
  }
  100% {
    transform: scaleY(0.18);
    opacity: 0.55;
  }
}

/* Stop button stays same */
.voice-bar-stop {
  width: 34px;
  height: 34px;
  border-radius: 999px;
  border: none;
  display: grid;
  place-items: center;
  cursor: pointer;
  background: var(--cv-primary);
  color: #fff;
  flex: 0 0 auto;
}

.voice-bar-stop.active {
  background: rgba(220, 38, 38, 0.95);
}

.voice-bar-stop:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.voice-bar-stop {
  width: 34px;
  height: 34px;
  border-radius: 999px;
  border: none;
  display: grid;
  place-items: center;
  cursor: pointer;
  background: var(--cv-primary);
  color: #fff;
  flex: 0 0 auto;
}

.voice-bar-stop.active {
  background: rgba(220, 38, 38, 0.95);
}

.voice-bar-stop:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
