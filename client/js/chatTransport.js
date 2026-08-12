/**
 * ChatTransport — единый интерфейс для хаба и мини-чата.
 * default → ragClient; external → profile proxy stream + общие sessions API.
 */

import { apiClient } from '@/js/api/manager'
import { logError, logWarn } from '@/js/utils/logError.js'
import { tGlobal } from '@/i18n/index.js'
import { buildChatRequestHeaders, withUiLanguage } from './chatRequestContext.js'
import { isStreamDisconnectError } from './streamDisconnect.js'
import { ragClient } from '../rag/js/rag-client.js'
import { endpoints } from './endpoints.js'
import { DEFAULT_CHAT_PROFILE_ID } from './chatProfiles.js'

/**
 * @param {object} opts
 * @param {string} opts.url
 * @param {object} opts.payload
 * @param {Function} [opts.onChunk]
 * @param {Function} [opts.onDone]
 * @param {Function} [opts.onError]
 * @param {Function} [opts.onPreparing]
 */
async function consumeSseStream({
  url,
  payload,
  onChunk,
  onDone,
  onError,
  onPreparing,
}) {
  try {
    const token = apiClient.getAuthToken()
    const headers = buildChatRequestHeaders(token)
    const response = await fetch(url, {
      method: 'POST',
      headers,
      body: JSON.stringify(payload),
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.error || `HTTP error ${response.status}`)
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let accumulatedContent = ''
    let doneEventReceived = false

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const jsonStr = line.slice(6).trim()
        if (!jsonStr) continue
        try {
          const event = JSON.parse(jsonStr)
          if (event.type === 'preparing') {
            onPreparing?.(event.session_id || null)
          } else if (event.type === 'chunk' && onChunk) {
            accumulatedContent += event.text
            onChunk(event.text)
          } else if (event.type === 'done') {
            doneEventReceived = true
            onDone?.(event.full_response || accumulatedContent, {
              session_id: event.session_id,
              message_id: event.message_id,
              processing_time_ms: event.processing_time_ms,
              timestamp: event.timestamp,
              skill_name: event.skill_name,
              skill_call: event.skill_call,
              chart_config: event.chart_config,
              sources: event.sources,
            })
          } else if (event.type === 'error' && onError) {
            doneEventReceived = true
            onError(event.message)
          }
        } catch (parseError) {
          logWarn('Ошибка парсинга SSE события:', parseError, jsonStr)
        }
      }
    }

    if (!doneEventReceived && accumulatedContent && onDone) {
      onDone(accumulatedContent)
    }
    return { disconnected: false }
  } catch (error) {
    if (isStreamDisconnectError(error)) {
      return { disconnected: true }
    }
    logError('Ошибка streaming сообщения:', error)
    onError?.(error.message || tGlobal('ai_assistant.rag.api.sendMessageFailed'))
    return { disconnected: false }
  }
}

/**
 * @param {import('./chatProfiles.js').ChatProfileDescriptor} profile
 */
export function createChatTransport(profile) {
  const isExternal = Boolean(profile?.external) && profile.id !== DEFAULT_CHAT_PROFILE_ID

  return {
    profile,

    async sendMessageStream(
      message,
      onChunk,
      onDone,
      onError,
      ollamaConfig = null,
      sessionId = null,
      module = null,
      files = null,
      enableVectorization = false,
      onPreparing = null,
    ) {
      if (!isExternal) {
        return ragClient.sendMessageStream(
          message,
          onChunk,
          onDone,
          onError,
          ollamaConfig,
          sessionId,
          module || profile.sessionModule || 'chat',
          files,
          enableVectorization,
          onPreparing,
        )
      }

      const baseUrl = apiClient.client?.defaults?.baseURL || `${apiClient.getBaseUrl()}api/`
      const url = `${baseUrl}${endpoints.profileChatStream(profile.id)}`
      const sessionModule = module || profile.sessionModule || `${profile.id}_chat`
      const payload = withUiLanguage({
        message,
        module: sessionModule,
      })
      if (sessionId) payload.session_id = sessionId

      return consumeSseStream({
        url,
        payload,
        onChunk,
        onDone,
        onError,
        onPreparing,
      })
    },

    getChatSessions(module = null) {
      return ragClient.getChatSessions(module)
    },

    getChatSession(sessionId) {
      return ragClient.getChatSession(sessionId)
    },

    createChatSession(title = null, module = null) {
      return ragClient.createChatSession(
        title,
        module || profile.sessionModule || 'chat',
      )
    },

    deleteChatSession(sessionId) {
      return ragClient.deleteChatSession(sessionId)
    },
  }
}
