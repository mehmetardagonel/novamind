<template>
  <div class="main-app">
    <div class="sidebar">
      <div class="sidebar-header">
        <div class="logo-icon-container">
          <div class="logo-svg novamind-logo">
            <svg fill="none" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
              <path
                d="M24 45.8096C19.6865 45.8096 15.4698 44.5305 11.8832 42.134C8.29667 39.7376 5.50128 36.3314 3.85056 32.3462C2.19985 28.361 1.76794 23.9758 2.60947 19.7452C3.451 15.5145 5.52816 11.6284 8.57829 8.5783C11.6284 5.52817 15.5145 3.45101 19.7452 2.60948C23.9758 1.76795 28.361 2.19986 32.3462 3.85057C36.3314 5.50129 39.7376 8.29668 42.134 11.8833C44.5305 15.4698 45.8096 19.6865 45.8096 24L24 24L24 45.8096Z"
                fill="currentColor"
              ></path>
            </svg>
          </div>
        </div>
        <h2>Novamind.AI</h2>
      </div>
      <p class="welcome-text">Welcome Back!</p>

      <button class="compose-button" @click="goToCompose">
        <span class="material-symbols-outlined">smart_toy</span>
        AI Assistant
      </button>

      <SidebarNav /> 

      <button class="logout-button" @click="exitApp">
        <span class="material-symbols-outlined">logout</span>
        Logout
      </button>
    </div>

    <div class="main-content">
      <div class="main-header">
        <h1>{{ currentPageTitle }}</h1>
      </div>
      <div class="content-view-wrapper">
        <router-view></router-view>
      </div>
    </div>
  </div>
</template>

<script>
import { useAuthStore } from '../stores/auth'
import { onMounted, computed, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import SidebarNav from '../components/SidebarNav.vue'

export default {
  name: "MainApp",
  components: {
    SidebarNav
  },
  setup() {
    const authStore = useAuthStore()
    const router = useRouter()
    const route = useRoute()

    // Removed searchQuery and performSearch, as the search bar is deleted

    onMounted(async () => {
      await new Promise(resolve => setTimeout(resolve, 100))

      if (!authStore.isAuthenticated) {
        router.push('/login')
        return
      }

      // Check if user just completed OAuth
      const storedPath = sessionStorage.getItem('oauth_redirect_path')

      if (storedPath) {
        // Clean up and navigate to stored path
        sessionStorage.removeItem('oauth_redirect_path')
        router.replace(storedPath)
      } else if (router.currentRoute.value.path === '/app') {
        // Default behavior
        router.replace('/app/email/inbox')
      }
    })

    const exitApp = async () => {
      try {
        console.log('Logging out user...')

        // Call enhanced auth store logout (now includes backend cleanup)
        await authStore.logout()

        sessionStorage.removeItem('chat_history')
        sessionStorage.removeItem('chat_session_id')
        // Redirect to home page
        router.push('/home')

        console.log('User logged out and redirected to home')
      } catch (err) {
        console.error('Logout error in MainApp:', err)

        // Always redirect even on error (graceful UX)
        router.push('/home')
      }
    }

    const goToCompose = () => {
      router.push('/app/compose')
    }
    
    // NEW: Computed property for the header title
    const currentPageTitle = computed(() => {
      const path = route.path
      
      if (path.startsWith('/app/compose')) {
        return 'AI Email Assistant'
      } else if (path.includes('/email/inbox')) {
        return 'Inbox'
      } else if (path.includes('/email/sent')) {
        return 'Sent'
      } else if (path.includes('/email/drafts')) {
        return 'Drafts'
      } else if (path.includes('/email/favorites')) {
        return 'Favorites'
      } else if (path.includes('/email/trash')) {
        return 'Trash'
      }
      else if (path.includes('/email/important')) {
        return 'Important'
      } else if (path.includes('/email/spam')) {
        return 'Spam'
      } else if (path.includes('/email/drafts')) {
        return 'Drafts'
      } else if (path.includes('/email/trash')) {
        return 'Trash'
      } else if (path.includes('/email/labels')) {
        return 'Labels'
      } 
      // Fallback for an email detail view (e.g., /app/email/inbox/123)
      else if (path.match(/\/email\/\w+\/\d+/)) {
        // You might fetch the email subject here in a real app, 
        // but for a simple header, we'll return the folder name
        const folder = path.split('/')[3] 
        return `${folder.charAt(0).toUpperCase() + folder.slice(1)}` 
      }
      
      return 'Novamind Mail' // Default
    })

    // Removed showSearchBar as the header is now always present with a title

    return {
      exitApp,
      goToCompose,
      currentPageTitle // Expose the new title to the template
    }
  }
};
</script>

<style scoped>
/* CSS Variables remain the same */
.main-app {
  /* --- Brand Color Palette --- */
  --primary-color: #6C63FF; 
  --primary-color-light: #f0f0ff; 
  --primary-hover-color: #574BDB;
  --danger-color: #e74c3c;
  --danger-hover-color: #c0392b;
  
  /* --- Layout & Greyscale Palette --- */
  --app-bg: #f7f8fa; 
  --sidebar-bg: #ffffff;
  --content-bg: #ffffff;
  --border-color: #e0e0e0;
  --light-border-color: #f0f0f0;
  --hover-bg: #f5f5f5; 
  --read-email-bg: #f7f8fa; 

  /* --- Typography Palette --- */
  --text-primary: #333;
  --text-secondary: #5f6368;
  --text-on-primary: #ffffff; 
  --text-brand: var(--primary-color);

  /* --- Base Layout --- */
  display: flex;
  height: 100vh;
  background-color: var(--app-bg); 
}

/* * SIDEBAR */
.sidebar {
  width: 250px; 
  flex-shrink: 0; 
  background-color: var(--sidebar-bg);
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--border-color);
  z-index: 10;
  gap: 1rem;
}

