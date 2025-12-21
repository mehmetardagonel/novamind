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
        <!-- ✅ Voice Agent -->
        <div v-if="isVoicePage" class="voice-page" aria-live="polite">
          <div class="voice-header">
            <div class="voice-title">
              Voice Agent
              <span v-if="activeChat" class="voice-subtitle">
                · {{ activeChat.title || "Chat" }}
              </span>
            </div>

            <!-- ✅ X is disabled while agent is active -->
            <button
              class="voice-close"
              @click="closeVoicePage"
              title="Close voice agent"
              :disabled="isVoiceBusy"
              :class="{ disabled: isVoiceBusy }"
            >
              ✕
            </button>
          </div>

          <div class="voice-stage">
            <!-- Orb -->
            <div
              class="voice-orb"
              :class="voicePhase"
              :style="orbStyle"
              aria-hidden="true"
            >
              <span class="voice-orb-core"></span>
              <span class="voice-orb-ring ring-1"></span>
              <span class="voice-orb-ring ring-2"></span>
              <span class="voice-orb-ring ring-3"></span>
            </div>

            <!-- Status ABOVE wave -->
            <div class="voice-status">
              <div class="voice-status-pill" :class="voicePhase">
                <span class="voice-status-dot" :class="voicePhase"></span>

                <span class="voice-status-text">
                  {{ voiceStatusLabel
                  }}<span v-if="voicePhase === 'listening'">{{
                    listeningDots
                  }}</span>
                </span>
              </div>

              <div class="voice-hint">{{ voiceHint }}</div>
            </div>

            <!-- Old bars animation -->
            <div class="voice-wave" :class="{ active: voicePhase !== 'ready' }">
              <span></span><span></span><span></span><span></span><span></span
              ><span></span><span></span>
            </div>
          </div>

          <div class="voice-footer">
            <button
              class="voice-primary"
              @click="handleVoiceInput"
              :disabled="isLoading || !activeChat"
            >
              <span class="material-symbols-outlined">
                {{
                  voicePhase === "listening" || voicePhase === "recording"
                    ? "stop"
                    : "mic"
                }}
              </span>
              <span>
                {{
                  voicePhase === "listening" || voicePhase === "recording"
                    ? "Stop"
                    : "Start"
                }}
              </span>
            </button>

            <!-- ✅ Cancel removed -->
          </div>
        </div>

        <!-- ✅ Normal chat panel -->
        <div v-else class="chat-container">
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
                    v-if="isImportantEmail(email)"
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
                :disabled="isLoading || !activeChat"
              />

              <button
                class="inner-send"
                @click="sendMessage"
                :disabled="!userPrompt.trim() || isLoading || !activeChat"
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
                @click="openVoicePage"
                :disabled="isLoading || !activeChat"
                title="Open voice agent"
              >
                <span class="material-symbols-outlined mic-icon">mic</span>
              </button>
            </div>
          </div>
        </div>
        <!-- /chat-container -->
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

