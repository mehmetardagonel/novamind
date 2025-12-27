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
        :class="{ unread: item.email?.isUnread }"
      >
        <div class="email-header">
          <div class="sender-with-label">
            <span class="email-sender">{{ senderLabel(item.email) }}</span>
            <span v-if="item.email?.recipient" class="email-recipient">
              → {{ item.email.recipient }}
            </span>
            <span
              v-if="item.email?.account_email"
              class="account-badge"
              :title="item.email.account_email"
            >
              {{ item.email.account_email }}
            </span>
            <span
              v-if="getLabelValue(item.email)"
              class="ml-label"
              :class="`ml-label-${getLabelValue(item.email)}`"
            >
              {{ getLabelText(getLabelValue(item.email)) }}
            </span>
          </div>
          <span class="email-date">{{ formatDate(item.email?.date || item.email?.timestamp) }}</span>
        </div>
        <div class="email-subject">{{ item.email?.subject || "(No subject)" }}</div>
        <div v-if="item.preview" class="email-preview">{{ item.preview }}</div>
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
      if (date.toDateString() === yesterday.toDateString()) {
        return "Yesterday";
      }
      return date.toLocaleDateString([], { month: "short", day: "numeric" });
    };

    const stripCssNoise = (text) => {
      if (!text) return "";
      const lines = text.split(/\n+/).map((line) => line.trim()).filter(Boolean);
      const filtered = lines.filter((line) => {
        const lower = line.toLowerCase();
        if (lower.startsWith("@font-face")) return false;
        if (lower.startsWith("@media")) return false;
        if (/^[.#]?[a-z0-9_-]+\s*\{/.test(lower) && /:/.test(lower)) return false;
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
      doc.querySelectorAll("style,script,head,meta,link,noscript").forEach((node) => {
        node.remove();
      });
      const rawText = (doc.body && doc.body.textContent) || doc.textContent || "";
      return stripCssNoise(rawText.replace(/\s+/g, " ").trim());
    };

    const extractImages = (body, existingImages) => {
      if (Array.isArray(existingImages) && existingImages.length > 0) {
        return existingImages.filter((src) => typeof src === "string" && !src.startsWith("cid:"));
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
      return text.substring(0, 100) + (text.length > 100 ? "..." : "");
    };

    const getLabelText = (prediction) => {
      const labels = {
        spam: "Spam",
        ham: "Normal",
        important: "Important",
      };
      return labels[prediction] || prediction;
    };

    const getLabelValue = (email) => {
      if (!email || typeof email !== "object") return null;
      if (email.is_important) return "important";
      const labels = Array.isArray(email.label_ids) ? email.label_ids : [];
      if (labels.some((label) => String(label).toUpperCase() === "IMPORTANT")) {
        return "important";
      }
      return email.ml_prediction || null;
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
      formatDate,
      getLabelText,
      getLabelValue,
      preparedEmails,
    };
  },
};
</script>

<style scoped>
.chat-email-list {
  border: 1px solid var(--border-color, #e0e0e0);
  border-radius: 12px;
  background-color: var(--content-bg, #ffffff);
  overflow: hidden;
}

.no-emails {
  padding: 1rem 1.25rem;
  color: var(--text-secondary, #667085);
  font-size: 0.95rem;
}

.email-list {
  display: flex;
  flex-direction: column;
}

.email-item {
  background-color: var(--read-email-bg, #f7f8fa);
  border-bottom: 1px solid var(--border-color, #e0e0e0);
  padding: 1rem 1.25rem;
  transition: background-color 0.2s ease;
}

.email-item.unread {
  background-color: var(--content-bg, #ffffff);
}

.email-item:last-child {
  border-bottom: none;
}

.email-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.sender-with-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex: 1;
  min-width: 0;
}

.email-sender {
  font-weight: 500;
  color: var(--text-secondary, #667085);
  font-size: 1.05rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.email-recipient {
  font-weight: 600;
  color: #1976d2;
  margin-left: 6px;
  font-size: 1.05rem;
}

.account-badge {
  display: inline-block;
  padding: 0.15rem 0.5rem;
  border-radius: 4px;
  font-size: 0.65rem;
  font-weight: 500;
  white-space: nowrap;
  flex-shrink: 0;
  background-color: #e3f2fd;
  color: #1565c0;
  border: 1px solid #bbdefb;
  max-width: 150px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.ml-label {
  display: inline-block;
  padding: 0.15rem 0.5rem;
  border-radius: 4px;
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  white-space: nowrap;
  flex-shrink: 0;
}

.ml-label-spam {
  background-color: #fee;
  color: #c33;
  border: 1px solid #fcc;
}

.ml-label-important {
  background-color: #fff3cd;
  color: #856404;
  border: 1px solid #ffeaa7;
}

.ml-label-ham {
  background-color: #d4edda;
  color: #155724;
  border: 1px solid #c3e6cb;
}

.email-subject {
  font-weight: 500;
  font-size: 1rem;
  color: var(--text-secondary, #667085);
  margin-bottom: 0.5rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.email-date {
  font-size: 0.8rem;
  color: var(--text-secondary, #667085);
  font-weight: 500;
  white-space: nowrap;
}

.email-preview {
  font-size: 0.9rem;
  color: var(--text-secondary, #667085);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.email-images {
  display: flex;
  gap: 0.5rem;
  margin-top: 0.6rem;
  align-items: center;
  flex-wrap: wrap;
}

.email-image {
  width: 72px;
  height: 48px;
  object-fit: cover;
  border-radius: 6px;
  border: 1px solid #e5e7eb;
  background-color: #f3f4f6;
}

.email-images-more {
  font-size: 0.75rem;
  font-weight: 600;
  color: #475467;
  background-color: #f1f5f9;
  border: 1px solid #e2e8f0;
  border-radius: 999px;
  padding: 0.2rem 0.5rem;
}
</style>
