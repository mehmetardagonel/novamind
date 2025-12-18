<template>
  <div class="main-app" :class="themeClass">
    <!-- Mobile overlay -->
    <div class="sidebar-overlay" :class="{ active: isSidebarOpen }" @click="toggleSidebar"></div>

    <div class="sidebar" :class="{ open: isSidebarOpen }">
      <div class="sidebar-header">
        <div class="logo-icon-container">
          <div class="logo-svg novamind-logo">
            <svg
              fill="none"
              viewBox="0 0 48 48"
              xmlns="http://www.w3.org/2000/svg"
            >
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
        <!-- Mobile hamburger menu -->
        <button class="hamburger-menu" @click="toggleSidebar">
          <span class="material-symbols-outlined">menu</span>
        </button>

        <h1>{{ currentPageTitle }}</h1>

        <!-- Account Selector (only show on inbox) -->
        <div v-if="isInboxView" class="account-selector">
          <span class="material-symbols-outlined selector-icon">account_circle</span>
          <select
            v-model="selectedAccountId"
            class="account-dropdown"
          >
            <option :value="null">Tüm Hesaplar</option>
            <option
              v-for="account in accounts"
              :key="account.id"
              :value="account.id"
            >
              {{ account.email_address }}
              <span v-if="account.is_primary"> ⭐</span>
            </option>
          </select>
        </div>

        <button
          class="theme-toggle-btn"
          @click="toggleTheme"
          title="Toggle Theme"
        >
          <span class="material-symbols-outlined">
            {{ isDarkTheme ? "light_mode" : "dark_mode" }}
          </span>
        </button>
      </div>
      <div class="content-view-wrapper">
        <router-view :selected-account-id="selectedAccountId"></router-view>
      </div>
    </div>
  </div>
</template>

<script>
import { useAuthStore } from "../stores/auth";
import { onMounted, computed, ref } from "vue";
import { useRouter, useRoute } from "vue-router";
import SidebarNav from "../components/SidebarNav.vue";
import { fetchGmailAccounts } from "../api/accounts";

export default {
  name: "MainApp",
  components: {
    SidebarNav,
  },
  setup() {
    const authStore = useAuthStore();
    const router = useRouter();
    const route = useRoute();
    const isDarkTheme = ref(false);
    const accounts = ref([]);
    const selectedAccountId = ref(null);
    const isSidebarOpen = ref(false);

    // Removed searchQuery and performSearch, as the search bar is deleted
    const toggleTheme = () => {
      isDarkTheme.value = !isDarkTheme.value;
    };

    const toggleSidebar = () => {
      isSidebarOpen.value = !isSidebarOpen.value;
    };

    const themeClass = computed(() => {
      return isDarkTheme.value ? "dark-theme" : "";
    });

    // Check if we're on inbox view
    const isInboxView = computed(() => {
      return route.path.includes('/email/inbox') || route.path === '/app';
    });

    onMounted(async () => {
      await new Promise((resolve) => setTimeout(resolve, 100));

      if (!authStore.isAuthenticated) {
        router.push("/login");
        return;
      }

      // Load Gmail accounts for account selector
      try {
        accounts.value = await fetchGmailAccounts();
      } catch (error) {
        console.error("Failed to load Gmail accounts:", error);
      }

      // Check if user just completed OAuth
      const storedPath = sessionStorage.getItem("oauth_redirect_path");

      if (storedPath) {
        // Clean up and navigate to stored path
        sessionStorage.removeItem("oauth_redirect_path");
        router.replace(storedPath);
      } else if (router.currentRoute.value.path === "/app") {
        // Default behavior
        router.replace("/app/email/inbox");
      }
    });

    const exitApp = async () => {
      try {
        console.log("Logging out user...");

        // Call enhanced auth store logout (now includes backend cleanup)
        await authStore.logout();

        sessionStorage.removeItem("chat_history");
        sessionStorage.removeItem("chat_session_id");
        // Redirect to home page
        router.push("/home");

        console.log("User logged out and redirected to home");
      } catch (err) {
        console.error("Logout error in MainApp:", err);

        // Always redirect even on error (graceful UX)
        router.push("/home");
      }
    };

    const goToCompose = () => {
      router.push("/app/compose");
    };

    // NEW: Computed property for the header title
    const currentPageTitle = computed(() => {
      const path = route.path;

      if (path.startsWith("/app/compose")) {
        return "AI Email Assistant";
      } else if (path.includes("/email/inbox")) {
        const labelName = route.query.labelName;
        if (labelName) {
          return `Label: ${labelName}`; // 👈 e.g. "Label: Work"
        }
        return "Inbox";
      } else if (path.includes("/email/sent")) {
        return "Sent";
      } else if (path.includes("/email/drafts")) {
        return "Drafts";
      } else if (path.includes("/email/favorites")) {
        return "Favorites";
      } else if (path.includes("/email/trash")) {
        return "Trash";
      } else if (path.includes("/email/important")) {
        return "Important";
      } else if (path.includes("/email/spam")) {
        return "Spam";
      } else if (path.includes("/email/drafts")) {
        return "Drafts";
      } else if (path.includes("/email/trash")) {
        return "Trash";
      } else if (path.includes("/email/labels")) {
        return "Labels";
      }
      // Fallback for an email detail view (e.g., /app/email/inbox/123)
      else if (path.match(/\/email\/\w+\/\d+/)) {
        // You might fetch the email subject here in a real app,
        // but for a simple header, we'll return the folder name
        const folder = path.split("/")[3];
        return `${folder.charAt(0).toUpperCase() + folder.slice(1)}`;
      }

      return "Novamind Mail"; // Default
    });

    // Removed showSearchBar as the header is now always present with a title

    return {
      exitApp,
      goToCompose,
      currentPageTitle, // Expose the new title to the template
      isDarkTheme,
      toggleTheme,
      themeClass,
      accounts,
      selectedAccountId,
      isInboxView,
      isSidebarOpen,
      toggleSidebar,
    };
  },
};
</script>