export default {
  name: "ComposeView",
  setup() {
    const authStore = useAuthStore();
    const chatStore = useChatStore();

    const userPrompt = ref("");
    const isLoading = ref(false);
    const historyContainer = ref(null);

    const isVoicePage = ref(false);

    /**
     * ✅ Voice UI phase
     * - ready | listening | recording | thinking | speaking
     */
    const voicePhase = ref("ready");

    // ✅ Busy state (used to disable X)
    const isVoiceBusy = computed(() =>
      ["listening", "recording", "thinking", "speaking"].includes(
        voicePhase.value
      )
    );

    const listeningDots = ref("");
    let dotInterval = null;

    // Mic-reactive level (0..1)
    const voiceLevel = ref(0);

    // WebAudio meter internals
    let meterStream = null;
    let audioCtx = null;
    let analyser = null;
    let meterRAF = null;
    let analyserData = null;

    const activeRecorder = ref(null);

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

    const voiceStatusLabel = computed(() => {
      if (voicePhase.value === "listening") return "Listening";
      if (voicePhase.value === "recording") return "Recording";
      if (voicePhase.value === "thinking") return "Thinking";
      if (voicePhase.value === "speaking") return "Speaking";
      return "Ready";
    });

    const voiceHint = computed(() => {
      if (!activeChat.value) return "Select a chat to start.";
      if (voicePhase.value === "listening")
        return "Speak naturally. Recording stops on silence.";
      if (voicePhase.value === "recording") return "Recording…";
      if (voicePhase.value === "thinking") return "Processing your request…";
      if (voicePhase.value === "speaking") return "Assistant is replying.";
      return "Tap Start to talk.";
    });

    const orbStyle = computed(() => {
      const lvl = Math.max(0, Math.min(1, voiceLevel.value || 0));
      const scale = 1 + lvl * 0.32;
      const glow = 0.55 + lvl * 0.55;
      return {
        "--v-lvl": String(lvl),
        "--v-scale": String(scale),
        "--v-glow": String(glow),
      };
    });

    const formatBody = (text) => (!text ? "" : text.replace(/\n/g, "<br>"));

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

    const findBalancedJson = (text, startIndex, openChar, closeChar) => {
      let depth = 0;
      let inString = false;
      let escape = false;
      for (let i = startIndex; i < text.length; i += 1) {
        const ch = text[i];
        if (inString) {
          if (escape) escape = false;
          else if (ch === "\\") escape = true;
          else if (ch === '"') inString = false;
          continue;
        }
        if (ch === '"') {
          inString = true;
          continue;
        }
        if (ch === openChar) depth += 1;
        else if (ch === closeChar) {
          depth -= 1;
          if (depth === 0) return text.slice(startIndex, i + 1);
        }
      }
      return null;
    };

    const findFirstBalancedJson = (text, openChar, closeChar) => {
      let idx = text.indexOf(openChar);
      while (idx !== -1) {
        const candidate = findBalancedJson(text, idx, openChar, closeChar);
        if (candidate) return { candidate, index: idx };
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

      const fenceRegex = /```\s*json\s*([\s\S]*?)\s*```/gi;
      for (const match of text.matchAll(fenceRegex)) {
        const candidate = (match[1] || "").trim();
        if (tryCandidate(candidate, match.index)) return result;
      }

      const anyFenceRegex = /```\s*([\s\S]*?)\s*```/g;
      for (const match of text.matchAll(anyFenceRegex)) {
        const candidate = (match[1] || "").trim();
        if (tryCandidate(candidate, match.index)) return result;
      }

      const directPayload = tryParseEmailsJson(text.trim());
      if (directPayload) {
        result.emails = directPayload.emails;
        result.insights = directPayload.insights;
        return result;
      }

      const arrayMatch = findFirstBalancedJson(text, "[", "]");
      if (arrayMatch && tryCandidate(arrayMatch.candidate, arrayMatch.index))
        return result;

      const objectMatch = findFirstBalancedJson(text, "{", "}");
      if (objectMatch && tryCandidate(objectMatch.candidate, objectMatch.index))
        return result;

      result.textBefore = stripJsonBlocks(text);
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

        if (!response.ok)
          throw new Error(`API request failed: ${response.status}`);

        const data = await response.json();

        if (data.session_id) {
          chatStore.setSessionId(chatId, data.session_id);
        }

        const responseText = data.response || "";
        const extracted = extractJsonFromText(responseText);

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
          displayText =
            stripJsonBlocks(responseText) || "I processed your request.";
        }

        chatStore.appendMessage(chatId, {
          role: "bot",
          text: displayText,
          emails: extracted.emails,
        });
      } catch (error) {
        console.error("Error:", error);
        chatStore.appendMessage(activeChat.value.id, {
          role: "bot",
          text: "Sorry, an error occurred connecting to the server. Please ensure the backend is running.",
          emails: null,
        });
      } finally {
        isLoading.value = false;
        scrollToBottom();
      }
    };

    const startDots = () => {
      listeningDots.value = "";
      dotInterval = setInterval(() => {
        listeningDots.value =
          listeningDots.value.length < 3 ? listeningDots.value + "." : "";
      }, 500);
    };

    const stopDots = () => {
      if (dotInterval) clearInterval(dotInterval);
      dotInterval = null;
      listeningDots.value = "";
    };

    const stopMicMeter = async () => {
      voiceLevel.value = 0;
      if (meterRAF) cancelAnimationFrame(meterRAF);
      meterRAF = null;

      try {
        if (audioCtx) await audioCtx.close();
      } catch {}
      audioCtx = null;
      analyser = null;
      analyserData = null;

      if (meterStream) meterStream.getTracks().forEach((t) => t.stop());
      meterStream = null;
    };

    const startMicMeter = async () => {
      if (meterStream || analyser || audioCtx) return;
      try {
        meterStream = await navigator.mediaDevices.getUserMedia({
          audio: {
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
          },
          video: false,
        });

        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        const src = audioCtx.createMediaStreamSource(meterStream);

        analyser = audioCtx.createAnalyser();
        analyser.fftSize = 1024;
        analyser.smoothingTimeConstant = 0.85;
        src.connect(analyser);

        analyserData = new Uint8Array(analyser.frequencyBinCount);

        const tick = () => {
          if (!analyser) return;
          analyser.getByteTimeDomainData(analyserData);

          let sum = 0;
          for (let i = 0; i < analyserData.length; i++) {
            const v = (analyserData[i] - 128) / 128;
            sum += v * v;
          }
          const rms = Math.sqrt(sum / analyserData.length);
          const scaled = Math.max(0, Math.min(1, rms * 2.8));
          voiceLevel.value = voiceLevel.value * 0.75 + scaled * 0.25;

          meterRAF = requestAnimationFrame(tick);
        };

        tick();
      } catch (e) {
        console.warn("Mic meter unavailable:", e);
        await stopMicMeter();
      }
    };

    const stopRecordingSession = async () => {
      if (activeRecorder.value?.stop) {
        try {
          activeRecorder.value.stop();
        } catch {}
      }
      activeRecorder.value = null;
      stopDots();
      await stopMicMeter();
      if (
        voicePhase.value === "listening" ||
        voicePhase.value === "recording"
      ) {
        voicePhase.value = "ready";
      }
    };

    audioPlayer.addEventListener("ended", () => {
      if (currentAudioUrl) {
        URL.revokeObjectURL(currentAudioUrl);
        currentAudioUrl = null;
      }
      if (voicePhase.value === "speaking") voicePhase.value = "ready";
    });

    const playReplyAudio = async (blob) => {
      if (!blob) return;
      if (currentAudioUrl) URL.revokeObjectURL(currentAudioUrl);
      currentAudioUrl = URL.createObjectURL(blob);
      audioPlayer.src = currentAudioUrl;

      voicePhase.value = "speaking";
      try {
        await audioPlayer.play();
      } catch (e) {
        console.error("Failed to play voice response:", e);
        voicePhase.value = "ready";
      }
    };

    const speakFallback = async (text) => {
      if (!text) return;

      voicePhase.value = "speaking";
      try {
        window.speechSynthesis.cancel();
        const utter = new SpeechSynthesisUtterance(text);
        utter.onend = () => {
          if (voicePhase.value === "speaking") voicePhase.value = "ready";
        };
        utter.onerror = () => {
          if (voicePhase.value === "speaking") voicePhase.value = "ready";
        };
        window.speechSynthesis.speak(utter);
      } catch {
        voicePhase.value = "ready";
      }
    };

    const openVoicePage = () => {
      if (!activeChat.value) return;
      isVoicePage.value = true;
      voicePhase.value = "ready";
      voiceLevel.value = 0;
    };

    // ✅ Close is blocked while busy (and X is disabled)
    const closeVoicePage = async () => {
      if (isVoiceBusy.value) return;

      await stopRecordingSession();

      try {
        audioPlayer.pause();
        audioPlayer.src = "";
      } catch {}
      try {
        window.speechSynthesis?.cancel?.();
      } catch {}

      voicePhase.value = "ready";
      isVoicePage.value = false;
    };

    const handleVoiceInput = async () => {
      if (isLoading.value || !activeChat.value) return;

      if (
        voicePhase.value === "listening" ||
        voicePhase.value === "recording"
      ) {
        await stopRecordingSession();
        return;
      }

      voicePhase.value = "listening";
      startDots();
      await startMicMeter();

      try {
        const recorder = recordUntilSilence();
        activeRecorder.value = recorder;

        voicePhase.value = "recording";

        const audioBlob = await recorder.promise;
        activeRecorder.value = null;

        await stopMicMeter();
        stopDots();

        if (!audioBlob || audioBlob.size === 0) {
          voicePhase.value = "ready";
          return;
        }

        voicePhase.value = "thinking";
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

        let responseText = assistantReply || "";
        let extracted = extractJsonFromText(responseText);

        if (responseId) {
          try {
            const res = await fetch(
              `${VOICE_RESPONSE_URL}/${encodeURIComponent(responseId)}`,
              { headers: { "X-User-Id": authStore.user?.id } }
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
          } catch (e) {
            console.warn("Failed to load voice response payload:", e);
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

        if (!displayText && !replyAudio) {
          displayText = "I didn't catch that. Please try again.";
        }

        if (displayText || Array.isArray(extracted.emails)) {
          chatStore.appendMessage(chatId, {
            role: "bot",
            text: displayText,
            emails: extracted.emails,
          });
        }

        if (replyAudio) {
          await playReplyAudio(replyAudio);
        } else {
          await speakFallback(displayText);
        }

        scrollToBottom();
      } catch (error) {
        console.error("Voice request failed:", error);
        await stopMicMeter();
        stopDots();
        voicePhase.value = "ready";
        window.alert("Voice request failed");
      } finally {
        isLoading.value = false;
        if (voicePhase.value === "thinking") voicePhase.value = "ready";
      }
    };

    onUnmounted(async () => {
      stopDots();
      await stopMicMeter();

      if (currentAudioUrl) {
        URL.revokeObjectURL(currentAudioUrl);
        currentAudioUrl = null;
      }
      try {
        audioPlayer.pause();
        audioPlayer.src = "";
      } catch {}
      try {
        window.speechSynthesis?.cancel?.();
      } catch {}
    });

    onMounted(async () => {
      await chatStore.initialize();
      nextTick(scrollToBottom);
    });

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
      () => nextTick(scrollToBottom)
    );

    return {
      userPrompt,
      isLoading,

      chats,
      activeChatId,
      activeChat,
      activeMessages,

      isVoicePage,
      openVoicePage,
      closeVoicePage,

      voicePhase,
      isVoiceBusy, // ✅ exposed for X disabled
      listeningDots,
      voiceStatusLabel,
      voiceHint,
      orbStyle,

      sendMessage,
      handleVoiceInput,

      formatBody,
      formatMessageText,
      isImportantEmail,
      historyContainer,

      createChat,
      deleteChat,
      setActiveChat,
    };
  },
};
</script>

<style scoped>
/* ✅ Keep your exact styles from your last working file (unchanged) */
.compose-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  overflow: hidden;
  box-sizing: border-box;
  padding: 0 1.5rem 1.5rem 0;
}

