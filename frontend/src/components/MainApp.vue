<template>
  <div class="main-app">
    <div class="sidebar">
      <div class="user-info">
        <h2>Novamind.AI</h2>
        <p class="user-name" v-if="currentUser">
          {{ currentUser.user_metadata?.full_name || 'User' }}
        </p>
        <p class="user-email" v-if="currentUser">{{ currentUser.email }}</p>
      </div>

      <div class="nav-buttons">
        <button
          :class="{ active: activeView === 'inbox' }"
          @click="loadInbox"
        >
          Inbox
        </button>
        <button
          :class="{ active: activeView === 'compose' }"
          @click="showCompose"
        >
          Compose
        </button>
      </div>

      <button class="exit-button" @click="exitApp">Logout</button>
    </div>

    <div class="main-content">
      <!-- Welcome View -->
      <div v-if="activeView === 'welcome'">
        <h2>Welcome to Your Email Assistant</h2>
        <p>Select Inbox to view your emails or Compose to send a new message.</p>
      </div>

      <!-- Inbox View -->
      <div v-else-if="activeView === 'inbox'" class="inbox-view">
        <h2>Inbox</h2>

        <!-- Loading State -->
        <div v-if="loading" class="loading">
          <p>Loading emails...</p>
        </div>

        <!-- Error State -->
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

        <!-- Email List -->
        <div v-else-if="emails.length > 0" class="email-list">
          <div
            v-for="(email, index) in emails"
            :key="index"
            class="email-item"
            @click="selectEmail(email)"
          >
            <div class="email-header">
              <span class="email-sender">{{ email.sender }}</span>
              <span class="email-date">{{ formatDate(email.date) }}</span>
            </div>
            <div class="email-subject">{{ email.subject }}</div>
            <div class="email-preview">{{ getPreview(email.body) }}</div>
          </div>
        </div>

        <!-- No Emails -->
        <div v-else class="no-emails">
          <p>No emails found in your inbox.</p>
        </div>
      </div>

      <!-- Compose View -->
      <div v-else-if="activeView === 'compose'" class="compose-view">
        <h2>Compose Email</h2>
        <p>Email composition feature coming soon!</p>
      </div>
    </div>
  </div>
</template>

<script>
import { useAuthStore } from '../stores/auth'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { fetchEmails } from '../api/emails'

export default {
  name: "MainApp",
  setup() {
    const authStore = useAuthStore()
    const router = useRouter()

    // State
    const activeView = ref('welcome')
    const emails = ref([])
    const loading = ref(false)
    const errorMessage = ref('')

    const currentUser = computed(() => authStore.currentUser)

    // Check authentication on mount
    onMounted(async () => {
      // Wait a moment for auth store to initialize
      await new Promise(resolve => setTimeout(resolve, 100))

      if (!authStore.isAuthenticated) {
        router.push('/login')
      }
    })

    // Load inbox emails
    const loadInbox = async () => {
      activeView.value = 'inbox'
      loading.value = true
      errorMessage.value = ''
      emails.value = []

      try {
        const emailList = await fetchEmails()
        emails.value = emailList
      } catch (error) {
        console.error('Error fetching emails:', error)
        errorMessage.value = error.detail || error.message || 'Failed to load emails. Please ensure Gmail API is configured.'
      } finally {
        loading.value = false
      }
    }

    // Show compose view
    const showCompose = () => {
      activeView.value = 'compose'
    }

    // Select email (placeholder for future implementation)
    const selectEmail = (email) => {
      console.log('Selected email:', email)
      // TODO: Open email detail view
    }

    // Format date
    const formatDate = (dateString) => {
      if (!dateString) return ''
      const date = new Date(dateString)
      return date.toLocaleDateString() + ' ' + date.toLocaleTimeString()
    }

    // Get email preview
    const getPreview = (body) => {
      if (!body) return ''
      const plainText = body.replace(/<[^>]*>/g, '') // Remove HTML tags
      return plainText.substring(0, 100) + (plainText.length > 100 ? '...' : '')
    }

    // Logout
    const exitApp = async () => {
      await authStore.logout()
      router.push('/login')
    }

    return {
      currentUser,
      activeView,
      emails,
      loading,
      errorMessage,
      loadInbox,
      showCompose,
      selectEmail,
      formatDate,
      getPreview,
      exitApp
    }
  }
};
</script>

