/**
 * Модуль: Общий чат
 * AI ассистент для общих вопросов о системе
 */
import { MessageSquare } from 'lucide-vue-next'
import { markRaw } from 'vue'

export default {
  id: 'chat',
  name: 'Общий чат',
  description: 'Задавайте вопросы о системе',
  icon: markRaw(MessageSquare),
  color: '#3b82f6', // Blue
  colorLight: 'rgba(59, 130, 246, 0.15)',
  enabled: true,
  
  // Настройки модуля
  settings: {
    welcomeMessage: 'Привет! Я AI ассистент системы ERGO MS. Чем могу помочь?',
    placeholder: 'Напишите сообщение...',
    maxTokens: 2048,
  },
  
  // Подсказки для пользователя
  suggestions: [
    'Как работает система?',
    'Расскажи о возможностях',
    'Помоги с навигацией',
    'Объясни функционал',
  ],
}