.chat-split {
  flex: 1;
  min-height: 0;
  display: flex;
  gap: 12px;
  overflow: hidden;
}

.chat-sidebar {
  width: 270px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  min-height: 0;
  border: 1px solid var(--border-color);
  border-radius: 12px;
  background-color: var(--content-bg);
  overflow: hidden;
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
  flex: 1;
  min-height: 0;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  overflow-y: auto;
  overflow-x: hidden;
  min-width: 0;
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
  min-width: 0;
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
  min-width: 0;
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
  overflow: hidden;
}

.chat-container {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--border-color);
  border-radius: 12px;
  background-color: var(--content-bg);
  overflow: hidden;
}

.chat-history {
  flex: 1;
  min-height: 0;
  padding: 1rem 1rem 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow-y: auto;
  overflow-x: hidden;
}

.message {
  max-width: 70%;
  padding: 10px 14px;
  border-radius: 18px;
  line-height: 1.5;
  font-size: 0.95rem;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06);
  min-width: 0;
  word-break: break-word;
  overflow-wrap: anywhere;
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

/* ===== Voice Page ===== */
.voice-page {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--border-color);
  border-radius: 12px;

  --voice-accent: #3b82f6;
  --voice-accent-soft: rgba(59, 130, 246, 0.18);
  --voice-accent-ring: rgba(59, 130, 246, 0.28);

  background: radial-gradient(
      circle at top,
      var(--voice-accent-soft),
      transparent 60%
    ),
    var(--content-bg);
  overflow: hidden;
  position: relative;
}

