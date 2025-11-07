<template>
  <div class="main-app">
    <div class="sidebar">
      <div class="user-info">
        <h2>Novamind.AI</h2>
        <p class="user-name" v-if="currentUser">
          {{ currentUser.full_name || currentUser.username }}
        </p>
        <p class="user-email" v-if="currentUser">{{ currentUser.email }}</p>
      </div>

      <div class="nav-buttons">
        <button>Inbox</button>
        <button>Compose</button>
      </div>

      <button class="exit-button" @click="exitApp">Logout</button>
    </div>

    <div class="main-content">
      <h2>Welcome to Your Email Assistant</h2>
      <p>Select an option from the sidebar to get started.</p>
      <p>Email management features coming soon!</p>
    </div>
  </div>
</template>

<script>
import { useAuthStore } from '../stores/auth'
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'

export default {
  name: "MainApp",
  setup() {
    const authStore = useAuthStore()
    const router = useRouter()

    const currentUser = computed(() => authStore.currentUser)

    // Check authentication on mount
    onMounted(() => {
      if (!authStore.isAuthenticated) {
        router.push('/login')
      }
    })

    const exitApp = () => {
      authStore.logout()
      router.push('/login')
    }

    return {
      currentUser,
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
</style>