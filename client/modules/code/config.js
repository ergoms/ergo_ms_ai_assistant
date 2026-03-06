/**
 * Модуль: Помощник по коду
 * AI ассистент для генерации и анализа кода
 */
import { Code } from 'lucide-vue-next'
import { markRaw } from 'vue'

export default {
  id: 'code',
  name: 'Код',
  description: 'Генерация и анализ кода',
  icon: markRaw(Code),
  color: '#8b5cf6', // Purple
  colorLight: 'rgba(139, 92, 246, 0.15)',
  enabled: true,
  comingSoon: true, // Модуль в разработке
  
  // Настройки модуля
  settings: {
    welcomeMessage: 'Помогу с генерацией и анализом кода.',
    placeholder: 'Опишите задачу...',
    maxTokens: 4096,
    supportedLanguages: ['python', 'javascript', 'typescript', 'sql'],
  },
  
  // Подсказки для пользователя
  suggestions: [
    'Напиши функцию для...',
    'Объясни этот код',
    'Оптимизируй запрос',
    'Найди ошибку',
  ],
}


