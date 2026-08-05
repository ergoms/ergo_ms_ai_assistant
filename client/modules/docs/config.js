/**
 * Модуль: Работа с документами
 * AI ассистент для анализа и генерации документов
 */
import { FileText } from 'lucide-vue-next'
import { markRaw } from 'vue'
import { tGlobal } from '@/i18n/index.js'

export default {
  id: 'docs',
  get name() {
    return tGlobal('ai_assistant.modules.docs.name')
  },
  get description() {
    return tGlobal('ai_assistant.modules.docs.description')
  },
  icon: markRaw(FileText),
  color: '#8b5cf6', // Purple/Violet (в стиле других модулей)
  colorLight: 'rgba(139, 92, 246, 0.15)',
  enabled: true,
  comingSoon: false, // Модуль готов к использованию

  // Настройки модуля
  settings: {
    get welcomeMessage() {
      return tGlobal('ai_assistant.modules.docs.welcome')
    },
    get placeholder() {
      return tGlobal('ai_assistant.modules.docs.placeholder')
    },
    maxTokens: 8192,
    supportedFormats: ['pdf', 'docx', 'txt', 'md', 'csv', 'xlsx', 'xls'],
  },

  // Подсказки для пользователя
  get suggestions() {
    return [
      tGlobal('ai_assistant.modules.docs.s1'),
      tGlobal('ai_assistant.modules.docs.s2'),
      tGlobal('ai_assistant.modules.docs.s3'),
      tGlobal('ai_assistant.modules.docs.s4'),
    ]
  },
}
