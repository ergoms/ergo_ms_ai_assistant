/**
 * Модуль: Общий чат
 * AI ассистент для общих вопросов о системе
 */
import { MessageSquare } from 'lucide-vue-next'
import { markRaw } from 'vue'
import { tGlobal } from '@/i18n/index.js'

export default {
  id: 'chat',
  get name() {
    return tGlobal('ai_assistant.modules.chat.name')
  },
  get description() {
    return tGlobal('ai_assistant.modules.chat.description')
  },
  icon: markRaw(MessageSquare),
  color: '#3b82f6', // Blue
  colorLight: 'rgba(59, 130, 246, 0.15)',
  enabled: true,

  // Настройки модуля
  settings: {
    get welcomeMessage() {
      return tGlobal('ai_assistant.modules.chat.welcome')
    },
    get placeholder() {
      return tGlobal('ai_assistant.modules.chat.placeholder')
    },
    maxTokens: 2048,
  },

  // Подсказки для пользователя
  get suggestions() {
    return [
      tGlobal('ai_assistant.modules.chat.s1'),
      tGlobal('ai_assistant.modules.chat.s2'),
      tGlobal('ai_assistant.modules.chat.s3'),
      tGlobal('ai_assistant.modules.chat.s4'),
    ]
  },
}
