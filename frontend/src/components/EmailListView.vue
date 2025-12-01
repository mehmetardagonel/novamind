<template>
  <div class="email-list-view">
    <div v-if="loading" class="loading">
      <p>Loading emails...</p>
    </div>

    <div v-else-if="authUrl" class="auth-prompt">
      <h2>Gmail Authentication Required</h2>
      <p>Please connect your Google account to fetch emails.</p>
      <button @click="authenticate" class="btn btn-primary">
        Connect with Google
      </button>
      <p v-if="errorMessage" class="text-danger mt-3">Error: {{ errorMessage }}</p>
    </div>
    
    <div v-else-if="errorMessage" class="error-box">
      <h3>Gmail API Error</h3>
      <p>{{ errorMessage }}</p>
      <div class="setup-instructions">
        <p><strong>Troubleshooting:</strong></p>
        <ol>
          <li>Ensure backend is running.</li>
          <li>Ensure <code>.env</code> file is correct.</li>
          <li>If auth fails, try deleting <code>token.json</code> and re-authenticating.</li>
        </ol>
      </div>
    </div>

    <div v-else-if="emails.length > 0" class="email-container" :class="{ 'has-detail': selectedEmail && !isTrash }">
      
      <div class="email-list-panel" :class="{ 'hide-on-mobile': selectedEmail && !isTrash, 'full-width': !selectedEmail || isTrash }">
        <div class="email-list">
          <div
          v-for="(email, index) in emails"
          :key="index"
          class="email-item"
          :class="{
          'unread': email.unread,
          'selected': email === selectedEmail
          }"
          @click="!isTrash && selectEmail(email)"
          >
            <div class="email-header">
              <span class="email-sender">{{ email.sender }}</span>
              <span class="email-date">{{ formatDate(email.date) }}</span>
            </div>
            <div class="email-subject">{{ email.subject }}</div>
            <div class="email-preview">{{ getPreview(email.body) }}</div>
            <button
            v-if="isTrash"
            class="restore-btn"
            @click.stop="handleRestore(email)"
            >
            Restore
            </button>
          </div>
        </div>
        </div>

      <div class="email-detail-panel" v-if="selectedEmail && !isTrash">
        <div class="email-detail-header">
        <button @click="closeEmail" class="icon-action-btn" title="Back to list">
          <span class="material-symbols-outlined">arrow_back</span>
        </button>

        <div class="email-actions" v-if="!isTrash">
          <button class="icon-action-btn" title="Add Label">
            <span class="material-symbols-outlined">label</span>
          </button>
          
          <button class="icon-action-btn" title="Favorite"  @click.stop="handleFavorite">
            <span class="material-symbols-outlined">star</span>
          </button>
          
          <button class="icon-action-btn" title="Delete"  @click.stop="handleDelete">
            <span class="material-symbols-outlined">delete</span>
          </button>
        </div>
      </div>
        
        <div class="email-detail-content">
          <h2 class="email-detail-subject">{{ selectedEmail.subject }}</h2>
          
          <div class="email-detail-meta">
            <div class="sender-info">
              <div class="sender-details">
                <div class="sender-name">{{ selectedEmail.sender }}</div>
                <div class="email-date-full">{{ formatFullDate(selectedEmail.date) }}</div>
              </div>
            </div>
          </div>

          <div class="email-body" v-html="sanitizeHtml(selectedEmail.body)"></div>
        </div>
      </div>
    </div>

    <div v-else class="no-emails">
      <p>No emails found.</p>
    </div>
  </div>
</template>

<script>
import { onMounted, ref, watch, computed } from 'vue'
import { fetchEmails, deleteEmail, setEmailStar, restoreEmail } from '../api/emails'