<style scoped>
/* CSS Variables remain the same */
.main-app {
  /* --- Brand Color Palette --- */
  --primary-color: #6c63ff;
  --primary-color-light: #f0f0ff;
  --primary-hover-color: #574bdb;
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

.main-app.dark-theme {
  /* --- Layout & Greyscale Palette (DARK MODE) --- */
  --app-bg: #1f2023; /* Dark background */
  --sidebar-bg: #28292c; /* Slightly lighter dark for sidebar */
  --content-bg: #1f2023; /* Dark background for main content */
  --border-color: #3d3e42; /* Darker border */
  --light-border-color: #333438;
  --hover-bg: #333438; /* Darker hover state */
  --read-email-bg: #28292c; /* Background for read emails */

  /* --- Typography Palette (DARK MODE) --- */
  --text-primary: #f0f0f0; /* White/light grey for main text */
  --text-secondary: #aaaaaa; /* Medium grey for secondary text */
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

  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.theme-toggle-btn {
  margin-left: auto; /* Push to the far right */
  background: transparent;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  padding: 4px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s, color 0.2s;
}

.theme-toggle-btn:hover {
  background-color: var(--hover-bg);
  color: var(--primary-color);
}

/* NEW: Style for the page title in the header */
.main-header h1 {
  margin: 0;
  font-size: 1.75rem;
  font-weight: 600;
  color: var(--text-primary);
  flex-grow: 1;
  text-align: left;
}

/* Account Selector Styles */
.account-selector {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-left: auto;
  margin-right: 1rem;
}

.selector-icon {
  font-size: 1.2rem;
  color: var(--text-secondary);
}

.account-dropdown {
  padding: 0.5rem 2rem 0.5rem 0.75rem;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background-color: var(--content-bg);
  color: var(--text-primary);
  font-size: 0.9rem;
  cursor: pointer;
  transition: all 0.2s ease;
  appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%23666' d='M6 9L1 4h10z'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 0.5rem center;
  min-width: 200px;
}

.account-dropdown:hover {
  border-color: var(--primary-color);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.account-dropdown:focus {
  outline: none;
  border-color: var(--primary-color);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.account-dropdown option {
  padding: 0.5rem;
}

/* Removed search-bar, search-bar input, etc. CSS */

/* * CONTENT VIEW WRAPPER */
.content-view-wrapper {
  flex: 1;
  overflow-y: auto;
  /* Removed the conditional padding logic as the header is now always present */
}

/* * HAMBURGER MENU BUTTON */
.hamburger-menu {
  display: none; /* Hidden by default on desktop */
  background: transparent;
  border: none;
  color: var(--text-primary);
  cursor: pointer;
  padding: 8px;
  border-radius: 8px;
  transition: background 0.2s;
}

.hamburger-menu:hover {
  background-color: var(--hover-bg);
}

.hamburger-menu .material-symbols-outlined {
  font-size: 24px;
}

/* * SIDEBAR OVERLAY (for mobile) */
.sidebar-overlay {
  display: none;
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(0, 0, 0, 0.5);
  z-index: 998;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.3s ease;
}

.sidebar-overlay.active {
  display: block;
  opacity: 1;
  pointer-events: auto;
}

/* ========== RESPONSIVE DESIGN - MOBILE & TABLET ========== */

/* Tablet and below (≤1024px) */
@media (max-width: 1024px) {
  .sidebar {
    position: fixed;
    top: 0;
    left: -250px; /* Hidden by default */
    height: 100vh;
    z-index: 999;
    transition: left 0.3s ease;
    box-shadow: 2px 0 10px rgba(0, 0, 0, 0.1);
  }

  .sidebar.open {
    left: 0; /* Slide in when open */
  }

  .hamburger-menu {
    display: flex; /* Show hamburger on tablet/mobile */
    align-items: center;
    justify-content: center;
  }

  .main-header h1 {
    font-size: 1.4rem;
  }

  .account-selector {
    margin-right: 0.5rem;
  }

  .account-dropdown {
    min-width: 150px;
    font-size: 0.85rem;
  }
}

/* Mobile (≤768px) */
@media (max-width: 768px) {
  .main-header {
    padding: 1rem;
    gap: 0.5rem;
  }

  .main-header h1 {
    font-size: 1.2rem;
    flex-shrink: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  /* Hide account selector on small mobile */
  .account-selector {
    display: none;
  }

  .theme-toggle-btn {
    padding: 6px;
  }

  /* Adjust sidebar width for mobile */
  .sidebar {
    width: 280px;
    left: -280px;
  }

  .sidebar-header h2 {
    font-size: 1.3rem;
  }

  .compose-button {
    padding: 10px;
    font-size: 14px;
  }

  .nav-buttons button {
    padding: 12px 16px;
    font-size: 15px;
  }
}

/* Small Mobile (≤480px) */
@media (max-width: 480px) {
  .sidebar {
    width: 85%; /* Use percentage for very small screens */
    max-width: 280px;
    left: -100%;
  }

  .main-header h1 {
    font-size: 1.1rem;
  }

  .hamburger-menu .material-symbols-outlined {
    font-size: 22px;
  }

  .theme-toggle-btn .material-symbols-outlined {
    font-size: 20px;
  }
}
</style>