.voice-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border-color);
}

.voice-title {
  font-weight: 700;
  color: var(--text-primary);
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.voice-subtitle {
  font-weight: 500;
  font-size: 0.9rem;
  color: var(--text-secondary);
}

.voice-close {
  border: 1px solid var(--border-color);
  background: rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  width: 36px;
  height: 36px;
  cursor: pointer;
  color: var(--text-primary);
}

/* ✅ Disabled X styling */
.voice-close:disabled,
.voice-close.disabled {
  opacity: 0.45;
  cursor: not-allowed;
  pointer-events: none;
}

.voice-stage {
  flex: 1;
  min-height: 0;
  display: grid;
  place-items: center;
  gap: 14px;
  padding: 24px 18px 18px;
}

.voice-orb {
  position: relative;
  width: min(240px, 46vw);
  height: min(240px, 46vw);
  max-width: 260px;
  max-height: 260px;
  min-width: 160px;
  min-height: 160px;
  display: grid;
  place-items: center;
  transform: translateZ(0);
}

.voice-orb-core {
  width: 62px;
  height: 62px;
  border-radius: 50%;
  background: radial-gradient(
    circle,
    var(--voice-accent),
    rgba(59, 130, 246, 0.62)
  );
  transform: scale(var(--v-scale, 1));
  box-shadow: 0 0 calc(26px * var(--v-glow, 1)) rgba(59, 130, 246, 0.55);
  transition: box-shadow 80ms linear, transform 80ms linear;
}

.voice-orb-ring {
  position: absolute;
  width: 100%;
  height: 100%;
  border-radius: 50%;
  border: 2px solid var(--voice-accent-ring);
  opacity: 0.35;
}

.voice-orb.ready .voice-orb-core {
  animation: orb-breathe 2.6s ease-in-out infinite;
}
.voice-orb.ready .voice-orb-ring {
  animation: ring-float 3.2s ease-in-out infinite;
}
.voice-orb.ready .ring-2 {
  animation-delay: 0.35s;
}
.voice-orb.ready .ring-3 {
  animation-delay: 0.7s;
}

.voice-orb.listening {
  animation: orb-wobble 1.3s ease-in-out infinite;
}
.voice-orb.listening .voice-orb-core {
  animation: orb-pulse 0.95s ease-in-out infinite;
}
.voice-orb.listening .voice-orb-ring {
  animation: ring-ripple 1.2s ease-out infinite;
  opacity: 0.55;
}
.voice-orb.listening .ring-2 {
  animation-delay: 0.18s;
}
.voice-orb.listening .ring-3 {
  animation-delay: 0.36s;
}

.voice-orb.recording .voice-orb-core {
  animation: orb-record 0.75s ease-in-out infinite;
}
.voice-orb.recording .voice-orb-ring {
  animation: ring-ripple 0.95s ease-out infinite;
  opacity: 0.6;
}
.voice-orb.recording .ring-2 {
  animation-delay: 0.16s;
}
.voice-orb.recording .ring-3 {
  animation-delay: 0.32s;
}

.voice-orb.thinking .voice-orb-core {
  animation: orb-speak 1.25s ease-in-out infinite;
}
.voice-orb.thinking .voice-orb-ring {
  animation: ring-ripple 1.9s ease-out infinite;
  opacity: 0.5;
}

.voice-orb.speaking .voice-orb-core {
  animation: orb-speak 1.1s ease-in-out infinite;
}
.voice-orb.speaking .voice-orb-ring {
  animation: ring-ripple 1.65s ease-out infinite;
  opacity: 0.55;
}
.voice-orb.speaking .ring-2 {
  animation-delay: 0.22s;
}
.voice-orb.speaking .ring-3 {
  animation-delay: 0.44s;
}

@keyframes orb-breathe {
  0%,
  100% {
    filter: saturate(1);
  }
  50% {
    filter: saturate(1.12);
  }
}
@keyframes ring-float {
  0%,
  100% {
    transform: translateY(0) scale(0.94);
    opacity: 0.28;
  }
  50% {
    transform: translateY(-6px) scale(1.02);
    opacity: 0.42;
  }
}
@keyframes orb-wobble {
  0%,
  100% {
    transform: rotate(-1.5deg);
  }
  50% {
    transform: rotate(1.5deg);
  }
}
@keyframes orb-pulse {
  0%,
  100% {
    filter: saturate(1);
  }
  50% {
    filter: saturate(1.15);
  }
}
@keyframes orb-record {
  0%,
  100% {
    filter: saturate(1.05);
  }
  50% {
    filter: saturate(1.18);
  }
}
@keyframes orb-speak {
  0%,
  100% {
    filter: saturate(1.06);
  }
  50% {
    filter: saturate(1.22);
  }
}
@keyframes ring-ripple {
  0% {
    transform: scale(0.78);
    opacity: 0.55;
  }
  100% {
    transform: scale(1.22);
    opacity: 0;
  }
}

.voice-status {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  text-align: center;
}

.voice-status-pill {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border-radius: 999px;
  border: 1px solid rgba(17, 24, 39, 0.12);
  background: rgba(255, 255, 255, 0.06);
  color: var(--text-primary);
  font-weight: 700;
}

.voice-status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  box-shadow: 0 0 0 6px rgba(59, 130, 246, 0.12);
  animation: voice-pulse 1.2s ease-in-out infinite;
  background: #3b82f6;
}
.voice-status-dot.ready {
  background: #3b82f6;
}
.voice-status-dot.listening {
  background: #22c55e;
  box-shadow: 0 0 0 6px rgba(34, 197, 94, 0.14);
}
.voice-status-dot.recording {
  background: #ef4444;
  box-shadow: 0 0 0 6px rgba(239, 68, 68, 0.14);
}
.voice-status-dot.thinking {
  background: #a855f7;
  box-shadow: 0 0 0 6px rgba(168, 85, 247, 0.14);
}
.voice-status-dot.speaking {
  background: #f59e0b;
  box-shadow: 0 0 0 6px rgba(245, 158, 11, 0.14);
}

