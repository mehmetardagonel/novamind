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

  const headers = response.headers || {}
  const contentType =
    headers['content-type'] || headers['Content-Type'] || 'audio/wav'
  const responseSessionId =
    headers['x-session-id'] || headers['X-Session-Id'] || sessionId || null
  const userTranscript =
    headers['x-user-transcript'] || headers['X-User-Transcript'] || null
  const assistantReply =
    headers['x-assistant-reply'] || headers['X-Assistant-Reply'] || null
  const assistantTts =
    headers['x-assistant-tts'] || headers['X-Assistant-Tts'] || null
  const responseId =
    headers['x-voice-response-id'] || headers['X-Voice-Response-Id'] || null
  const isJson = contentType.toLowerCase().includes('application/json')

  if (isJson) {
    const decoder = new TextDecoder('utf-8')
    const text = decoder.decode(new Uint8Array(response.data || []))
    try {
      const payload = JSON.parse(text)
      return {
        audioBlob: null,
        sessionId: payload.session_id || responseSessionId,
        userTranscript: payload.transcript || userTranscript,
        assistantReply: payload.response_text || assistantReply,
        assistantTts,
        responseId,
      }
    } catch {
      return {
        audioBlob: null,
        sessionId: responseSessionId,
        userTranscript,
        assistantReply,
        assistantTts,
        responseId,
      }
    }
  }

  const replyAudioBlob = new Blob([response.data], { type: contentType })

  return {
    audioBlob: replyAudioBlob,
    sessionId: responseSessionId,
    userTranscript,
    assistantReply,
    assistantTts,
    responseId,
  }
}
