import apiClient from './client'

/**
 * Authentication API functions
 */

/**
 * User login
 * @param {string} username - Username
 * @param {string} password - Password
 * @returns {Promise} Login response with token and user data
 */
export const login = async (username, password) => {
  try {
    // FastAPI OAuth2PasswordRequestForm expects form data, not JSON
    const formData = new FormData()
    formData.append('username', username)
    formData.append('password', password)

    const response = await apiClient.post('/api/auth/login', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })

    // Store token and user data in localStorage
    if (response.data.access_token) {
      localStorage.setItem('access_token', response.data.access_token)
      localStorage.setItem('user', JSON.stringify(response.data.user))
    }

    return response.data
  } catch (error) {
    throw error.response?.data || error
  }
}

/**
 * User signup
 * @param {Object} userData - User registration data
 * @param {string} userData.email - Email address
 * @param {string} userData.username - Username
 * @param {string} userData.password - Password
 * @param {string} [userData.full_name] - Full name (optional)
 * @returns {Promise} Signup response with token and user data
 */
export const signup = async (userData) => {
  try {
    const response = await apiClient.post('/api/auth/signup', userData)

    // Store token and user data in localStorage
    if (response.data.access_token) {
      localStorage.setItem('access_token', response.data.access_token)
      localStorage.setItem('user', JSON.stringify(response.data.user))
    }

    return response.data
  } catch (error) {
    throw error.response?.data || error
  }
}

/**
 * Get current user information
 * @returns {Promise} Current user data
 */
export const getCurrentUser = async () => {
  try {
    const response = await apiClient.get('/api/auth/me')
    return response.data
  } catch (error) {
    throw error.response?.data || error
  }
}

/**
 * Logout user
 */
export const logout = () => {
  localStorage.removeItem('access_token')
  localStorage.removeItem('user')
}

/**
 * Check if user is authenticated
 * @returns {boolean} True if user has valid token
 */
export const isAuthenticated = () => {
  const token = localStorage.getItem('access_token')
  return !!token
}

/**
 * Get stored user data
 * @returns {Object|null} User data from localStorage
 */
export const getStoredUser = () => {
  const userStr = localStorage.getItem('user')
  try {
    return userStr ? JSON.parse(userStr) : null
  } catch {
    return null
  }
}

export default {
  login,
  signup,
  getCurrentUser,
  logout,
  isAuthenticated,
  getStoredUser,
}