/* * SIDEBAR HEADER (was .user-info) */
.sidebar-header {
  padding-left: 0.5rem;
  padding-right: 0.5rem;
  /* NEW: Flexbox for logo + text */
  display: flex;
  align-items: center;
  gap: 10px;
}

.logo-icon-container {
  position: relative;
  width: 2rem; /* Keep a fixed width for the icons */
  height: 2rem; /* Keep a fixed height for the icons */
}

/* Base style for both icons inside the container */
.logo-svg {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  color: var(--primary-color);
  transition: opacity 0.3s ease, transform 0.3s ease;
}

/* 1. Novamind Logo (Default State) */
.novamind-logo {
  opacity: 1; 
  transform: scale(1); 
  z-index: 2; /* On top when visible */
}

.sidebar-header h2 {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 700;
  /* UPDATED: Changed from text-brand to text-primary (black) */
  color: var(--text-primary); 
}

/* UPDATED: Renamed from .sidebar-header p */
.welcome-text {
  margin: -0.75rem 0 0.5rem 0.5rem; /* Tucked under header */
  font-size: 0.9rem;
  color: var(--text-secondary);
}

/* * COMPOSE BUTTON */
.compose-button {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  background-color: var(--primary-color);
  color: var(--text-on-primary);
  border: none;
  padding: 12px;
  cursor: pointer;
  border-radius: 10px; 
  font-size: 15px; 
  font-weight: 600;
  transition: all 0.2s ease;
  box-shadow: 0 4px 12px rgba(108, 99, 255, 0.3);
}

.compose-button:hover {
  background-color: var(--primary-hover-color);
  box-shadow: 0 6px 16px rgba(108, 99, 255, 0.4);
}

.compose-button .material-symbols-outlined {
  font-size: 20px;
}

/* * LOGOUT BUTTON */
.logout-button {
  margin-top: auto; 
  background-color: transparent;
  border: none;
  box-shadow: none;
  color: var(--text-secondary);
  font-weight: 500;
  padding: 10px 20px;
  border-radius: 10px; 
  text-align: left;
  cursor: pointer;
  font-size: 16px;
  transition: background-color 0.2s ease, color 0.2s ease;
  display: flex; 
  align-items: center;
  gap: 10px; 
  width: 100%;
}

.logout-button:hover {
  background-color: var(--hover-bg);
  color: var(--text-primary);
}

.logout-button .material-symbols-outlined { 
  font-size: 20px;
}

/* * MAIN CONTENT AREA */
.main-content {
  flex: 1;
  background-color: var(--content-bg);
  height: 100vh;
  display: flex;
  flex-direction: column;
  overflow-y: hidden;
}

/* * MAIN HEADER (FOR PAGE TITLE) */
.main-header {
  padding: 1.25rem 2rem;
  border-bottom: 1px solid var(--border-color);
  background-color: var(--content-bg);
  z-index: 5;
}

/* NEW: Style for the page title in the header */
.main-header h1 {
  margin: 0;
  font-size: 1.75rem;
  font-weight: 600;
  color: var(--text-primary);
}

/* Removed search-bar, search-bar input, etc. CSS */

/* * CONTENT VIEW WRAPPER */
.content-view-wrapper {
  flex: 1;
  overflow-y: auto;
  /* Removed the conditional padding logic as the header is now always present */
}
</style>