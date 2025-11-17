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
    // On success, just return the response
    return response
  },
  (error) => {
    if (error.response) {
      // Server responded with error
      switch (error.response.status) {
        case 401:
          // CRITICAL FIX: Differentiate between Google Auth 401 and other 401s
          
          const isGoogleAuthError =
            // Check if the response body contains the unique 'auth_url' payload
            error.response.data &&
            error.response.data.auth_url;

          if (isGoogleAuthError) {
            // This is the Google Auth 401. Let the component handle the redirect to Google.
            // We must re-throw the original error to be caught by emaillist.vue's .catch() block.
            console.warn('Google Auth 401 detected. Passing error to component.');
            return Promise.reject(error);
          } else {
            // This is a DIFFERENT 401 (e.g., Supabase token expired). Execute original logic.
            console.error('Unauthorized (401). Signing out and redirecting to /login.');
            supabase.auth.signOut();
            window.location.href = '/login';
          }
          break;
        
        case 403:
          console.error('Access forbidden (403)');
          break;
        case 404:
          console.error('Resource not found (404)');
          break;
        case 500:
          console.error('Server error (500)');
          break;
        default:
          console.error('An error occurred:', error.response.data);
      }
    } else if (error.request) {
      // Request was made but no response received
      console.error('No response from server');
    } else {
      // Something happened in setting up the request
      console.error('Error:', error.message);
    }
    
    // For all unhandled cases, re-throw the error
    return Promise.reject(error);
  }
)

export default apiClient