@keyframes voice-pulse {
  0%,
  100% {
    transform: scale(1);
  }
  50% {
    transform: scale(1.18);
  }
}

.voice-hint {
  color: var(--text-secondary);
  font-size: 0.95rem;
}

.voice-wave {
  display: flex;
  justify-content: center;
  gap: 6px;
  height: 22px;
  opacity: 0.65;
}
.voice-wave span {
  width: 5px;
  height: 100%;
  background: rgba(59, 130, 246, 0.65);
  border-radius: 999px;
  transform: scaleY(0.25);
}
.voice-wave.active span {
  animation: voice-wave 1s ease-in-out infinite;
}
.voice-wave.active span:nth-child(2) {
  animation-delay: 0.12s;
}
.voice-wave.active span:nth-child(3) {
  animation-delay: 0.24s;
}
.voice-wave.active span:nth-child(4) {
  animation-delay: 0.36s;
}
.voice-wave.active span:nth-child(5) {
  animation-delay: 0.48s;
}
.voice-wave.active span:nth-child(6) {
  animation-delay: 0.6s;
}
.voice-wave.active span:nth-child(7) {
  animation-delay: 0.72s;
}

@keyframes voice-wave {
  0%,
  100% {
    transform: scaleY(0.3);
  }
  50% {
    transform: scaleY(1);
  }
}

