<template>
  <div class="email-list-view">
    <div v-if="loading" class="loading">
      <p>Loading emails...</p>
    </div>

    <div v-else-if="errorMessage" class="error-box">
      <h3>Gmail API Error</h3>
      <p>{{ errorMessage }}</p>
      <div class="setup-instructions">
        <p><strong>To set up Gmail API:</strong></p>
        <ol>
          <li>Place <code>client_secret.json</code> in backend directory</li>
          <li>Run backend and follow OAuth flow to generate <code>gmail_token.json</code></li>
        </ol>
      </div>
    </div>

    <div v-else-if="emails.length > 0" class="email-list">
      <div
        v-for="(email, index) in emails"
        :key="index"
        class="email-item"
        :class="{ 
          'unread': index === 0, /* Now only marking the first as unread for demo */
          'selected': index === selectedEmailIndex 
        }" 
        @click="selectEmail(email, index)"
      >
        <div class="email-header">
          <span class="email-sender">{{ email.sender }}</span>
          <span class="email-date">{{ formatDate(email.date) }}</span>
        </div>
        <div class="email-subject">{{ email.subject }}</div>
        <div class="email-preview">{{ getPreview(email.body) }}</div>
      </div>
    </div>

    <div v-else class="no-emails">
      <p>No emails found in this folder.</p>
    </div>
  </div>
</template>

<script>
import { onMounted, ref } from 'vue'
import { fetchEmails } from '../api/emails' 

export default {
  name: "EmailListView",
  props: {
    folder: {
      type: String,
      required: true,
      default: 'inbox'
    }
  },
  setup(props) {
    const emails = ref([])
    const loading = ref(false)
    const errorMessage = ref('')
    const selectedEmailIndex = ref(null) 

    const loadEmails = async () => {
      loading.value = true
      errorMessage.value = ''
      emails.value = []
      selectedEmailIndex.value = null 

      try {
        console.log(`Fetching emails for folder: ${props.folder}`)
        const emailList = await fetchEmails(props.folder) 
        emails.value = emailList
      } catch (error) {
        console.error(`Error fetching ${props.folder} emails:`, error)
        errorMessage.value = error.detail || error.message || 'Failed to load emails. Please ensure Gmail API is configured.'
      } finally {
        loading.value = false
      }
    }

    onMounted(loadEmails)

    const selectEmail = (email, index) => {
      selectedEmailIndex.value = index
      console.log('Selected email:', email)
      // TODO: Emit event to parent to show email detail here
    }

    const formatDate = (dateString) => {
      if (!dateString) return ''
      const date = new Date(dateString)
      const today = new Date();
      if (date.toDateString() === today.toDateString()) {
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      }
      const yesterday = new Date(today);
      yesterday.setDate(yesterday.getDate() - 1);
      if (date.toDateString() === yesterday.toDateString()) {
        return 'Yesterday';
      }
      return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
    }

    const getPreview = (body) => {
      if (!body) return ''
      const plainText = body.replace(/<[^>]*>/g, '') 
      return plainText.substring(0, 100) + (plainText.length > 100 ? '...' : '')
    }

    return {
      emails,
      loading,
      errorMessage,
      selectedEmailIndex,
      selectEmail,
      formatDate,
      getPreview,
      loadEmails
    }
  }
}
</script>

<style scoped>
/* --- ERROR / LOADING / NO EMAIL STYLES --- */
.loading, .no-emails {
  text-align: center;
  padding: 3rem;
  color: var(--text-secondary);
  font-size: 1.1rem;
}
.error-box {
  background-color: #fffbeb;
  border: 1px solid #ffe58f;
  border-radius: 6px;
  padding: 1.5rem;
  margin: 1rem 0;
}
.error-box h3 { margin-top: 0; color: #d46b08; font-weight: 700; }
.error-box p { color: #d48806; }
.setup-instructions { margin-top: 1rem; padding: 1rem; background-color: #fff; border-radius: 4px; border: 1px solid var(--light-border-color); }
.setup-instructions ol { margin: 0.5rem 0; padding-left: 1.5rem; }
.setup-instructions code { background-color: #f4f4f4; padding: 2px 6px; border-radius: 3px; font-family: monospace; color: #c41d7f; }

/* === EMAIL ITEM BASE STYLES === */
.email-list {
  display: flex;
  flex-direction: column;
}

.email-item {
  /* Default background for ALL read emails */
  background-color: var(--read-email-bg, #f7f8fa);
  border: none;
  border-bottom: 1px solid var(--border-color, #e0e0e0);
  padding: 1rem 1.25rem; 
  cursor: pointer;
  transition: all 0.2s ease;
  box-shadow: none;
  border-left: 4px solid transparent; 
}

/* UNREAD STATE: overrides background to white */
.email-item.unread {
  background-color: var(--content-bg, #ffffff);
}

.email-item:last-child {
  border-bottom: none;
}

/* Hover state for non-selected items */
.email-item:not(.selected):hover {
  background-color: var(--hover-bg, #f0f4f8);
  transform: none;
  box-shadow: none;
}

/* SELECTED STATE: adds blue side bar and subtle background */
.email-item.selected {
  background-color: var(--hover-bg, #f0f4f8); 
  border-left: 4px solid var(--primary-color, #6C63FF);
}

.email-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

/* --- BASE READ TEXT STYLES (Applies to all unless overridden by .unread) --- */

/* Read Sender: Muted weight/color */
.email-sender {
  font-weight: 500; 
  color: var(--text-secondary); /* Muted gray */
  font-size: 1.05rem;
}

/* Read Subject: Muted weight/color */
.email-subject {
  font-weight: 500; 
  font-size: 1rem;
  color: var(--text-secondary); /* Muted gray */
  margin-bottom: 0.5rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Date and Preview Text (Always Muted) */
.email-date {
  font-size: 0.8rem;
  color: var(--text-secondary);
  font-weight: 500;
}

.email-preview {
  font-size: 0.9rem;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* --- UNREAD OVERRIDES (Only for high contrast) --- */

.email-item.unread .email-sender,
.email-item.unread .email-subject {
  font-weight: 700; /* Unread: Bold */
  color: var(--text-primary, #333); /* Unread: Black/Dark Gray */
}
</style>