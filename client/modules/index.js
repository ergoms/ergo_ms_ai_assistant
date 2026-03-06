/**
 * AI Hub - Module Registry
 * Автоматическая регистрация AI помощников из папок модулей
 */

// Импорт конфигураций модулей
import chatConfig from './chat/config.js'
import biConfig from './bi/config.js'
import codeConfig from './code/config.js'
import docsConfig from './docs/config.js'

/**
 * Реестр всех AI модулей
 * Каждый модуль должен экспортировать конфигурацию с полями:
 * - id: string - уникальный идентификатор
 * - name: string - название модуля
 * - description: string - краткое описание
 * - icon: Component - иконка из lucide-vue-next
 * - color: string - цвет акцента модуля
 * - enabled: boolean - включен ли модуль
 * - component: Component | null - компонент модуля (null = coming soon)
 */
export const modules = [
  chatConfig,
  biConfig,
  codeConfig,
  docsConfig,
]

/**
 * Получить активные модули
 */
export const getEnabledModules = () => {
  return modules.filter(m => m.enabled)
}

/**
 * Получить модуль по ID
 */
export const getModuleById = (id) => {
  return modules.find(m => m.id === id)
}

export default modules


