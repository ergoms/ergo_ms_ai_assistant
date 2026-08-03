import { apiClient } from '@/js/api/manager'
import { logError } from '@/js/utils/logError.js'
import { tGlobal } from '@/i18n/index.js'

import { endpoints } from './endpoints.js'

const OLLAMA_STATUS_ENDPOINT = endpoints.ollamaStatus
const EMBEDDINGS_STATUS_ENDPOINT = endpoints.embeddingsStatus

let cachedStatus = null
let lastCheck = 0
const CHECK_INTERVAL_MS = 45000

function pickDisplayModel(data) {
  const models = data?.models
  if (Array.isArray(models) && models.length > 0) {
    return models[0]
  }
  return null
}

function normalizeOllamaResponse(data) {
  const available = Boolean(data?.available)
  const model = pickDisplayModel(data)

  return {
    available,
    models: data?.models || [],
    model,
    modelLoaded: Boolean(data?.model_loaded),
    baseUrl: data?.base_url || null,
    processRunning: Boolean(data?.process_running),
    message:
      data?.message ||
      (available ? tGlobal('ai_assistant.ollama.available') : data?.error || tGlobal('ai_assistant.ollama.unavailable')),
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

  try {
    const requests = [apiClient.get(OLLAMA_STATUS_ENDPOINT)]
    if (includeEmbeddings) {
      requests.push(apiClient.get(EMBEDDINGS_STATUS_ENDPOINT))
    }

    const responses = await Promise.all(requests)
    const ollamaResponse = responses[0]
    const embeddingsResponse = includeEmbeddings ? responses[1] : null

    if (!ollamaResponse.success) {
      const message =
        ollamaResponse.data?.message ||
        ollamaResponse.data?.error ||
        ollamaResponse.message ||
        tGlobal('ai_assistant.ollama.statusCheckError')

      cachedStatus = {
        available: false,
        models: [],
        model: null,
        modelLoaded: false,
        baseUrl: null,
        processRunning: false,
        message,
        error: message,
        embeddings: includeEmbeddings ? false : undefined,
        embeddingsMessage: includeEmbeddings ? null : undefined,
      }
      lastCheck = now
      return { ...cachedStatus }
    }

    const normalized = normalizeOllamaResponse(ollamaResponse.data)

    if (includeEmbeddings && embeddingsResponse) {
      normalized.embeddings = Boolean(embeddingsResponse.success && embeddingsResponse.data?.available)
      normalized.embeddingsMessage = embeddingsResponse.data?.message || null
    }

    cachedStatus = normalized
    lastCheck = now
    return { ...cachedStatus }
  } catch (error) {
    logError('Ошибка проверки Ollama', error)
    const message =
      error.response?.data?.error ||
      error.response?.data?.message ||
      error.message ||
      tGlobal('ai_assistant.ollama.connectFailed')

    cachedStatus = {
      available: false,
      models: [],
      model: null,
      modelLoaded: false,
      baseUrl: null,
      processRunning: false,
      message,
      error: message,
      embeddings: includeEmbeddings ? false : undefined,
      embeddingsMessage: includeEmbeddings ? message : undefined,
    }
    lastCheck = now
    return { ...cachedStatus }
  }
}

export function resetOllamaStatusCache() {
  cachedStatus = null
  lastCheck = 0
}
