import { apiClient } from '@/js/api/manager'
import { fetchOllamaStatus } from '../../js/ollamaStatusApi.js'

/**
 * API Endpoints для BI модуля AI Assistant
 */
const endpoints = {
  files: 'ai_assistant/files/',
  biQuery: 'ai_assistant/bi_query/',
  ollamaStatus: 'ollama_framework/status/',
  chartAnalysis: 'ai_assistant/chart_analysis/',
}

/**
 * Клиент для работы с BI Assistant (Fast BI)
 */
class BIClient {
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

  async checkOllamaStatus(force = false) {
    const result = await fetchOllamaStatus({ force })
    this.ollamaAvailable = result.available
    this.lastCheck = Date.now()
    return result
  }

  async getUserFiles() {
    try {
      const response = await apiClient.get(endpoints.files)
      
      if (response.success) {
        return {
          success: true,
          files: response.data.files || [],
          count: response.data.count || 0,
        }
      }
      
      return { success: false, files: [], error: 'Не удалось загрузить файлы' }
    } catch (error) {
      logError('Ошибка загрузки файлов:', error)
      return { success: false, files: [], error: error.message }
    }
  }

  async getConnections() {
    try {
      const response = await apiClient.get('bi_analysis/bi_connections/')
      
      if (response.success !== false) {
        return {
          success: true,
          connections: Array.isArray(response.data) ? response.data : (response.data.results || []),
        }
      }
      
      return { success: false, connections: [], error: 'Не удалось загрузить подключения' }
    } catch (error) {
      logError('Ошибка загрузки подключений:', error)
      return { success: false, connections: [], error: error.message }
    }
  }

  async getConnectionFiles(connectionId) {
    try {
      const response = await apiClient.get(`bi_analysis/bi_datasets/connection/${connectionId}/files/`)
      
      if (response.success !== false) {
        return {
          success: true,
          files: Array.isArray(response.data) ? response.data : (response.data.results || response.data.files || []),
        }
      }
      
      return { success: false, files: [], error: 'Не удалось загрузить файлы подключения' }
    } catch (error) {
      logError('Ошибка загрузки файлов подключения:', error)
      return { success: false, files: [], error: error.message }
    }
  }

  async askQuestion(fileId, question, wantCommentary = true) {
    try {
      const response = await apiClient.post(endpoints.biQuery, {
        file_id: fileId,
        question: question,
        want_commentary: wantCommentary,
        stream: false,
      })

      if (response.success) {
        return {
          success: true,
          fileName: response.data.file_name,
          question: response.data.question,
          sql: response.data.sql,
          data: response.data.data,
          comment: response.data.comment,
          rows: response.data.rows,
          columns: response.data.columns,
        }
      }

      return {
        success: false,
        error: response.data?.error || 'Ошибка обработки запроса',
      }
    } catch (error) {
      return {
        success: false,
        error: error.message || 'Неизвестная ошибка',
      }
    }
  }

  async analyzeChart(chartId, onEvent) {
    try {
      const baseURL = apiClient.getBaseUrl() + apiClient.apiPath
      const token = apiClient.getAuthToken()
      
      const url = `${baseURL}${endpoints.chartAnalysis}`
      
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          chart_id: chartId,
          stream: true,
        }),
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        
        if (done) {
          break
        }

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))
              if (onEvent) {
                onEvent(data)
              }
            } catch {
              // Игнорируем ошибки парсинга
            }
          }
        }
      }

      return { success: true }
    } catch (error) {
      if (onEvent) {
        onEvent({
          type: 'error',
          message: error.message || 'Ошибка подключения',
        })
      }
      
      return {
        success: false,
        error: error.message || 'Неизвестная ошибка',
      }
    }
  }

  async askQuestionStream(fileId, question, wantCommentary = true, ollamaConfig = null, onEvent, sessionId = null) {
    try {
      const baseURL = apiClient.getBaseUrl() + apiClient.apiPath
      const token = apiClient.getAuthToken()
      
      const url = `${baseURL}${endpoints.biQuery}`
      
      // Используем настройки из параметра или из сохраненного конфига
      const config = ollamaConfig || this.ollamaConfig
      
      const requestBody = {
        file_id: fileId,
        question: question,
        want_commentary: wantCommentary,
        stream: true,
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
          sql_generation_tokens: config.sqlGenerationTokens,
          commentary_tokens: config.commentaryTokens,
        }
      }
      
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify(requestBody),
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        
        if (done) {
          break
        }

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))
              if (onEvent) {
                onEvent(data)
              }
            } catch (e) {
              logWarn('Не удалось распарсить SSE данные:', e)
            }
          }
        }
      }

      return { success: true }
    } catch (error) {
      if (onEvent) {
        onEvent({
          type: 'error',
          message: error.message || 'Ошибка подключения',
        })
      }
      
      return {
        success: false,
        error: error.message || 'Неизвестная ошибка',
      }
    }
  }
}

export const biClient = new BIClient()
export default BIClient

