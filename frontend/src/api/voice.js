import apiClient from '@/api/client'
import { supabase } from '@/database/supabaseClient'

const getUserId = async () => {
  const { data, error } = await supabase.auth.getUser()
  if (error) throw error
  return data?.user?.id || null
}

export const sendVoicePrompt = async (audioBlob, sessionId = null) => {
  if (!audioBlob) {
    throw new Error('audioBlob is required')
  }

  const userId = await getUserId()
  if (!userId) {
    throw new Error('User is not authenticated')
  }

  const formData = new FormData()
  formData.append('file', audioBlob, 'voice.webm')

  const query = sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : ''
  const response = await apiClient.post(`/voice/chat${query}`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
      'X-User-Id': userId,
    },
    responseType: 'arraybuffer',
  })

  const contentType = response.headers['content-type'] || 'audio/wav'
  const responseSessionId = response.headers['x-session-id'] || null
  const transcript = response.headers['x-transcript'] || null
  const replyAudioBlob = new Blob([response.data], { type: contentType })

  return {
    audioBlob: replyAudioBlob,
    sessionId: responseSessionId,
    transcript,
  }
}
