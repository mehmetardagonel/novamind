import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as authAPI from '../api/auth'

export const useAuthStore = defineStore('auth', () => {
  // State
  const user = ref(null)
  const token = ref(null)
  const loading = ref(false)
  const error = ref(null)

  // Getters
  const isAuthenticated = computed(() => !!token.value)
  const currentUser = computed(() => user.value)

  // Actions
  const initialize = () => {
    // Load user and token from localStorage on app startup
    const storedUser = authAPI.getStoredUser()
    const storedToken = localStorage.getItem('access_token')

    if (storedUser && storedToken) {
      user.value = storedUser
      token.value = storedToken
    }
  }

  const login = async (username, password) => {
    try {
      loading.value = true
      error.value = null

      const response = await authAPI.login(username, password)

      user.value = response.user
      token.value = response.access_token

      return response
    } catch (err) {
      error.value = err.detail || 'Login failed'
      throw err
    } finally {
      loading.value = false
    }
  }

  const signup = async (userData) => {
    try {
      loading.value = true
      error.value = null

      const response = await authAPI.signup(userData)

      user.value = response.user
      token.value = response.access_token

      return response
    } catch (err) {
      error.value = err.detail || 'Signup failed'
      throw err
    } finally {
      loading.value = false
    }
  }

  const logout = () => {
    authAPI.logout()
    user.value = null
    token.value = null
    error.value = null
  }

  const refreshUser = async () => {
    try {
      const userData = await authAPI.getCurrentUser()
      user.value = userData
      localStorage.setItem('user', JSON.stringify(userData))
    } catch (err) {
      console.error('Failed to refresh user:', err)
      // If refresh fails, logout
      logout()
    }
  }

  // Initialize store
  initialize()

  return {
    // State
    user,
    token,
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