export default {
  name: "EmailListView",
  props: {
    folder: {
      type: String,
      required: true,
      default: 'inbox'
    }
    // Removed emailsPerPage prop
  },
  setup(props) {
    const emails = ref([])
    const loading = ref(false)
    const errorMessage = ref('')
    const selectedEmail = ref(null)
    const authUrl = ref('')
    const isTrash = computed(() => props.folder === 'trash')
    const MAX_RETRIES = 2
    const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

 const loadEmails = async () => {
  loading.value = true
  errorMessage.value = ''
  emails.value = []
  selectedEmail.value = null
  authUrl.value = ''

  for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
    try {
      console.log(`Fetching emails for folder: ${props.folder} (attempt ${attempt})`)
      const emailList = await fetchEmails(props.folder)
      emails.value = emailList

      // ✅ Success: stop retrying
      loading.value = false
      return
    } catch (error) {
      console.error(`Error fetching ${props.folder} emails (attempt ${attempt}):`, error)
      const hasResponse = !!error.response

      // 1️⃣ Pure network / backend not reachable
      if (!hasResponse) {
        if (attempt < MAX_RETRIES) {
          console.warn('Network/backend error, retrying...')
          await sleep(1000)
          continue
        }

        // All retries failed → show proper backend error
        errorMessage.value =
          'Cannot reach the backend API. Make sure the FastAPI server is running.'
        loading.value = false
        return
      }

      // 2️⃣ 401 with auth_url → Gmail OAuth flow
      if (error.response.status === 401 && error.response.data.auth_url) {
        authUrl.value = error.response.data.auth_url
        errorMessage.value = ''
        loading.value = false
        return
      }

      // 3️⃣ Real backend/Gmail error
      errorMessage.value =
        error.response?.data?.detail ||
        error.message ||
        'Failed to load emails. Please ensure Gmail API is configured.'
      loading.value = false
      return
    }
  }

  // Safety – should never really hit here, but just in case
  loading.value = false
}
    
    const authenticate = () => {
      if (authUrl.value) {
        // Store current path before redirecting to OAuth
        sessionStorage.setItem('oauth_redirect_path', window.location.pathname)
        window.location.href = authUrl.value
      } else {
        errorMessage.value = "Authentication URL is missing. Please try reloading the page."
      }
    }
      const handleFavorite = async () => {
      if (!selectedEmail.value) return

      try {
        const messageId = selectedEmail.value.message_id

        // For now: always star it (backend handles it)
        await setEmailStar(messageId, true)

        // Optional: mark as starred locally so UI can react if you later style it
        selectedEmail.value = {
          ...selectedEmail.value,
          starred: true
        }

        // Also update in the list
        emails.value = emails.value.map(email =>
          email.message_id === messageId
            ? { ...email, starred: true }
            : email
        )

      } catch (error) {
        console.error('Failed to favorite email:', error)
        errorMessage.value = error.response?.data?.detail
          || error.message
          || 'Failed to favorite email.'
      }
    }

    const handleDelete = async () => {
      if (!selectedEmail.value) return

      try {
        const messageId = selectedEmail.value.message_id

        await deleteEmail(messageId)

        // Remove from list
        emails.value = emails.value.filter(
          email => email.message_id !== messageId
        )

        // Close detail view
        selectedEmail.value = null
      } catch (error) {
        console.error('Failed to delete email:', error)
        errorMessage.value = error.response?.data?.detail
          || error.message
          || 'Failed to delete email.'
      }
    }

    const handleRestore = async (email) => {
  try {
    const messageId = email.message_id
    await restoreEmail(messageId)

    // Remove from list
    emails.value = emails.value.filter(e => e.message_id !== messageId)

    // Just in case it was selected somehow
    if (selectedEmail.value && selectedEmail.value.message_id === messageId) {
      selectedEmail.value = null
    }
  } catch (error) {
    console.error('Failed to restore email:', error)
    errorMessage.value =
      error.response?.data?.detail ||
      error.message ||
      'Failed to restore email.'
  }
}

    onMounted(() => {
        loadEmails()
    })

    watch(() => props.folder, () => {
      loadEmails()
    })

    const selectEmail = (email) => {
      selectedEmail.value = email
    }

    const closeEmail = () => {
      selectedEmail.value = null
    }

    const formatDate = (dateString) => {
      if (!dateString) return ''
      const date = new Date(dateString)
      const today = new Date()
      if (date.toDateString() === today.toDateString()) {
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      }
      const yesterday = new Date(today)
      yesterday.setDate(yesterday.getDate() - 1)
      if (date.toDateString() === yesterday.toDateString()) {
        return 'Yesterday'
      }
      return date.toLocaleDateString([], { month: 'short', day: 'numeric' })
    }

    const formatFullDate = (dateString) => {
      if (!dateString) return ''
      const date = new Date(dateString)
      return date.toLocaleString([], { 
        weekday: 'short',
        year: 'numeric', 
        month: 'short', 
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      })
    }

    const getPreview = (body) => {
      if (!body) return ''
      const plainText = body.replace(/<[^>]*>/g, '') 
      return plainText.substring(0, 100) + (plainText.length > 100 ? '...' : '')
    }

    const sanitizeHtml = (html) => {
      if (!html) return ''
      return html
    }

    return {
    emails,
    loading,
    errorMessage,
    selectedEmail,
    authUrl,
    selectEmail,
    closeEmail,
    handleFavorite,
    handleDelete,
    handleRestore,  
    isTrash,        
    // plus existing helpers:
    formatDate,
    formatFullDate,
    getPreview,
    sanitizeHtml,
    loadEmails,
    authenticate,
  }
  }
}
</script>

<style scoped>
/* Standard Loading & Error Styles */
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

.auth-prompt {
  background-color: #e6f7ff;
  border: 1px solid #91d5ff;
  border-radius: 6px;
  padding: 2rem;
  margin: 1rem 0;
  text-align: center;
}

