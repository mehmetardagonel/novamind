// Platform detection and API URL helper for mobile

import { Capacitor } from '@capacitor/core'

/**
 * Get the correct API URL based on the platform
 * @returns {string} API URL
 */
export function getApiUrl() {
  const envUrl = import.meta.env.VITE_API_URL || 'http://localhost:8001'
  
  // If running in native mobile (not web)
  if (Capacitor.isNativePlatform()) {
    const platform = Capacitor.getPlatform()
    
    // For Android
    if (platform === 'android') {
      // Check if we're in emulator or physical device
      // If env has localhost, convert to emulator IP
      if (envUrl.includes('localhost') || envUrl.includes('127.0.0.1')) {
        return envUrl.replace('localhost', '10.0.2.2').replace('127.0.0.1', '10.0.2.2')
      }
    }
    
    // For iOS
    if (platform === 'ios') {
      // iOS simulator can use localhost
      // Physical device needs the computer's IP (set in .env)
      return envUrl
    }
  }
  
  // For web browser, use as-is
  return envUrl
}

/**
 * Check if running on native platform
 */
export function isNativePlatform() {
  return Capacitor.isNativePlatform()
}

/**
 * Get current platform
 */
export function getPlatform() {
  return Capacitor.getPlatform()
}

export default {
  getApiUrl,
  isNativePlatform,
  getPlatform
}
