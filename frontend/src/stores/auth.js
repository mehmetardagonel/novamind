import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { supabase } from '@/database/supabaseClient'

export const useAuthStore = defineStore('auth', () => {
  // State
  const user = ref(null)
  const session = ref(null)
  const loading = ref(false)
  const error = ref(null)

  // Getters
  const isAuthenticated = computed(() => !!session.value)
  const currentUser = computed(() => user.value)

  // Actions
  const initialize = async () => {
    try {
      // Get current Supabase session
      const { data: { session: currentSession } } = await supabase.auth.getSession()

      if (currentSession) {
        session.value = currentSession
        user.value = currentSession.user
      }

      // Listen for auth state changes
      supabase.auth.onAuthStateChange((_event, newSession) => {
        session.value = newSession
        user.value = newSession?.user || null
      })
    } catch (err) {
      console.error('Failed to initialize auth:', err)
    }
  }

  const login = async (email, password) => {
    try {
      loading.value = true
      error.value = null

      // Append @gmail.com suffix if not present
      let fullEmail = email.trim()
      if (fullEmail && !fullEmail.includes('@')) {
        fullEmail = fullEmail + '@gmail.com'
      }

      const { data, error: loginError } = await supabase.auth.signInWithPassword({
        email: fullEmail,
        password: password,
      })

      if (loginError) throw loginError

      session.value = data.session
      user.value = data.user

      return data
    } catch (err) {
      error.value = err.message || 'Login failed'
      throw err
    } finally {
      loading.value = false
    }
  }

  const signup = async (email, password) => {
    try {
      loading.value = true
      error.value = null

      // Append @gmail.com suffix if not present
      let fullEmail = email.trim()
      if (fullEmail && !fullEmail.includes('@')) {
        fullEmail = fullEmail + '@gmail.com'
      }

      const { data, error: signupError } = await supabase.auth.signUp({
        email: fullEmail,
        password: password,
      })

      if (signupError) throw signupError

      session.value = data.session
      user.value = data.user

      return data
    } catch (err) {
      error.value = err.message || 'Signup failed'
      throw err
    } finally {
      loading.value = false
    }
  }

  const logout = async () => {
    try {
      await supabase.auth.signOut()
      user.value = null
      session.value = null
      error.value = null
    } catch (err) {
      console.error('Logout error:', err)
    }
  }

  const refreshUser = async () => {
    try {
      const { data: { user: userData } } = await supabase.auth.getUser()
      user.value = userData
    } catch (err) {
      console.error('Failed to refresh user:', err)
      await logout()
    }
  }

  // Initialize store
  initialize()

  return {
    // State
    user,
    session,
    loading,
    error,
    // Getters
    isAuthenticated,
    currentUser,
    // Actions
    login,
    signup,
    logout,
    refreshUser,
  }
})
