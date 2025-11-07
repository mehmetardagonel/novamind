import axios from 'axios'
import { supabase } from '@/database/supabaseClient'

// Get API base URL from environment variables or use default
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// Create axios instance with default configuration
const apiClient = axios.create({
  baseURL: API_URL,
  timeout: 30000, // 30 seconds
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor - add Supabase auth token to requests
apiClient.interceptors.request.use(
  async (config) => {
    // Get current Supabase session
    const { data: { session } } = await supabase.auth.getSession()

    if (session?.access_token) {
      config.headers.Authorization = `Bearer ${session.access_token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor - handle errors globally
apiClient.interceptors.response.use(
  (response) => {
    return response
  },
  (error) => {
    if (error.response) {
      // Server responded with error
      switch (error.response.status) {
        case 401:
          // Unauthorized - sign out from Supabase and redirect to login
          supabase.auth.signOut()
          window.location.href = '/login'
          break
        case 403:
          console.error('Access forbidden')
          break
        case 404:
          console.error('Resource not found')
          break
        case 500:
          console.error('Server error')
          break
        default:
          console.error('An error occurred:', error.response.data)
      }
    } else if (error.request) {
      // Request was made but no response received
      console.error('No response from server')
    } else {
      // Something happened in setting up the request
      console.error('Error:', error.message)
    }
    return Promise.reject(error)
  }
)

export default apiClient
