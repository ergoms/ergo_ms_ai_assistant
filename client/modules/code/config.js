/**
 * Модуль: Помощник по коду
 * AI ассистент для генерации и анализа кода
 */
import { Code } from '@lucide/vue'
import { markRaw } from 'vue'
import { tGlobal } from '@/i18n/index.js'

export default {
  id: 'code',
  get name() {
    return tGlobal('ai_assistant.modules.code.name')
  },
  get description() {
    return tGlobal('ai_assistant.modules.code.description')
  },
  icon: markRaw(Code),
  color: '#8b5cf6', // Purple
  colorLight: 'rgba(139, 92, 246, 0.15)',
  enabled: true,
  comingSoon: true, // Модуль в разработке

  // Настройки модуля
  settings: {
    get welcomeMessage() {
      return tGlobal('ai_assistant.modules.code.welcome')
    },
    get placeholder() {
      return tGlobal('ai_assistant.modules.code.placeholder')
    },
    maxTokens: 4096,
    supportedLanguages: ['python', 'javascript', 'typescript', 'sql'],
  },

  // Подсказки для пользователя
  get suggestions() {
    return [
      tGlobal('ai_assistant.modules.code.s1'),
      tGlobal('ai_assistant.modules.code.s2'),
      tGlobal('ai_assistant.modules.code.s3'),
      tGlobal('ai_assistant.modules.code.s4'),
    ]
  },
}
