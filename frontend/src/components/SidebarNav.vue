<template>
  <div class="nav-buttons">
    <router-link
      v-for="item in navItems"
      :key="item.view"
      :to="item.to"
      custom
      v-slot="{ href, navigate, isActive }"
    >
      <button
        :href="href"
        @click="navigate"
        :class="{ active: isActive || (item.view === 'inbox' && $route.path === '/app/email') }"
      >
        <span class="material-symbols-outlined">{{ item.icon }}</span>
        {{ item.label }}
      </button>
    </router-link>
  </div>
</template>

<script>
import { RouterLink, useRoute } from 'vue-router' 
import { computed } from 'vue';

export default {
  name: 'SidebarNav',
  components: {
    RouterLink,
  },
  setup() {
    const route = useRoute();

    // UPDATED: Added 'Favorites' and 'AI Assistant'
     const navItems = computed(() => [
      { view: 'inbox', label: 'Inbox', icon: 'inbox', to: '/app/email/inbox' },
      { view: 'sent', label: 'Sent', icon: 'send', to: '/app/email/sent' },
      { view: 'favorites', label: 'Favorites', icon: 'star', to: '/app/email/favorites' },
      { view: 'important', label: 'Important', icon: 'label_important', to: '/app/email/important' },
      { view: 'spam', label: 'Spam', icon: 'report', to: '/app/email/spam' },
      { view: 'drafts', label: 'Drafts', icon: 'draft', to: '/app/email/drafts' },
      { view: 'trash', label: 'Trash', icon: 'delete', to: '/app/email/trash' },
      { view: 'labels', label: 'Labels', icon: 'label', to: '/app/email/labels' },
      { view: 'ai-assistant', label: 'AI Assistant', icon: 'smart_toy', to: '/app/compose' },
    ]);

    return {
      navItems,
      route
    }
  }
}
</script>

<style scoped>
/* Icon style */
.nav-buttons .material-symbols-outlined {
    font-size: 20px;
}

/* Base style for all nav buttons */
.nav-buttons button {
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

/* Hover state for INACTIVE items */
.nav-buttons button:not(.active):hover {
  background-color: var(--hover-bg);
  color: var(--text-primary);
}

/* Active (chosen) item style */
.nav-buttons button.active {
  background-color: var(--primary-color-light, #f0f0ff);
  color: var(--primary-color, #6C63FF);
  font-weight: 700;
  box-shadow: none; 
}

/* Keep active item solid on hover */
.nav-buttons button.active:hover {
  background-color: var(--primary-color-light, #f0f0ff);
  color: var(--primary-color, #6C63FF);
}
</style>