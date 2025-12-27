<template>
  <div class="chat-email-list">
    <div v-if="preparedEmails.length === 0" class="no-emails">
      No emails found.
    </div>

    <div v-else class="email-list">
      <div
        v-for="(item, index) in preparedEmails"
        :key="index"
        class="email-item"
        :class="{
          unread: item.email?.isUnread,
          'is-important': getLabelValue(item.email) === 'important',
          'is-spam': getLabelValue(item.email) === 'spam',
        }"
      >
        <!-- ✅ Row 1: email number - recipient account - status - date -->
        <div class="email-top-row">
          <span class="email-number">#{{ index + 1 }}</span>

          <span
            v-if="destinationAccount(item.email)"
            class="account-pill"
            :title="destinationAccount(item.email)"
          >
            {{ destinationAccount(item.email) }}
          </span>

          <!-- ✅ ALWAYS shown: Normal / Important / Spam -->
          <span
            class="status-pill"
            :class="`status-${getLabelValue(item.email)}`"
          >
            {{ getLabelText(getLabelValue(item.email)) }}
          </span>

          <span class="email-date">
            {{ formatDate(item.email?.date || item.email?.timestamp) }}
          </span>
        </div>

        <!-- Rest of email -->
        <div class="email-body">
          <div class="email-from-row">
            <span class="avatar" aria-hidden="true">
              {{ senderInitial(item.email) }}
            </span>

            <div class="from-block">
              <div class="email-sender" :title="senderLabel(item.email)">
                {{ senderLabel(item.email) }}
              </div>

              <div
                class="email-subject"
                :title="item.email?.subject || '(No subject)'"
              >
                {{ item.email?.subject || "(No subject)" }}
              </div>
            </div>

            <span
              v-if="item.email?.recipient"
              class="to-hint"
              :title="item.email.recipient"
            >
              → {{ item.email.recipient }}
            </span>
          </div>

          <div v-if="item.preview" class="email-preview">
            {{ item.preview }}
          </div>

          <div v-if="item.images.length" class="email-images">
            <img
              v-for="(image, imageIndex) in item.images.slice(0, 3)"
              :key="imageIndex"
              :src="image"
              :alt="item.email?.subject || 'Email image'"
              class="email-image"
            />
            <span v-if="item.images.length > 3" class="email-images-more">
              +{{ item.images.length - 3 }}
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { computed } from "vue";