.auth-prompt h2 { color: #0050b3; margin-bottom: 0.5rem; }
.auth-prompt p { color: #0050b3; }

.btn-primary {
    background-color: #4285F4;
    color: white;
    border: none;
    padding: 12px 25px;
    cursor: pointer;
    border-radius: 4px;
    font-size: 1rem;
    margin-top: 1rem;
    transition: background-color 0.2s;
}
.btn-primary:hover {
    background-color: #337ae2;
}

.error-box h3 { margin-top: 0; color: #d46b08; font-weight: 700; }
.error-box p { color: #d48806; }
.setup-instructions { margin-top: 1rem; padding: 1rem; background-color: #fff; border-radius: 4px; border: 1px solid var(--light-border-color); }
.setup-instructions ol { margin: 0.5rem 0; padding-left: 1.5rem; }

/* Email Container */
.email-container {
  display: flex;
  height: calc(100vh - 200px);
  gap: 0;
  overflow: hidden;
}

.email-list-panel {
  flex: 0 0 400px;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--border-color, #e0e0e0);
  overflow: hidden;
}

.email-list-panel.full-width {
  flex: 1;
  border-right: none;
}

/* IMPORTANT: This ensures the list scrolls if there are too many items
*/
.email-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.email-detail-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background-color: var(--content-bg, #ffffff);
}

/* Email Item Styles */
.email-item {
  background-color: var(--read-email-bg, #f7f8fa);
  border: none;
  border-bottom: 1px solid var(--border-color, #e0e0e0);
  padding: 1rem 1.25rem; 
  cursor: pointer;
  transition: all 0.2s ease;
  box-shadow: none;
  border-left: 4px solid transparent; 
}

.email-item.unread {
  background-color: var(--content-bg, #ffffff);
}

.email-item:last-child {
  border-bottom: none;
}

.email-item:not(.selected):hover {
  background-color: var(--hover-bg, #f0f4f8);
}

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

.email-sender {
  font-weight: 500; 
  color: var(--text-secondary);
  font-size: 1.05rem;
}

.email-subject {
  font-weight: 500; 
  font-size: 1rem;
  color: var(--text-secondary);
  margin-bottom: 0.5rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

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

.email-item.unread .email-sender,
.email-item.unread .email-subject {
  font-weight: 700;
  color: var(--text-primary, #333);
}
.email-item:not(.selected):hover {
  background-color: var(--hover-bg, #f0f4f8);
  cursor: pointer;
  border-left: 4px solid rgba(108, 99, 255, 0.3);
}

/* REMOVED: All .pagination related styles */

/* Email Detail Styles */
.email-detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.5rem;
  border-bottom: 1px solid var(--border-color, #e0e0e0);
  background-color: var(--content-bg, #ffffff);
}

/* Email Detail Header Styles */
.email-detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.5rem;
  border-bottom: 1px solid var(--border-color, #e0e0e0);
  background-color: var(--content-bg, #ffffff);
}

.email-actions {
  display: flex;
  gap: 0.5rem;
}

/* Unified Button Style for Material Icons */
.icon-action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;  /* Fixed width for square shape */
  height: 40px; /* Fixed height */
  padding: 0;
  border: 1px solid var(--border-color, #e0e0e0);
  background-color: var(--content-bg, #ffffff);
  border-radius: 4px; /* Keep your existing rounded look, or use 50% for circles */
  cursor: pointer;
  color: var(--text-secondary, #666); /* Icon color */
  transition: all 0.2s ease;
}

.icon-action-btn:hover {
  background-color: var(--hover-bg, #f0f4f8);
  color: var(--text-primary, #333);
  border-color: #d0d0d0;
}

/* Material Symbol Font Size Settings */
.material-symbols-outlined {
  font-size: 20px; /* Adjust size of the icon inside the button */
  font-variation-settings:
  'FILL' 0,
  'wght' 400,
  'GRAD' 0,
  'opsz' 24
}

.email-actions {
  display: flex;
  gap: 0.5rem;
}


.email-detail-content {
  flex: 1;
  overflow-y: auto;
  padding: 2rem;
}

.email-detail-subject {
  font-size: 1.5rem;
  margin: 0 0 1.5rem 0;
  color: var(--text-primary, #333);
}

.email-detail-meta {
  margin-bottom: 2rem;
  padding-bottom: 1.5rem;
  border-bottom: 1px solid var(--border-color, #e0e0e0);
}

.sender-info {
  display: flex;
  align-items: center;
}

.sender-details {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.sender-name {
  font-weight: 600;
  color: var(--text-primary, #333);
  font-size: 1.1rem;
}

.email-date-full {
  font-size: 0.9rem;
  color: var(--text-secondary);
}

.email-body {
  line-height: 1.6;
  color: var(--text-primary, #333);
}

/* Mobile Responsive */
@media (max-width: 768px) {
 .email-container {
  display: flex;
  height: calc(100vh - 100px); 
  gap: 0;
  overflow: hidden;
}

  .email-list-panel {
    flex: 0 0 auto;
    border-right: none;
    border-bottom: 1px solid var(--border-color, #e0e0e0);
    max-height: none;
  }

  .email-list-panel.full-width {
    flex: 1;
  }

  .email-list-panel.hide-on-mobile {
    display: none;
  }

  .email-detail-panel {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 100;
  }
}
</style>