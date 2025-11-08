// src/stores/authStore.js

import { defineStore } from 'pinia';
import { supabase } from '@/database/supabaseClient'; 

export const useAuthStore = defineStore('auth', {
  
  // STATE: The data we want to share
  state: () => ({
    user: null, 
  }),

  // GETTERS: Computed properties for reading the state
  getters: {
    isLoggedIn: (state) => !!state.user,
    
    userEmail: (state) => {
      return state.user ? state.user.email : '';
    },
    
    username: (state) => {
      if (state.user && state.user.email) {
        return state.user.email.split('@')[0];
      }
      return 'Guest';
    }
  },

  // ACTIONS: Methods to change the state or call the API
  actions: {
    
    setUser(user) {
      this.user = user;
    },

    async fetchUser() {
      try {
        const { data, error } = await supabase.auth.getUser();
        if (error) throw error;
        
        this.user = data.user;
        return this.user;

      } catch (error) {
        this.user = null;
        return null;
      }
    },
    
    async handleLogout() {
      try {
        const { error } = await supabase.auth.signOut();
        if (error) throw error;
        this.user = null;
        
      } catch (error) {
        console.error('Error logging out:', error.message);
      }
    }
  }
});