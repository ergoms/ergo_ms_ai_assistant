import { apiClient } from '@/js/api/manager'
import { mediaApiClient } from '@/js/api/media-api-client'
import { fetchOllamaStatus } from '../../js/ollamaStatusApi.js'
import { tGlobal } from '@/i18n/index.js'

const CHAT_UPLOAD_OPTIONS = {
  targetDir: 'ai_assistant/chat_uploads',
  allowedTypes: ['pdf', 'docx', 'doc', 'txt', 'md'],
}

async function uploadChatFiles(filesArray) {
  const uploaded = await mediaApiClient.uploadMultiple(filesArray, CHAT_UPLOAD_OPTIONS)
  return uploaded.map((item, index) => ({
    path: item.path,
    original_name: item.original_name || filesArray[index]?.name || 'file',
  }))
}

/**
 * API Endpoints для RAG модуля AI Assistant
 */
const endpoints = {
  chat: 'ai_assistant/chat/',
  chatStream: 'ai_assistant/chat/stream/',
  ollamaStatus: 'ollama_framework/status/',
  chatSessions: 'ai_assistant/chat_sessions/',
  chatSessionDetail: (id) => `ai_assistant/chat_sessions/${id}/`,
}

/**
 * Клиент для работы с RAG Assistant (простой чат)
 */
class RAGClient {
  constructor() {
    this.ollamaAvailable = false
    this.lastCheck = 0
    this.checkInterval = 60000
    this.ollamaConfig = null // Настройки Ollama из module-config
  }

  /**
   * Устанавливает настройки Ollama из конфига модуля
   * @param {Object} config - настройки Ollama из module-config.json
   */
  setOllamaConfig(config) {
    this.ollamaConfig = config
  }

  /**
   * Проверка доступности Ollama
   */
  async checkOllamaStatus(force = false) {
    const result = await fetchOllamaStatus({ force })
    this.ollamaAvailable = result.available
    this.lastCheck = Date.now()
    return result
  }

  /**
   * Отправить сообщение в чат (без streaming)
   * @param {string} message - Сообщение пользователя
   * @param {Object} ollamaConfig - настройки Ollama (опционально)
   * @param {File|File[]|null} files - Файл или массив файлов для загрузки (опционально)
   * @returns {Promise<Object>}
   */
  async sendMessage(message, ollamaConfig = null, files = null) {
    try {
      // Используем настройки из параметра или из сохраненного конфига
      const config = ollamaConfig || this.ollamaConfig
      
      const filesArray = files ? (Array.isArray(files) ? files : [files]) : []
      const requestBody = {
        message: message,
      }

      if (config) {
        requestBody.ollama_config = {
          base_url: config.baseUrl,
          model: config.model,
          temperature: config.temperature,
          context_window: config.contextWindow,
          max_tokens: config.maxTokens,
        }
      }

      if (filesArray.length > 0) {
        requestBody.files_paths = await uploadChatFiles(filesArray)
      }
      
      const response = await apiClient.post(endpoints.chat, requestBody)

      if (response.success) {
        return {
          success: true,
          response: response.data.response || response.data.message,
        }
      }

      // Если success: false, но ответ получен
      return {
        success: false,
        error: response.data?.error || response.data?.message || tGlobal('ai_assistant.rag.api.processingError'),
      }
    } catch (error) {
      logError('Ошибка отправки сообщения:', error)
      
      // Извлекаем сообщение об ошибке из разных возможных мест
      const errorMessage = 
        error.response?.data?.error ||
        error.response?.data?.message ||
        error.message ||
        tGlobal('ai_assistant.rag.api.sendMessageFailed')
      
      return {
        success: false,
        error: errorMessage,
      }
    }
  }

