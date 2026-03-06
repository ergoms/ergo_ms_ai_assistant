/**
 * Модуль: BI Анализ
 * AI ассистент для анализа табличных данных
 */
import { Database } from 'lucide-vue-next'
import { markRaw } from 'vue'

export default {
  id: 'bi',
  name: 'BI Анализ',
  description: 'Анализ табличных данных',
  icon: markRaw(Database),
  color: '#10b981', // Green
  colorLight: 'rgba(16, 185, 129, 0.15)',
  enabled: true,
  
  // Настройки модуля
  settings: {
    welcomeMessage: 'Выберите файл для анализа данных.',
    placeholder: 'Задайте вопрос к данным...',
    maxTokens: 1024,
    requiresFile: true,
  },
  
  // Подсказки для пользователя
  suggestions: [
    'Покажи первые 10 строк',
    'Какие колонки в файле?',
    'Посчитай среднее значение',
    'Найди максимум по категориям',
  ],
}