export default {
  name: "ChatEmailList",
  props: {
    emails: {
      type: Array,
      default: () => [],
    },
  },
  setup(props) {
    const senderLabel = (email) => {
      if (!email || typeof email !== "object") return "Unknown";
      return email.sender || email.from || "Unknown";
    };

    const senderInitial = (email) => {
      const s = senderLabel(email);
      const cleaned = String(s).replace(/["<>]/g, "").trim();
      const letter = cleaned ? cleaned[0].toUpperCase() : "•";
      return /[A-Z0-9]/.test(letter) ? letter : "•";
    };

    const formatDate = (dateString) => {
      if (!dateString) return "";
      const date = new Date(dateString);
      if (Number.isNaN(date.getTime())) return String(dateString);

      const today = new Date();
      if (date.toDateString() === today.toDateString()) {
        return date.toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        });
      }

      const yesterday = new Date(today);
      yesterday.setDate(yesterday.getDate() - 1);
      if (date.toDateString() === yesterday.toDateString()) return "Yesterday";

      return date.toLocaleDateString([], {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
      });
    };

    const stripCssNoise = (text) => {
      if (!text) return "";
      const lines = text
        .split(/\n+/)
        .map((line) => line.trim())
        .filter(Boolean);

      const filtered = lines.filter((line) => {
        const lower = line.toLowerCase();
        if (lower.startsWith("@font-face")) return false;
        if (lower.startsWith("@media")) return false;
        if (/^[.#]?[a-z0-9_-]+\s*\{/.test(lower) && /:/.test(lower))
          return false;
        if (/[{}]/.test(line) && /:/.test(line) && /;/.test(line)) return false;
        if (lower.includes("font-family") && lower.includes(";")) return false;
        return true;
      });

      return filtered.join(" ");
    };

    const sanitizeBodyText = (body) => {
      if (!body) return "";
      const html = String(body);
      const parser = new DOMParser();
      const doc = parser.parseFromString(html, "text/html");
      doc
        .querySelectorAll("style,script,head,meta,link,noscript")
        .forEach((n) => n.remove());
      const rawText =
        (doc.body && doc.body.textContent) || doc.textContent || "";
      return stripCssNoise(rawText.replace(/\s+/g, " ").trim());
    };

    const extractImages = (body, existingImages) => {
      if (Array.isArray(existingImages) && existingImages.length > 0) {
        return existingImages.filter(
          (src) => typeof src === "string" && !src.startsWith("cid:")
        );
      }
      if (!body) return [];
      const html = String(body);
      const parser = new DOMParser();
      const doc = parser.parseFromString(html, "text/html");
      const images = [];
      doc.querySelectorAll("img").forEach((img) => {
        const src =
          img.getAttribute("src") ||
          img.getAttribute("data-src") ||
          img.getAttribute("data-original");
        if (!src || src.startsWith("cid:")) return;
        images.push(src);
      });
      return Array.from(new Set(images));
    };

    const buildPreview = (text) => {
      if (!text) return "";
      return text.substring(0, 120) + (text.length > 120 ? "…" : "");
    };

    const getLabelText = (prediction) => {
      const labels = { spam: "Spam", ham: "Normal", important: "Important" };
      return labels[prediction] || "Normal";
    };

    // ✅ ALWAYS returns one of: important | spam | ham
    const getLabelValue = (email) => {
      if (!email || typeof email !== "object") return "ham";

      // explicit flags
      if (email.is_important) return "important";
      if (email.is_spam) return "spam";

      // gmail-style label ids
      const labels = Array.isArray(email.label_ids) ? email.label_ids : [];
      const upper = labels.map((l) => String(l).toUpperCase());
      if (upper.includes("IMPORTANT")) return "important";
      if (upper.includes("SPAM")) return "spam";

      // ML prediction
      const ml = String(email.ml_prediction || "").toLowerCase();
      if (ml === "important") return "important";
      if (ml === "spam") return "spam";

      // default
      return "ham";
    };

    // connected account destination
    const destinationAccount = (email) => {
      if (!email || typeof email !== "object") return "";

      const candidates = [
        email.account_email,
        email.accountEmail,
        email.mailbox_email,
        email.mailbox,
        email.user_email,
        email.userEmail,

        // fallbacks
        email.recipient,
        email.delivered_to,
        email.deliveredTo,
        email.to,
        email.to_email,
      ];

      let val = candidates.find(
        (v) => v !== undefined && v !== null && v !== ""
      );
      if (!val) return "";

      if (Array.isArray(val)) val = val[0];
      if (val && typeof val === "object")
        val = val.email || val.address || val.value || "";

      const s = String(val).trim();
      if (!s) return "";

      const first = s.split(/[;,]/)[0].trim();
      const m = first.match(/<([^>]+)>/);
      return (m ? m[1] : first).trim();
    };

    const preparedEmails = computed(() =>
      (props.emails || []).map((email) => {
        const body = email?.body || email?.snippet || "";
        const sanitized = sanitizeBodyText(body);
        return {
          email,
          preview: buildPreview(sanitized),
          images: extractImages(body, email?.images),
        };
      })
    );

    return {
      senderLabel,
      senderInitial,
      formatDate,
      getLabelText,
      getLabelValue,
      destinationAccount,
      preparedEmails,
    };
  },
};
</script>

<style scoped>
/* ✅ FULL UI CSS (your nice version) */

.chat-email-list {
  --accent: var(--cv-primary, #6c63ff);
  --border: var(--cv-border, rgba(17, 24, 39, 0.12));
  --border-soft: var(--cv-border-light, rgba(17, 24, 39, 0.08));
  --bg: color-mix(
    in srgb,
    var(--cv-content-bg, rgba(255, 255, 255, 0.9)) 88%,
    transparent
  );
  --text: var(--cv-text, #1f2328);
  --muted: var(--cv-text-2, #667085);
  --hover: var(--cv-hover, rgba(17, 24, 39, 0.05));

  border: 1px solid color-mix(in srgb, var(--accent) 35%, var(--border));
  border-radius: 16px;
  background: var(--bg);
  overflow: hidden;
}

.no-emails {
  padding: 1rem 1.25rem;
  color: var(--muted);
  font-size: 0.95rem;
}

.email-list {
  display: flex;
  flex-direction: column;
}

.email-item {
  border-bottom: 1px solid var(--border-soft);
  padding: 12px 12px 14px;
  background: transparent;
}

.email-item:last-child {
  border-bottom: none;
}

.email-top-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border: 1px solid color-mix(in srgb, var(--accent) 22%, var(--border-soft));
  border-radius: 12px;
  background: color-mix(in srgb, var(--accent) 10%, transparent);
}

.email-number {
  font-weight: 700;
  font-size: 0.78rem;
  color: color-mix(in srgb, var(--accent) 88%, var(--text));
  padding: 2px 8px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--accent) 14%, transparent);
  border: 1px solid color-mix(in srgb, var(--accent) 26%, transparent);
}

.account-pill {
  max-width: 240px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;

  font-size: 0.78rem;
  font-weight: 650;
  color: color-mix(in srgb, var(--accent) 92%, var(--text));
  padding: 2px 10px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--accent) 16%, transparent);
  border: 1px solid color-mix(in srgb, var(--accent) 30%, transparent);
}

