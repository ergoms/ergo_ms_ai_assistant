import { apiClient } from '@/js/api/manager'

/**
 * API Endpoints для RAG модуля AI Assistant
 */
const endpoints = {
  chat: 'ai_assistant/chat/',
  chatStream: 'ai_assistant/chat/stream/',
  ollamaStatus: 'ai_assistant/ollama_status/',
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
  async checkOllamaStatus() {
    const now = Date.now()
    
    if (this.lastCheck && (now - this.lastCheck < this.checkInterval)) {
      return { available: this.ollamaAvailable }
    }

    try {
      const response = await apiClient.get(endpoints.ollamaStatus)
      
      if (response.success) {
        this.ollamaAvailable = response.data.available
        this.lastCheck = now
        
        return {
          available: this.ollamaAvailable,
          message: response.data.message,
        }
      }
      
      // Если success: false, но ответ получен
      return { 
        available: false, 
        message: response.data?.message || response.data?.error || 'Ошибка проверки статуса' 
      }
    } catch (error) {
      console.error('Ошибка проверки Ollama:', error)
      this.ollamaAvailable = false
      
      // Извлекаем сообщение об ошибке из разных возможных мест
      const errorMessage = 
        error.response?.data?.error ||
        error.response?.data?.message ||
        error.message ||
        'Не удалось подключиться к Ollama'
      
      return { 
        available: false, 
        message: errorMessage
      }
    }
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
      
      // Нормализуем files в массив
      const filesArray = files ? (Array.isArray(files) ? files : [files]) : []
      
      // Если есть файлы, используем FormData
      if (filesArray.length > 0) {
        const formData = new FormData()
        formData.append('message', message)
        
        // Добавляем все файлы
        filesArray.forEach((file) => {
          formData.append('files', file)
        })
        
        // Добавляем настройки Ollama, если они есть
        if (config) {
          formData.append('ollama_config', JSON.stringify({
            base_url: config.baseUrl,
            model: config.model,
            temperature: config.temperature,
            context_window: config.contextWindow,
            max_tokens: config.maxTokens,
          }))
        }
        
        const response = await apiClient.post(endpoints.chat, formData, {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
        })
        
        if (response.success) {
          return {
            success: true,
            response: response.data.response || response.data.message,
          }
        }
        
        return {
          success: false,
          error: response.data?.error || response.data?.message || 'Ошибка обработки запроса',
        }
      }
      
      // Обычный JSON запрос без файла
      const requestBody = {
        message: message,
      }
      
      // Добавляем настройки Ollama, если они есть
      if (config) {
        requestBody.ollama_config = {
          base_url: config.baseUrl,
          model: config.model,
          temperature: config.temperature,
          context_window: config.contextWindow,
          max_tokens: config.maxTokens,
        }
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
        error: response.data?.error || response.data?.message || 'Ошибка обработки запроса',
      }
    } catch (error) {
      console.error('Ошибка отправки сообщения:', error)
      
      // Извлекаем сообщение об ошибке из разных возможных мест
      const errorMessage = 
        error.response?.data?.error ||
        error.response?.data?.message ||
        error.message ||
        'Не удалось отправить сообщение'
      
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
      
      // Если есть файлы, используем FormData
      let requestBody
      let headers = {
        'Authorization': token ? `Bearer ${token}` : '',
      }
      
      // Нормализуем files в массив
      const filesArray = files ? (Array.isArray(files) ? files : [files]) : []
      
      if (filesArray.length > 0) {
        const formData = new FormData()
        formData.append('message', message)
        formData.append('module', module)
        
        // Добавляем все файлы
        filesArray.forEach((file) => {
          formData.append('files', file)
        })
        
        // Добавляем session_id, если указан
        if (sessionId) {
          formData.append('session_id', sessionId)
        }
        
        // Добавляем настройки Ollama, если они есть
        if (config) {
          formData.append('ollama_config', JSON.stringify({
            base_url: config.baseUrl,
            model: config.model,
            temperature: config.temperature,
            context_window: config.contextWindow,
            max_tokens: config.maxTokens,
          }))
        }
        
        // Добавляем флаг векторизации
        formData.append('enable_vectorization', enableVectorization ? 'true' : 'false')
        
        requestBody = formData
        // Не устанавливаем Content-Type для FormData - браузер сделает это сам с boundary
      } else {
        // Обычный JSON запрос без файла
        requestBody = {
          message: message,
          module: module,
        }
        
        // Добавляем session_id, если указан
        if (sessionId) {
          requestBody.session_id = sessionId
        }
        
        // Добавляем настройки Ollama, если они есть
        if (config) {
          requestBody.ollama_config = {
            base_url: config.baseUrl,
            model: config.model,
            temperature: config.temperature,
            context_window: config.contextWindow,
            max_tokens: config.maxTokens,
          }
        }
        
        // Добавляем флаг векторизации
        requestBody.enable_vectorization = enableVectorization
        
        headers['Content-Type'] = 'application/json'
        requestBody = JSON.stringify(requestBody)
      }
      
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
                    sources: event.sources || [],
                    suggestions: event.suggestions || [],
                  })
                }
              } else if (event.type === 'error' && onError) {
                doneEventReceived = true
                onError(event.message)
              }
            } catch (parseError) {
              console.warn('Ошибка парсинга SSE события:', parseError, jsonStr)
            }
          }
        }
      }

      // Если stream завершился без события done, вызываем onDone с накопленным контентом
      if (!doneEventReceived && accumulatedContent && onDone) {
        onDone(accumulatedContent)
      }
    } catch (error) {
      console.error('Ошибка streaming сообщения:', error)
      if (onError) {
        onError(error.message || 'Не удалось отправить сообщение')
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
        error: response.data?.error || 'Ошибка получения списка чатов',
      }
    } catch (error) {
      console.error('Ошибка получения списка чатов:', error)
      return {
        success: false,
        error: error.message || 'Не удалось получить список чатов',
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
        error: response.data?.error || 'Ошибка получения чата',
      }
    } catch (error) {
      console.error('Ошибка получения чата:', error)
      return {
        success: false,
        error: error.message || 'Не удалось получить чат',
      }
    }
  }

  /**
   * Создать новую сессию чата
   * @param {string} title - Название чата
   * @param {string} module - Модуль AI ассистента
   * @returns {Promise<Object>}
   */
  async createChatSession(title = 'Новый чат', module = 'chat') {
    try {
      const response = await apiClient.post(endpoints.chatSessions, {
        title,
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
        error: response.data?.error || 'Ошибка создания чата',
      }
    } catch (error) {
      console.error('Ошибка создания чата:', error)
      return {
        success: false,
        error: error.message || 'Не удалось создать чат',
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
          message: response.data?.message || 'Чат удален',
        }
      }
      
      return {
        success: false,
        error: response.data?.error || 'Ошибка удаления чата',
      }
    } catch (error) {
      console.error('Ошибка удаления чата:', error)
      return {
        success: false,
        error: error.message || 'Не удалось удалить чат',
      }
    }
  }
}

export const ragClient = new RAGClient()
export default RAGClient

