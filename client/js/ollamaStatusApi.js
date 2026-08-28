import { apiClient } from '@/js/api/manager'
import { logError } from '@/js/utils/logError.js'
import { tGlobal } from '@/i18n/index.js'
import { formatOllamaModelLabel } from './formatOllamaModelLabel.js'

import { endpoints } from './endpoints.js'

const OLLAMA_STATUS_ENDPOINT = endpoints.ollamaStatus
const EMBEDDINGS_STATUS_ENDPOINT = endpoints.embeddingsStatus

let cachedStatus = null
let lastCheck = 0
const CHECK_INTERVAL_MS = 45000

function pickDisplayModel(data) {
  if (data?.model) {
    return data.model
  }
  const models = data?.models
  if (Array.isArray(models) && models.length > 0) {
    return models[0]
  }
  return null
}

function emptyOllamaStatus(includeEmbeddings, message = '', forbidden = false) {
  return {
    available: false,
    models: [],
    model: null,
    modelLoaded: false,
    baseUrl: null,
    processRunning: false,
    message,
    error: message || null,
    embeddings: includeEmbeddings ? false : undefined,
    embeddingsMessage: includeEmbeddings ? null : undefined,
    forbidden,
  }
}

function isForbiddenStatusError(error) {
  const status = error?.response?.status ?? error?.status
  return status === 403
}

function normalizeOllamaResponse(data) {
  const available = Boolean(data?.available)
  const model = formatOllamaModelLabel(pickDisplayModel(data)) || null

  return {
    available,
    models: data?.models || [],
    model,
    modelLoaded: Boolean(data?.model_loaded),
    baseUrl: data?.base_url || null,
    processRunning: Boolean(data?.process_running),
    message:
      data?.message ||
      (available
        ? tGlobal('ai_assistant.ollama.available')
        : data?.error || tGlobal('ai_assistant.ollama.unavailable')),
    error: data?.error || null,
  }
}

/**
 * @param {{ force?: boolean, includeEmbeddings?: boolean }} options
 */
export async function fetchOllamaStatus(options = {}) {
  const { force = false, includeEmbeddings = false } = options
  const now = Date.now()

  if (!force && cachedStatus && lastCheck && now - lastCheck < CHECK_INTERVAL_MS) {
    return { ...cachedStatus }
  }

  const { canFetchOllamaStatus } = await import('./aiAssistantAccess.js')
  if (!(await canFetchOllamaStatus())) {
    cachedStatus = emptyOllamaStatus(includeEmbeddings)
    lastCheck = now
    return { ...cachedStatus }
  }

  try {
    const requests = [
      apiClient.get(OLLAMA_STATUS_ENDPOINT, {}, true, { quietStatuses: [403] }),
    ]
    if (includeEmbeddings) {
      requests.push(
        apiClient.get(EMBEDDINGS_STATUS_ENDPOINT, {}, true, { quietStatuses: [403] }),
      )
    }

    const responses = await Promise.all(requests)
    const ollamaResponse = responses[0]
    const embeddingsResponse = includeEmbeddings ? responses[1] : null

    if (!ollamaResponse.success) {
      const forbidden = ollamaResponse.status === 403
      const message = forbidden
        ? ''
        : ollamaResponse.data?.message
          || ollamaResponse.data?.error
          || ollamaResponse.message
          || tGlobal('ai_assistant.ollama.statusCheckError')

      cachedStatus = emptyOllamaStatus(includeEmbeddings, message, forbidden)
      lastCheck = now
      return { ...cachedStatus }
    }

    const normalized = normalizeOllamaResponse(ollamaResponse.data)

    if (includeEmbeddings && embeddingsResponse) {
      normalized.embeddings = Boolean(
        embeddingsResponse.success && embeddingsResponse.data?.available,
      )
      normalized.embeddingsMessage = embeddingsResponse.data?.message || null
    }

    cachedStatus = normalized
    lastCheck = now
    return { ...cachedStatus }
  } catch (error) {
    if (!isForbiddenStatusError(error)) {
      logError('Ошибка проверки Ollama', error)
    }
    const message = isForbiddenStatusError(error)
      ? ''
      : error.response?.data?.error
        || error.response?.data?.message
        || error.message
        || tGlobal('ai_assistant.ollama.connectFailed')

    cachedStatus = emptyOllamaStatus(
      includeEmbeddings,
      message,
      isForbiddenStatusError(error),
    )
    lastCheck = now
    return { ...cachedStatus }
  }
}

export function resetOllamaStatusCache() {
  cachedStatus = null
  lastCheck = 0
}
