<template>
  <div class="email-list-view">
    <div v-if="loading" class="loading">
      <p>Loading emails...</p>
    </div>

    <!-- THIS IS THE NEW PART THAT HANDLES THE 401 -->
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

    <div v-else-if="emails.length > 0" class="email-list">
      <div
        v-for="(email, index) in emails"
        :key="index"
        class="email-item"
        :class="{ 
          'unread': email.unread, 
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
      <p>No emails found.</p>
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
    const authUrl = ref('') // <--- State for the Auth URL

    const loadEmails = async () => {
      loading.value = true
      errorMessage.value = ''
      emails.value = []
      selectedEmailIndex.value = null 
      authUrl.value = '' // <--- Reset auth URL

      try {
        console.log(`Fetching emails for folder: ${props.folder}`)
        // Note: The backend must return an 'unread' boolean field on each email object.
        const emailList = await fetchEmails(props.folder) 
        emails.value = emailList
      } catch (error) {
        console.error(`Error fetching ${props.folder} emails:`, error)
        
        // <--- THIS LOGIC CATCHES THE 401 RESPONSE
        if (error.response && error.response.status === 401 && error.response.data.auth_url) {
            authUrl.value = error.response.data.auth_url;
            errorMessage.value = ''; // Clear generic error message
        } else {
            // Original logic for all other errors
            errorMessage.value = error.response?.data?.detail 
                               || error.message 
                               || 'Failed to load emails. Please ensure Gmail API is configured.'
        }
      } finally {
        loading.value = false
      }
    }
    
    // <--- THIS METHOD REDIRECTS THE USER TO GOOGLE
    const authenticate = () => {
      if (authUrl.value) {
        window.location.href = authUrl.value;
      } else {
        errorMessage.value = "Authentication URL is missing. Please try reloading the page.";
      }
    }

    // --- FIX: Force reload after successful auth redirect ---
    onMounted(() => {
        // 1. Check if the URL contains the success status from the backend redirect
        const params = new URLSearchParams(window.location.search);
        const authStatus = params.get('auth_status');

        if (authStatus === 'success') {
            // 2. Clear the query parameter to prevent repeated reloads if user navigates away
            window.history.replaceState(null, '', window.location.pathname);
        }
        
        // 3. Load emails on mount (this will now succeed if we just authenticated)
        loadEmails();
    })

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
      authUrl, // <--- Expose authUrl
      selectEmail,
      formatDate,
      getPreview,
      loadEmails,
      authenticate // <--- Expose authenticate method
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
/* --- Auth Prompt Styles --- */
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

/* === EMAIL ITEM BASE STYLES === */
.email-list {
  display: flex;
  flex-direction: column;
}

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
</style>