.status-pill {
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.3px;
  text-transform: uppercase;
  padding: 2px 10px;
  border-radius: 999px;
  border: 1px solid transparent;
}

/* ✅ IMPORTANT/SPAM/NORMAL */
.status-important {
  background: rgba(245, 158, 11, 0.14);
  color: rgb(180, 83, 9);
  border-color: rgba(245, 158, 11, 0.28);
}

.status-ham {
  background: rgba(34, 197, 94, 0.12);
  color: rgb(21, 128, 61);
  border-color: rgba(34, 197, 94, 0.24);
}

.status-spam {
  background: rgba(239, 68, 68, 0.12);
  color: rgb(185, 28, 28);
  border-color: rgba(239, 68, 68, 0.24);
}

.email-date {
  margin-left: auto;
  font-size: 0.78rem;
  font-weight: 650;
  color: var(--muted);
  white-space: nowrap;
}

.email-body {
  padding: 10px 8px 0;
}

.email-from-row {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.avatar {
  width: 34px;
  height: 34px;
  border-radius: 12px;
  display: grid;
  place-items: center;
  flex: 0 0 auto;

  background: color-mix(in srgb, var(--accent) 14%, transparent);
  border: 1px solid color-mix(in srgb, var(--accent) 28%, transparent);
  color: color-mix(in srgb, var(--accent) 92%, var(--text));
  font-weight: 800;
  font-size: 0.9rem;
}

.from-block {
  min-width: 0;
  flex: 1;
}

.email-sender {
  font-weight: 750;
  color: var(--text);
  font-size: 0.92rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.email-subject {
  margin-top: 2px;
  font-weight: 650;
  font-size: 0.9rem;
  color: color-mix(in srgb, var(--text) 85%, var(--muted));
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.to-hint {
  flex: 0 0 auto;
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 0.78rem;
  color: var(--muted);
  padding: 2px 8px;
  border-radius: 999px;
  border: 1px solid var(--border-soft);
  background: rgba(17, 24, 39, 0.03);
}

.email-preview {
  margin-top: 8px;
  font-size: 0.86rem;
  color: var(--muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.email-images {
  display: flex;
  gap: 8px;
  margin-top: 10px;
  align-items: center;
  flex-wrap: wrap;
}

.email-image {
  width: 76px;
  height: 50px;
  object-fit: cover;
  border-radius: 10px;
  border: 1px solid var(--border-soft);
  background-color: rgba(17, 24, 39, 0.04);
}

.email-images-more {
  font-size: 0.75rem;
  font-weight: 750;
  color: var(--muted);
  background: rgba(17, 24, 39, 0.04);
  border: 1px solid var(--border-soft);
  border-radius: 999px;
  padding: 0.2rem 0.55rem;
}
</style>
