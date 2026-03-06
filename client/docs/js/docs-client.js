import { apiClient } from '@/js/api/manager'

/**
 * API Endpoints для Docs модуля AI Assistant
 */
const endpoints = {
  documents: 'ai_assistant/knowledge_documents/',
  documentDetail: (id) => `ai_assistant/knowledge_documents/${id}/`,
  documentIndex: (id) => `ai_assistant/knowledge_documents/${id}/index/`,
  documentUnindex: (id) => `ai_assistant/knowledge_documents/${id}/unindex/`,
  embeddingsStatus: 'ai_assistant/embeddings_status/',
  chat: 'ai_assistant/chat/',
  chatStream: 'ai_assistant/chat/stream/',
  chatSessions: 'ai_assistant/chat_sessions/',
}

/**
 * Клиент для работы с Docs Assistant (RAG с документами)
 */
class DocsClient {
  constructor() {
    this.ollamaAvailable = false
    this.embeddingsAvailable = false
    this.lastCheck = 0
    this.checkInterval = 60000
    this.ollamaConfig = null
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
      return { 
        available: this.ollamaAvailable,
        embeddings: this.embeddingsAvailable 
      }
    }

    try {
      const [ollamaStatus, embeddingsStatus] = await Promise.all([
        apiClient.get('ai_assistant/ollama_status/'),
        apiClient.get(endpoints.embeddingsStatus)
      ])
      
      this.ollamaAvailable = ollamaStatus.success && ollamaStatus.data?.available
      this.embeddingsAvailable = embeddingsStatus.success && embeddingsStatus.data?.available
      this.lastCheck = now
      
      return {
        available: this.ollamaAvailable,
        embeddings: this.embeddingsAvailable,
        message: ollamaStatus.data?.message,
        embeddingsMessage: embeddingsStatus.data?.message,
      }
    } catch (error) {
      console.error('Ошибка проверки статуса:', error)
      this.ollamaAvailable = false
      this.embeddingsAvailable = false
      
      return { 
        available: false, 
        embeddings: false,
        message: error.message || 'Не удалось проверить статус'
      }
    }
  }

  /**
   * Получить список документов
   */
  async getDocuments() {
    try {
      const response = await apiClient.get(endpoints.documents)
      
      if (response.success) {
        return {
          success: true,
          documents: response.data.documents || [],
          count: response.data.count || 0,
        }
      }
      
      return {
        success: false,
        documents: [],
        error: response.data?.error || 'Не удалось загрузить документы'
      }
    } catch (error) {
      console.error('Ошибка загрузки документов:', error)
      return {
        success: false,
        documents: [],
        error: error.message || 'Не удалось загрузить документы'
      }
    }
  }

  /**
   * Получить документ по ID
   */
  async getDocument(documentId) {
    try {
      const response = await apiClient.get(endpoints.documentDetail(documentId))
      
      if (response.success) {
        return {
          success: true,
          document: response.data.document,
        }
      }
      
      return {
        success: false,
        error: response.data?.error || 'Документ не найден'
      }
    } catch (error) {
      console.error('Ошибка получения документа:', error)
      return {
        success: false,
        error: error.message || 'Не удалось получить документ'
      }
    }
  }

  /**
   * Создать документ из текста
   */
  async createDocumentFromText(title, content, source = '', metadata = {}, indexImmediately = false) {
    try {
      const response = await apiClient.post(endpoints.documents, {
        title,
        content,
        source,
        metadata,
        index_immediately: indexImmediately,
      })
      
      if (response.success) {
        return {
          success: true,
          document: response.data.document,
          indexingResult: response.data.indexing_result,
        }
      }
      
      return {
        success: false,
        error: response.data?.error || 'Не удалось создать документ'
      }
    } catch (error) {
      console.error('Ошибка создания документа:', error)
      return {
        success: false,
        error: error.response?.data?.error || error.message || 'Не удалось создать документ'
      }
    }
  }

  /**
   * Загрузить документ из файла
   */
  async uploadDocument(file, title, source = '', metadata = {}, indexImmediately = false) {
    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('title', title)
      if (source) formData.append('source', source)
      if (Object.keys(metadata).length > 0) {
        formData.append('metadata', JSON.stringify(metadata))
      }
      formData.append('index_immediately', indexImmediately)
      
      const response = await apiClient.post(endpoints.documents, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      })
      
      if (response.success) {
        return {
          success: true,
          document: response.data.document,
          indexingResult: response.data.indexing_result,
        }
      }
      
      return {
        success: false,
        error: response.data?.error || 'Не удалось загрузить документ'
      }
    } catch (error) {
      console.error('Ошибка загрузки документа:', error)
      return {
        success: false,
        error: error.response?.data?.error || error.message || 'Не удалось загрузить документ'
      }
    }
  }

  /**
   * Обновить документ
   */
  async updateDocument(documentId, updates) {
    try {
      const response = await apiClient.put(endpoints.documentDetail(documentId), updates)
      
      if (response.success) {
        return {
          success: true,
          document: response.data.document,
        }
      }
      
      return {
        success: false,
        error: response.data?.error || 'Не удалось обновить документ'
      }
    } catch (error) {
      console.error('Ошибка обновления документа:', error)
      return {
        success: false,
        error: error.response?.data?.error || error.message || 'Не удалось обновить документ'
      }
    }
  }

  /**
   * Удалить документ
   */
  async deleteDocument(documentId) {
    try {
      const response = await apiClient.delete(endpoints.documentDetail(documentId))
      
      if (response.success) {
        return {
          success: true,
          message: response.data?.message || 'Документ удален'
        }
      }
      
      return {
        success: false,
        error: response.data?.error || 'Не удалось удалить документ'
      }
    } catch (error) {
      console.error('Ошибка удаления документа:', error)
      return {
        success: false,
        error: error.message || 'Не удалось удалить документ'
      }
    }
  }

  /**
   * Индексировать документ
   */
  async indexDocument(documentId, force = false) {
    try {
      const response = await apiClient.post(endpoints.documentIndex(documentId), {
        force,
      })
      
      if (response.success) {
        return {
          success: true,
          result: response.data.result,
          document: response.data.document,
        }
      }
      
      return {
        success: false,
        error: response.data?.error || 'Не удалось проиндексировать документ'
      }
    } catch (error) {
      console.error('Ошибка индексации документа:', error)
      return {
        success: false,
        error: error.response?.data?.error || error.message || 'Не удалось проиндексировать документ'
      }
    }
  }

  /**
   * Деиндексировать документ
   */
  async unindexDocument(documentId) {
    try {
      const response = await apiClient.post(endpoints.documentUnindex(documentId))
      
      if (response.success) {
        return {
          success: true,
          message: response.data?.message || 'Документ деиндексирован',
          document: response.data.document,
        }
      }
      
      return {
        success: false,
        error: response.data?.error || 'Не удалось деиндексировать документ'
      }
    } catch (error) {
      console.error('Ошибка деиндексации документа:', error)
      return {
        success: false,
        error: error.message || 'Не удалось деиндексировать документ'
      }
    }
  }

  /**
   * Отправить сообщение в чат с документами (streaming)
   */
  async sendMessageStream(message, onChunk, onDone, onError, sessionId = null, documentId = null) {
    const config = this.ollamaConfig
    
    const requestBody = {
      message: message,
      module: 'docs',
    }
    
    if (sessionId) {
      requestBody.session_id = sessionId
    }
    
    if (documentId) {
      requestBody.document_id = documentId
    }
    
    if (config) {
      requestBody.ollama_config = {
        base_url: config.baseUrl || config.base_url,
        model: config.model,
        temperature: config.temperature,
        context_window: config.contextWindow || config.context_window,
        max_tokens: config.maxTokens || config.max_tokens,
      }
    }

    try {
      const baseUrl = apiClient.client?.defaults?.baseURL || `${apiClient.getBaseUrl()}api/`
      const url = `${baseUrl}${endpoints.chatStream}`
      const token = apiClient.getAuthToken()
      
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': token ? `Bearer ${token}` : '',
        },
        body: JSON.stringify(requestBody),
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
              console.warn('Ошибка парсинга SSE события:', parseError, jsonStr)
            }
          }
        }
      }

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
}

export const docsClient = new DocsClient()
export default DocsClient