<style>
/* * --------------------------------
 * UPDATED STYLES FOR CONSISTENCY
 * --------------------------------
 */

.main-app {
  display: flex;
  height: 100vh;
  /* Matched the overall lighter background of the application */
  background-color: #f7f7f7; 
}

.sidebar {
  width: 250px;
  background-color: white;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  border-right: 1px solid #ccc;
}

.user-info {
  padding-bottom: 1rem;
  border-bottom: 1px solid #e0e0e0;
  margin-bottom: 0.5rem;
}

.user-info h2 {
  margin: 0 0 0.5rem 0;
  font-size: 1.2rem;
}

.user-name {
  margin: 0.5rem 0 0.2rem 0;
  font-weight: 600;
  font-size: 0.9rem;
  color: #333;
}

.user-email {
  margin: 0;
  font-size: 0.75rem;
  color: #666;
}

.nav-buttons {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  flex: 1;
}

/* Styles for general sidebar buttons (Inbox, Compose) */
.sidebar button:not(.exit-button) {
  padding: 10px; 
  /* Applied the primary blue CTA color */
  background-color: #007bff; 
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 16px;
  text-align: left;
}

.sidebar button:not(.exit-button):hover {
  /* Applied the hover blue color */
  background-color: #0056b3;
}

.exit-button {
  margin-top: auto; /* pushes it to the bottom */
  background-color: #e74c3c;
  color: white;
  border: none;
  padding: 0.5rem;
  cursor: pointer;
  border-radius: 4px; /* Added border-radius for consistency */
  font-size: 16px; /* Added font-size for consistency */
}

.exit-button:hover {
  background-color: #c0392b;
}

.main-content {
  flex: 1;
  padding: 1rem;
  /* Ensured main area background is explicitly white */
  background-color: #ffffff;
}

h2 {
    color: #333;
}

/* Active button state */
.sidebar button.active {
  background-color: #0056b3;
  font-weight: bold;
}

/* Inbox View */
.inbox-view {
  height: 100%;
  overflow-y: auto;
}

.loading {
  text-align: center;
  padding: 2rem;
  color: #666;
}

.error-box {
  background-color: #fff3cd;
  border: 1px solid #ffc107;
  border-radius: 4px;
  padding: 1.5rem;
  margin: 1rem 0;
}

.error-box h3 {
  margin-top: 0;
  color: #856404;
}

.error-box p {
  color: #856404;
}

.setup-instructions {
  margin-top: 1rem;
  padding: 1rem;
  background-color: white;
  border-radius: 4px;
}

.setup-instructions ol {
  margin: 0.5rem 0;
  padding-left: 1.5rem;
}

.setup-instructions code {
  background-color: #f4f4f4;
  padding: 2px 6px;
  border-radius: 3px;
  font-family: monospace;
}

/* Email List */
.email-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.email-item {
  background-color: white;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  padding: 1rem;
  cursor: pointer;
  transition: all 0.2s ease;
}

.email-item:hover {
  background-color: #f8f9fa;
  border-color: #007bff;
  transform: translateY(-1px);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.email-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.email-sender {
  font-weight: 600;
  color: #333;
}

.email-date {
  font-size: 0.85rem;
  color: #666;
}

.email-subject {
  font-weight: 500;
  color: #007bff;
  margin-bottom: 0.5rem;
}

.email-preview {
  font-size: 0.9rem;
  color: #666;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.no-emails {
  text-align: center;
  padding: 3rem;
  color: #666;
}

/* Compose View */
.compose-view {
  padding: 1rem;
}
</style>