  /**
   * Отправить сообщение в чат с поддержкой streaming (SSE)
   * @param {string} message - Сообщение пользователя
   * @param {Function} onChunk - Callback для каждого чанка текста
   * @param {Function} onDone - Callback при завершении (получает полный ответ, session_id, message_id, processing_time_ms)
   * @param {Function} onError - Callback при ошибке
   * @param {Object} ollamaConfig - настройки Ollama (опционально)
   * @param {string} sessionId - ID сессии чата (опционально)
   * @param {string} module - Модуль AI ассистента (опционально, по умолчанию 'chat')
   * @param {File|File[]|null} files - Файл или массив файлов для загрузки (опционально)
   * @param {boolean} enableVectorization - Включить векторизацию файлов для векторного поиска (опционально)
   * @returns {Promise<void>}
   */
  async sendMessageStream(message, onChunk, onDone, onError, ollamaConfig = null, sessionId = null, module = 'chat', files = null, enableVectorization = false) {
    // Используем настройки из параметра или из сохраненного конфига
    const config = ollamaConfig || this.ollamaConfig

    try {
      // Получаем базовый URL API (используем axios instance из apiClient)
      const baseUrl = apiClient.client?.defaults?.baseURL || `${apiClient.getBaseUrl()}api/`
      const url = `${baseUrl}${endpoints.chatStream}`
      
      // Получаем токен авторизации
      const token = apiClient.getAuthToken()
      
      const headers = {
        'Authorization': token ? `Bearer ${token}` : '',
        'Content-Type': 'application/json',
      }
      
      const filesArray = files ? (Array.isArray(files) ? files : [files]) : []
      const payload = {
        message: message,
        module: module,
        enable_vectorization: enableVectorization,
      }

      if (sessionId) {
        payload.session_id = sessionId
      }

      if (config) {
        payload.ollama_config = {
          base_url: config.baseUrl,
          model: config.model,
          temperature: config.temperature,
          context_window: config.contextWindow,
          max_tokens: config.maxTokens,
        }
      }

      if (filesArray.length > 0) {
        payload.files_paths = await uploadChatFiles(filesArray)
      }

      const requestBody = JSON.stringify(payload)
      
      const response = await fetch(url, {
        method: 'POST',
        headers: headers,
        body: requestBody,
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
        
        // Парсим SSE события из буфера
        const lines = buffer.split('\n')
        buffer = lines.pop() || '' // Оставляем неполную строку в буфере

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const jsonStr = line.slice(6).trim()
            if (!jsonStr) continue

            try {
              const event = JSON.parse(jsonStr)
              
              if (event.type === 'chunk' && onChunk) {
                accumulatedContent += event.text
                onChunk(event.text)
              } else if (event.type === 'done') {
                doneEventReceived = true
                if (onDone) {
                  onDone(event.full_response || accumulatedContent, {
                    session_id: event.session_id,
                    message_id: event.message_id,
                    processing_time_ms: event.processing_time_ms,
                    timestamp: event.timestamp,
                    skill_name: event.skill_name,
                    skill_call: event.skill_call,
                    chart_config: event.chart_config,
                  })
                }
              } else if (event.type === 'error' && onError) {
                doneEventReceived = true
                onError(event.message)
              }
            } catch (parseError) {
              logWarn('Ошибка парсинга SSE события:', parseError, jsonStr)
            }
          }
        }
      }

      // Если stream завершился без события done, вызываем onDone с накопленным контентом
      if (!doneEventReceived && accumulatedContent && onDone) {
        onDone(accumulatedContent)
      }
    } catch (error) {
      logError('Ошибка streaming сообщения:', error)
      if (onError) {
        onError(error.message || tGlobal('ai_assistant.rag.api.sendMessageFailed'))
      }
    }
  }

  /**
   * Получить список сессий чатов
   * @param {string} module - Фильтр по модулю (опционально)
   * @returns {Promise<Object>}
   */
  async getChatSessions(module = null) {
    try {
      const params = module ? { module } : {}
      const response = await apiClient.get(endpoints.chatSessions, params)
      
      if (response.success) {
        return {
          success: true,
          sessions: response.data.sessions || [],
          count: response.data.count || 0,
        }
      }
      
      return {
        success: false,
        error: response.data?.error || tGlobal('ai_assistant.rag.api.sessionsListError'),
      }
    } catch (error) {
      logError('Ошибка получения списка чатов:', error)
      return {
        success: false,
        error: error.message || tGlobal('ai_assistant.rag.api.sessionsListFailed'),
      }
    }
  }

  /**
   * Получить сессию чата с сообщениями
   * @param {string} sessionId - ID сессии
   * @returns {Promise<Object>}
   */
  async getChatSession(sessionId) {
    try {
      const response = await apiClient.get(endpoints.chatSessionDetail(sessionId))
      
      if (response.success) {
        return {
          success: true,
          session: response.data.session,
          messages: response.data.messages || [],
        }
      }
      
      return {
        success: false,
        error: response.data?.error || tGlobal('ai_assistant.rag.api.sessionError'),
      }
    } catch (error) {
      logError('Ошибка получения чата:', error)
      return {
        success: false,
        error: error.message || tGlobal('ai_assistant.rag.api.sessionFailed'),
      }
    }
  }

  /**
   * Создать новую сессию чата
   * @param {string} title - Название чата
   * @param {string} module - Модуль AI ассистента
   * @returns {Promise<Object>}
   */
  async createChatSession(title = null, module = 'chat') {
    try {
      const response = await apiClient.post(endpoints.chatSessions, {
        title: title || tGlobal('ai_assistant.sidebar.newChat'),
        module,
      })
      
      if (response.success) {
        return {
          success: true,
          session: response.data.session,
        }
      }
      
      return {
        success: false,
        error: response.data?.error || tGlobal('ai_assistant.chatCreateError'),
      }
    } catch (error) {
      logError('Ошибка создания чата:', error)
      return {
        success: false,
        error: error.message || tGlobal('ai_assistant.chatCreateFail'),
      }
    }
  }

  /**
   * Удалить сессию чата
   * @param {string} sessionId - ID сессии
   * @returns {Promise<Object>}
   */
  async deleteChatSession(sessionId) {
    try {
      const response = await apiClient.delete(endpoints.chatSessionDetail(sessionId))
      
      if (response.success) {
        return {
          success: true,
          message: response.data?.message || tGlobal('ai_assistant.chatDeleted'),
        }
      }
      
      return {
        success: false,
        error: response.data?.error || tGlobal('ai_assistant.chatDeleteError'),
      }
    } catch (error) {
      logError('Ошибка удаления чата:', error)
      return {
        success: false,
        error: error.message || tGlobal('ai_assistant.chatDeleteFail'),
      }
    }
  }
}

export const ragClient = new RAGClient()
export default RAGClient

