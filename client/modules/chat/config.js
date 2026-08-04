/**
 * Единственный режим чата AI-хаба (без вариаций типов).
 */
import { MessageSquare } from 'lucide-vue-next'
import { markRaw } from 'vue'
import { tGlobal } from '@/i18n/index.js'

export default {
  id: 'chat',
  // Пусто: в UI не показываем название/описание типа чата
  name: '',
  description: '',
  icon: markRaw(MessageSquare),
  color: '#d0322d',
  colorLight: 'rgba(208, 50, 45, 0.12)',
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
