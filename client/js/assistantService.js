/**
 * Глобальный сервис для управления AI-ассистентом
 */
class AssistantService {
  constructor() {
    this.callbacks = {
      openChat: null,
      analyzeChart: null,
    }
  }

  /**
   * Регистрация функции открытия чата
   */
  registerOpenChat(callback) {
    this.callbacks.openChat = callback
  }

  /**
   * Регистрация функции анализа графика
   */
  registerAnalyzeChart(callback) {
    this.callbacks.analyzeChart = callback
  }

  /**
   * Открыть чат ассистента
   */
  openChat() {
    if (this.callbacks.openChat) {
      this.callbacks.openChat()
    } else {
      console.warn('AssistantService: openChat callback not registered')
    }
  }

  /**
   * Запустить анализ графика
   */
  analyzeChart(chartId) {
    if (this.callbacks.analyzeChart) {
      this.callbacks.analyzeChart(chartId)
    } else {
      console.warn('AssistantService: analyzeChart callback not registered')
    }
  }

  /**
   * Открыть чат и запустить анализ графика
   */
  openAndAnalyzeChart(chartId) {
    this.openChat()
    // Небольшая задержка для открытия чата
    setTimeout(() => {
      this.analyzeChart(chartId)
    }, 300)
  }
}

// Создаем единственный экземпляр сервиса
export const assistantService = new AssistantService()

// Composable для использования в компонентах
export function useAssistant() {
  return {
    openChat: () => assistantService.openChat(),
    analyzeChart: (chartId) => assistantService.analyzeChart(chartId),
    openAndAnalyzeChart: (chartId) => assistantService.openAndAnalyzeChart(chartId),
  }
}

