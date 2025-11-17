import apiClient from './client'

/**
 * Email API functions
 */

/**
 * Fetch emails from Gmail with optional filters
 * @param {Object} filters - Email filters
 * @param {string} [filters.sender] - Filter by sender
 * @param {string} [filters.subject_contains] - Filter by subject keywords
 * @param {boolean} [filters.unread] - Filter unread emails
 * @param {Array<string>} [filters.labels] - Filter by labels
 * @param {number} [filters.newer_than_days] - Filter by days
 * @param {string} [filters.since] - Filter by start date (ISO format)
 * @param {string} [filters.until] - Filter by end date (ISO format)
 * @returns {Promise} Array of emails
 */
export const fetchEmails = async (filters = {}) => {
  // Build query parameters
  const params = new URLSearchParams()

  if (filters.sender) params.append('sender', filters.sender)
  if (filters.subject_contains) params.append('subject_contains', filters.subject_contains)
  if (filters.unread !== undefined) params.append('unread', filters.unread)
  if (filters.labels && filters.labels.length > 0) {
    filters.labels.forEach(label => params.append('labels', label))
  }
  if (filters.newer_than_days) params.append('newer_than_days', filters.newer_than_days)
  if (filters.since) params.append('since', filters.since)
  if (filters.until) params.append('until', filters.until)

  // FIX: Removed try...catch. Errors now propagate to the client interceptor.
  const response = await apiClient.get(`/read-email?${params.toString()}`)
  return response.data
}

/**
 * Send email via Gmail
 * @param {Object} emailData - Email data
 * @param {string} emailData.to - Recipient email address
 * @param {string} emailData.subject - Email subject
 * @param {string} emailData.body - Email body
 * @returns {Promise} Send response
 */
export const sendEmail = async (emailData) => {
  // FIX: Removed try...catch.
  const response = await apiClient.post('/send-email', emailData)
  return response.data
}

/**
 * Get emails from today
 * @returns {Promise} Array of today's emails
 */
export const getTodayEmails = async () => {
  return fetchEmails({ newer_than_days: 1 })
}

/**
 * Get unread emails
 * @returns {Promise} Array of unread emails
 */
export const getUnreadEmails = async () => {
  return fetchEmails({ unread: true })
}

/**
 * Get emails by label
 * @param {string} label - Label name (e.g., 'Work', 'Personal', 'Promotions')
 * @returns {Promise} Array of emails with the label
 */
export const getEmailsByLabel = async (label) => {
  return fetchEmails({ labels: [label] })
}

/**
 * Search emails by sender
 * @param {string} sender - Sender name or email
 * @returns {Promise} Array of emails from sender
 */
export const searchBySender = async (sender) => {
  return fetchEmails({ sender })
}

/**
 * Search emails by subject
 * @param {string} subject - Subject keywords
 * @returns {Promise} Array of emails matching subject
 */
export const searchBySubject = async (subject) => {
  return fetchEmails({ subject_contains: subject })
}

export default {
  fetchEmails,
  sendEmail,
  getTodayEmails,
  getUnreadEmails,
  getEmailsByLabel,
  searchBySender,
  searchBySubject,
}