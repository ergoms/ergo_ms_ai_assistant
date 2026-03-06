/**
 * Модуль: Работа с документами
 * AI ассистент для анализа и генерации документов
 */
import { FileText } from 'lucide-vue-next'
import { markRaw } from 'vue'

export default {
  id: 'docs',
  name: 'Документы',
  description: 'Работа с документами',
  icon: markRaw(FileText),
  color: '#8b5cf6', // Purple/Violet (в стиле других модулей)
  colorLight: 'rgba(139, 92, 246, 0.15)',
  enabled: true,
  comingSoon: false, // Модуль готов к использованию
  
  // Настройки модуля
  settings: {
    welcomeMessage: 'Помогу с анализом и созданием документов.',
    placeholder: 'Опишите задачу...',
    maxTokens: 8192,
    supportedFormats: ['pdf', 'docx', 'txt', 'md'],
  },
  
  // Подсказки для пользователя
  suggestions: [
    'Проанализируй документ',
    'Создай отчёт',
    'Суммируй текст',
    'Извлеки данные',
  ],
}