.voice-footer {
  display: flex;
  justify-content: center;
  gap: 10px;
  padding: 14px 16px 16px;
  border-top: 1px solid var(--border-color);
  background: rgba(0, 0, 0, 0.03);
}

.voice-primary {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  border: none;
  background: var(--primary-color);
  color: #fff;
  padding: 10px 18px;
  border-radius: 999px;
  cursor: pointer;
  font-weight: 800;
}
.voice-primary:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.voice-page::before {
  content: "";
  position: absolute;
  inset: 0;
  background: radial-gradient(
      circle at 30% 20%,
      rgba(59, 130, 246, 0.12),
      transparent 45%
    ),
    radial-gradient(circle at 70% 70%, rgba(59, 130, 246, 0.1), transparent 45%),
    linear-gradient(to bottom, rgba(255, 255, 255, 0.03), rgba(0, 0, 0, 0.08));
  pointer-events: none;
}

.voice-page::after {
  content: "";
  position: absolute;
  inset: 0;
  background-image: linear-gradient(
      rgba(255, 255, 255, 0.03) 1px,
      transparent 1px
    ),
    linear-gradient(90deg, rgba(255, 255, 255, 0.03) 1px, transparent 1px);
  background-size: 48px 48px;
  opacity: 0.25;
  mask-image: radial-gradient(circle at center, black 40%, transparent 75%);
  pointer-events: none;
}
</style>
